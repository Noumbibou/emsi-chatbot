import base64
import io
import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import ollama
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION,
    EMBEDDING_MODEL,
    IMAGE_COLLECTION,
    IMAGE_MODEL,
    LLM_MODEL,
    QDRANT_URL,
    TEXT_IMAGE_MODEL,
    TOP_K,
)

SYSTEM_PROMPT = (
    "Tu es l'assistant officiel de l'EMSI (École Marocaine des Sciences de l'Ingénieur). "
    "Réponds en français, de façon claire et concise, en te basant UNIQUEMENT sur le "
    "contexte fourni. Tu peux utiliser l'historique de la conversation pour comprendre "
    "les questions de suivi, mais les faits doivent venir du contexte. Si l'information "
    "n'est pas dans le contexte, dis que tu ne la trouves pas dans la brochure. "
    "N'invente rien."
)

GREETINGS = re.compile(
    r"^\s*(bonjour|salut|salam|bonsoir|hello|hi|coucou)\b[\s!.?]*$", re.IGNORECASE
)
GREETING_ANSWER = (
    "Bonjour ! Posez-moi une question sur l'EMSI : filières, admission, campus…"
)

OLLAMA_OPTIONS = {"num_ctx": 3072, "num_predict": 250, "temperature": 0.2}
KEEP_ALIVE = "30m"

MAX_HISTORY_MESSAGES = 4  # les 2 derniers échanges
MAX_HISTORY_CHARS = 400  # par message
SHORT_QUESTION_WORDS = 8  # en dessous, la question est complétée pour la recherche

IMAGES_DIR = Path("data/images")
IMAGE_TOP_K = 3
IMAGE_MIN_SCORE = 0.22
RRF_K = 60

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["embedder"] = SentenceTransformer(EMBEDDING_MODEL)
    state["clip_text"] = SentenceTransformer(TEXT_IMAGE_MODEL)
    state["clip_image"] = SentenceTransformer(IMAGE_MODEL)
    state["qdrant"] = QdrantClient(url=QDRANT_URL)
    yield
    state.clear()


app = FastAPI(title="EMSI ChatBot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # développement uniquement
    allow_methods=["*"],
    allow_headers=["*"],
)

if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    print(
        f"[422] {request.url.path} | "
        f"content-type={request.headers.get('content-type')!r} | "
        f"body={str(exc.body)[:200]!r} | "
        f"erreurs={[(e['loc'], e['type']) for e in exc.errors()]}"
    )
    return JSONResponse(status_code=422, content={"detail": "Requête invalide."})


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    image_base64: str | None = None


class Source(BaseModel):
    page: int
    score: float
    text: str


class ImageResult(BaseModel):
    file: str
    page: int
    score: float
    rrf_score: float
    context: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    images: list[ImageResult] = Field(default_factory=list)


def decode_base64_image(b64_str: str) -> Image.Image:
    """Décode une chaîne base64 (avec ou sans préfixe data:image/...) en image RGB."""
    if "," in b64_str and b64_str.strip().startswith("data:"):
        b64_str = b64_str.split(",", 1)[1]
    raw = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def retrieve_text(query: str):
    """Retrieval texte : texte -> vecteur BGE-M3 -> chunks proches dans Qdrant."""
    vec = state["embedder"].encode(query, normalize_embeddings=True).tolist()
    result = state["qdrant"].query_points(
        collection_name=COLLECTION, query=vec, limit=TOP_K
    )
    return result.points


def retrieve_images(query: str):
    """Retrieval multimodal : texte -> vecteur CLIP -> images proches dans Qdrant."""
    if not state["qdrant"].collection_exists(IMAGE_COLLECTION):
        return []
    vec = state["clip_text"].encode(query, normalize_embeddings=True).tolist()
    result = state["qdrant"].query_points(
        collection_name=IMAGE_COLLECTION, query=vec, limit=IMAGE_TOP_K
    )
    return [p for p in result.points if p.score >= IMAGE_MIN_SCORE]


def retrieve_by_image(img: Image.Image):
    """Retrieval image -> image : image -> vecteur CLIP vision -> images proches."""
    if not state["qdrant"].collection_exists(IMAGE_COLLECTION):
        return []
    vec = state["clip_image"].encode(img, normalize_embeddings=True).tolist()
    result = state["qdrant"].query_points(
        collection_name=IMAGE_COLLECTION, query=vec, limit=IMAGE_TOP_K
    )
    return result.points


def rrf_fuse(*ranked_lists, k: int = RRF_K) -> dict[str, float]:
    """Fusion RRF (Reciprocal Rank Fusion) sur une ou plusieurs listes ordonnées."""
    scores: dict[str, float] = {}
    for ranking in ranked_lists:
        for rank, item_key in enumerate(ranking, start=1):
            scores[item_key] = scores.get(item_key, 0.0) + 1.0 / (k + rank)
    return dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))


def fuse_and_rank(text_points, image_points):
    """Combine les classements texte et image via RRF pour prioriser les pages/résultats."""
    text_keys = [f"page:{p.payload['page']}" for p in text_points]
    image_keys = [f"page:{p.payload['page']}" for p in image_points]
    page_rrf = rrf_fuse(text_keys, image_keys, k=RRF_K)

    ranked_images = []
    for p in image_points:
        page_key = f"page:{p.payload['page']}"
        rrf_val = page_rrf.get(page_key, 0.0) + (p.score * 0.01)
        ranked_images.append((rrf_val, p))

    ranked_images.sort(key=lambda pair: pair[0], reverse=True)
    return ranked_images


def retrieval_query(question: str, history: list[HistoryMessage]) -> str:
    """Complète une question courte avec la question précédente."""
    if history and len(question.split()) <= SHORT_QUESTION_WORDS:
        previous = [m.content for m in history if m.role == "user"]
        if previous:
            return f"{previous[-1][:300]} {question}"
    return question


def recent_history(history: list[HistoryMessage]) -> list[dict]:
    """Derniers messages, tronqués, pour limiter la taille du prompt."""
    return [
        {"role": m.role, "content": m.content[:MAX_HISTORY_CHARS]}
        for m in history[-MAX_HISTORY_MESSAGES:]
    ]


def build_messages(
    question: str, text_points, image_points, history: list[HistoryMessage]
) -> list[dict]:
    text_context = "\n\n".join(
        f"[Page {p.payload['page']}] {p.payload['text']}" for p in text_points
    )
    image_context = "\n".join(
        f"[Image page {p.payload['page']} - {p.payload['file']}] "
        f"Contexte visuel : {p.payload.get('context', '')}"
        for p in image_points
    )
    full_context = text_context
    if image_context:
        full_context = f"{text_context}\n\nIllustrations pertinentes :\n{image_context}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *recent_history(history),
        {
            "role": "user",
            "content": f"Contexte :\n{full_context}\n\nQuestion : {question}",
        },
    ]


def to_sources(points) -> list[Source]:
    return [
        Source(page=p.payload["page"], score=p.score, text=p.payload["text"][:200])
        for p in points
    ]


def to_images(ranked_images) -> list[ImageResult]:
    results = []
    for rrf_val, p in ranked_images:
        filename = p.payload["file"]
        results.append(
            ImageResult(
                file=filename,
                page=p.payload["page"],
                score=p.score,
                rrf_score=round(rrf_val, 6),
                context=p.payload.get("context", "")[:200],
                url=f"/images/{filename}",
            )
        )
    return results


def run_retrieval(req: ChatRequest):
    q = retrieval_query(req.question, req.history)
    text_points = retrieve_text(q)

    if req.image_base64:
        img = decode_base64_image(req.image_base64)
        image_points = retrieve_by_image(img)
        # Si la question est courte/générique avec une image, on complète la recherche texte
        # avec le contexte des images trouvées
        img_contexts = " ".join(
            p.payload.get("context", "") for p in image_points if p.payload.get("context")
        )
        if img_contexts:
            text_points = retrieve_text(f"{q} {img_contexts[:250]}")
    else:
        image_points = retrieve_images(q)

    ranked_images = fuse_and_rank(text_points, image_points)
    return text_points, image_points, ranked_images


def ndjson(event: dict) -> str:
    """Un événement = une ligne JSON (format NDJSON)."""
    return json.dumps(event, ensure_ascii=False) + "\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Version sans streaming : la réponse arrive d'un bloc."""
    if not req.image_base64 and GREETINGS.match(req.question):
        return ChatResponse(answer=GREETING_ANSWER, sources=[], images=[])

    text_points, image_points, ranked_images = run_retrieval(req)

    response = ollama.chat(
        model=LLM_MODEL,
        messages=build_messages(req.question, text_points, image_points, req.history),
        options=OLLAMA_OPTIONS,
        keep_alive=KEEP_ALIVE,
    )
    return ChatResponse(
        answer=response["message"]["content"],
        sources=to_sources(text_points),
        images=to_images(ranked_images),
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Version streaming : événements envoyés au fil de la génération.

    Types d'événements : sources, images, token, done, error.
    """

    def generate():
        if not req.image_base64 and GREETINGS.match(req.question):
            yield ndjson({"type": "token", "content": GREETING_ANSWER})
            yield ndjson({"type": "done"})
            return
        try:
            t0 = time.perf_counter()
            text_points, image_points, ranked_images = run_retrieval(req)
            t1 = time.perf_counter()

            yield ndjson(
                {
                    "type": "sources",
                    "sources": [s.model_dump() for s in to_sources(text_points)],
                }
            )
            yield ndjson(
                {
                    "type": "images",
                    "images": [img.model_dump() for img in to_images(ranked_images)],
                }
            )

            first_token_at = None
            for chunk in ollama.chat(
                model=LLM_MODEL,
                messages=build_messages(
                    req.question, text_points, image_points, req.history
                ),
                options=OLLAMA_OPTIONS,
                keep_alive=KEEP_ALIVE,
                stream=True,
            ):
                content = chunk["message"]["content"]
                if content:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    yield ndjson({"type": "token", "content": content})

            t2 = time.perf_counter()
            first = f"{first_token_at - t0:.1f}s" if first_token_at else "?"
            print(
                f"[perf] recherche={t1 - t0:.1f}s | premier token={first} | "
                f"total={t2 - t0:.1f}s | imgs={len(ranked_images)} | "
                f"historique={len(req.history)} msg"
            )
            yield ndjson({"type": "done"})
        except Exception as e:
            print(f"[stream] erreur : {e}")
            yield ndjson({"type": "error", "message": "Erreur pendant la génération."})

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )