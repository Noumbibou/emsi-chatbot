import base64
import gc
import io
import json
import re
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
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
    IMAGE_CAPTION_COLLECTION,
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
    "les questions de suivi, mais les faits doivent venir du contexte. Recopie les noms "
    "propres EXACTEMENT comme ils sont écrits dans le contexte, lettre par lettre. "
    "Si l'information n'est pas dans le contexte, dis que tu ne la trouves pas dans "
    "la brochure. N'invente rien."
)

GREETINGS = re.compile(
    r"^\s*(bonjour|salut|salam|bonsoir|hello|hi|coucou)\b[\s!.?]*$", re.IGNORECASE
)
GREETING_ANSWER = (
    "Bonjour ! Posez-moi une question sur l'EMSI : filières, admission, campus…"
)

# Les images ne sont recherchées que si la question les demande.
VISUAL_REQUEST = re.compile(
    r"\b(photos?|images?|illustrations?|logos?|montre[rz]?(?:-moi)?|affiche[rz]?|voir)\b",
    re.IGNORECASE,
)

# Au pluriel ("les photos des labos"), plusieurs images ; sinon une seule.
PLURAL_VISUAL = re.compile(
    r"\b(photos|images|logos|illustrations|plusieurs|quelques|toutes|tous)\b",
    re.IGNORECASE,
)

NO_MATCH_ANSWER = (
    "Je ne retrouve pas cette image dans la brochure. Je ne reconnais pas les "
    "visages : je compare seulement avec les images de la brochure."
)

OLLAMA_OPTIONS = {"num_ctx": 3072, "num_predict": 250, "temperature": 0.2}
KEEP_ALIVE = "30m"

MAX_HISTORY_MESSAGES = 4  # les 2 derniers échanges
MAX_HISTORY_CHARS = 400  # par message
SHORT_QUESTION_WORDS = 8  # en dessous, la question est complétée pour la recherche

IMAGES_DIR = Path("data/images")
IMAGE_TOP_K = 4  # nombre maximal d'images (demande au pluriel)
IMAGE_MIN_SCORE = 0.22  # seuil texte -> image (CLIP)
IMAGE_MATCH_STRONG = 0.90  # seuil image -> image : "c'est la même image"
CAPTION_MIN_SCORE = 0.45  # seuil texte -> légende d'image (BGE-M3), à calibrer
CAPTION_STRONG = 0.55  # légende très proche de la question (ex. nom + titre)
CAPTION_MARGIN = 0.02  # écart minimal avec la légende suivante pour trancher seule
RRF_K = 60

state = {}
model_lock = RLock()


def get_model(key: str, name: str) -> SentenceTransformer:
    """Charge un modèle à la première utilisation seulement (économise la RAM)."""
    with model_lock:
        if key not in state:
            other_clip_model = {
                "clip_text": "clip_image",
                "clip_image": "clip_text",
            }.get(key)
            if other_clip_model in state:
                del state[other_clip_model]
                gc.collect()
            state[key] = SentenceTransformer(name)
        return state[key]


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["embedder"] = SentenceTransformer(EMBEDDING_MODEL)
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
    """Retrieval texte -> image : texte -> vecteur CLIP -> images proches."""
    if not state["qdrant"].collection_exists(IMAGE_COLLECTION):
        return []
    with model_lock:
        model = get_model("clip_text", TEXT_IMAGE_MODEL)
        vec = model.encode(query, normalize_embeddings=True).tolist()
        del model
    result = state["qdrant"].query_points(
        collection_name=IMAGE_COLLECTION, query=vec, limit=IMAGE_TOP_K
    )
    return [p for p in result.points if p.score >= IMAGE_MIN_SCORE]


def retrieve_image_captions(query: str):
    """Retrieval texte -> légendes : BGE-M3 sur le texte qui accompagne chaque image."""
    if not state["qdrant"].collection_exists(IMAGE_CAPTION_COLLECTION):
        return []
    vec = state["embedder"].encode(query, normalize_embeddings=True).tolist()
    result = state["qdrant"].query_points(
        collection_name=IMAGE_CAPTION_COLLECTION, query=vec, limit=IMAGE_TOP_K * 2
    )
    return [p for p in result.points if p.score >= CAPTION_MIN_SCORE]


def retrieve_by_image(img: Image.Image):
    """Retrieval image -> image : image -> vecteur CLIP -> images proches."""
    if not state["qdrant"].collection_exists(IMAGE_COLLECTION):
        return []
    with model_lock:
        model = get_model("clip_image", IMAGE_MODEL)
        vec = model.encode(img, normalize_embeddings=True).tolist()
        del model
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


def fuse_image_results(clip_points, caption_points):
    """Fusionne par RRF le classement CLIP (apparence) et celui des légendes (texte).

    Les légendes comptent double : l'apparence seule ne dit pas qui est une personne.
    """
    by_file = {}
    for p in [*clip_points, *caption_points]:
        by_file.setdefault(p.payload["file"], p)
    clip_keys = [p.payload["file"] for p in clip_points]
    caption_keys = [p.payload["file"] for p in caption_points]
    fused = rrf_fuse(clip_keys, caption_keys, caption_keys)
    return [(score, by_file[name]) for name, score in fused.items()][:IMAGE_TOP_K]


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
    image_contexts = []
    for point in image_points:
        context = point.payload.get("context") or ""
        image_contexts.append(
            f"[Illustration page {point.payload['page']} - {point.payload['file']}]\n"
            f"Contexte complet associé : {context or '(aucun texte associé)'}"
        )

    image_instructions = ""
    if image_points:
        image_instructions = (
            "\n\nDes illustrations pertinentes sont incluses dans les résultats "
            "d'image de la réponse et affichées directement à l'utilisateur dans "
            "l'interface. Elles existent donc bien, même si leurs pixels ne sont "
            "pas envoyés dans ce prompt. Appuie-toi sur leurs contextes complets "
            "et sur les extraits textuels pour les présenter. Ne dis jamais qu'il "
            "n'y a pas de photo ou d'image lorsqu'une illustration est listée. "
            "N'attribue une identité à une personne que si le contexte de la "
            "brochure associe explicitement cette personne à l'illustration."
        )

    sections = [f"Extraits textuels :\n{text_context or '(aucun extrait pertinent)'}"]
    if image_contexts:
        sections.append(
            "Illustrations pertinentes (jointes à la réponse et affichées dans "
            "l'interface) :\n" + "\n\n".join(image_contexts)
        )
    full_context = "\n\n".join(sections)

    return [
        {"role": "system", "content": SYSTEM_PROMPT + image_instructions},
        *recent_history(history),
        {
            "role": "user",
            "content": (
                f"Contexte documentaire :\n{full_context}\n\nQuestion : {question}"
            ),
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


def strong_uploaded_image_match(image_points):
    """Renvoie la meilleure correspondance de brochure si elle est assez forte."""
    best = image_points[0] if image_points else None
    score = best.score if best is not None else 0.0
    print(
        f"[image] meilleur score image->image = {score:.3f} "
        f"(seuil {IMAGE_MATCH_STRONG})"
    )

    if best is None or best.score < IMAGE_MATCH_STRONG:
        return None
    return best

def uploaded_image_answer(best) -> str:
    """Réponse fixe (sans LLM) pour une photo reconnue : la légende vient de la brochure."""
    page = best.payload["page"]
    parts = [
        p.strip()
        for p in (best.payload.get("context") or "").split(" | ")
        if p.strip()
    ]
    caption = " — ".join(p[:120] for p in parts[:2])

    answer = f"Cette image correspond à une image de la page {page} de la brochure EMSI."
    if caption:
        answer += f" La brochure l'accompagne de ce texte : « {caption} »."
    answer += (
        "\n\n(Il s'agit d'une correspondance avec une image de la brochure, "
        "pas d'une reconnaissance faciale.)"
    )
    return answer


def build_uploaded_image_messages(
    question: str, image_point, history: list[HistoryMessage]
) -> list[dict]:
    context = image_point.payload.get("context") or ""
    system_prompt = (
        SYSTEM_PROMPT
        + "\n\nL'utilisateur a envoyé une image qui correspond fortement à une "
        "illustration de la brochure. Réponds avec un texte bref, fluide et "
        "naturel, jamais en recopiant le contexte brut. Présente ce que montre "
        "l'illustration en t'appuyant exclusivement sur son contexte. Précise "
        "brièvement qu'il s'agit d'une correspondance avec une illustration de "
        "la brochure. Ne prétends pas reconnaître un visage et n'invente aucune "
        "identité."
    )
    user_prompt = (
        f"L'image envoyée correspond à l'illustration "
        f"{image_point.payload['file']} de la page "
        f"{image_point.payload['page']} de la brochure EMSI. Cette illustration "
        "est jointe à la réponse et affichée à l'utilisateur.\n\n"
        "Contexte complet associé à cette illustration :\n"
        f"{context or '(aucun texte associé dans la brochure)'}\n\n"
        f"Question de l'utilisateur : {question}"
    )
    return [
        {"role": "system", "content": system_prompt},
        *recent_history(history),
        {"role": "user", "content": user_prompt},
    ]


def clear_caption_match(caption_points) -> bool:
    """Vrai si une légende répond nettement à la question (ex. un nom + un titre)."""
    if not caption_points:
        return False
    best = caption_points[0].score
    second = caption_points[1].score if len(caption_points) > 1 else 0.0
    return best >= CAPTION_STRONG and best - second >= CAPTION_MARGIN


def run_retrieval(req: ChatRequest):
    # Photo envoyée : on cherche seulement des images proches, sans recherche texte.
    if req.image_base64:
        image_points = retrieve_by_image(decode_base64_image(req.image_base64))
        return [], image_points, []

    q = retrieval_query(req.question, req.history)
    text_points = retrieve_text(q)

    ranked_images = []
    # Les images ne sont cherchées que si la question les demande.
    if VISUAL_REQUEST.search(req.question):
        plural = bool(PLURAL_VISUAL.search(req.question))
        caption_points = retrieve_image_captions(q)

        if not plural and clear_caption_match(caption_points):
            # Une légende répond nettement (nom, titre) : on la garde seule.
            ranked_images = [(caption_points[0].score, caption_points[0])]
            mode = "légende nette"
        else:
            clip_points = retrieve_images(q)
            limit = IMAGE_TOP_K if plural else 1
            ranked_images = fuse_image_results(clip_points, caption_points)[:limit]
            mode = "fusion RRF"

        print(
            f"[images] mode={mode} | "
            f"légendes={[round(p.score, 2) for p in caption_points]} | "
            f"retenues={[p.payload['file'] for _, p in ranked_images]}"
        )
    image_points = [p for _, p in ranked_images]
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

    if req.image_base64:
        best = strong_uploaded_image_match(image_points)
        if best is None:
            return ChatResponse(answer=NO_MATCH_ANSWER, sources=[], images=[])
        return ChatResponse(
            answer=uploaded_image_answer(best),
            sources=[],
            images=to_images([(best.score, best)]),
        )

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

            if req.image_base64:
                best = strong_uploaded_image_match(image_points)
                images = to_images([(best.score, best)]) if best is not None else []
                answer = (
                    NO_MATCH_ANSWER if best is None else uploaded_image_answer(best)
                )
                yield ndjson({"type": "sources", "sources": []})
                yield ndjson(
                    {"type": "images", "images": [i.model_dump() for i in images]}
                )
                yield ndjson({"type": "token", "content": answer})
                yield ndjson({"type": "done"})
                print(f"[perf] image : recherche={t1 - t0:.1f}s")
                return

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
            traceback.print_exc()
            yield ndjson({"type": "error", "message": "Erreur pendant la génération."})

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )