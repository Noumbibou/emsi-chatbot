import json
import re
import time
from contextlib import asynccontextmanager
from typing import Literal

import ollama
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import COLLECTION, EMBEDDING_MODEL, LLM_MODEL, QDRANT_URL, TOP_K

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

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["embedder"] = SentenceTransformer(EMBEDDING_MODEL)
    state["qdrant"] = QdrantClient(url=QDRANT_URL)
    yield
    state.clear()


app = FastAPI(title="EMSI ChatBot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # développement uniquement, on restreindra plus tard
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class Source(BaseModel):
    page: int
    score: float
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


def retrieve(query: str):
    """Retrieval : texte -> vecteur -> chunks les plus proches dans Qdrant."""
    vec = state["embedder"].encode(query, normalize_embeddings=True).tolist()
    result = state["qdrant"].query_points(
        collection_name=COLLECTION, query=vec, limit=TOP_K
    )
    return result.points


def retrieval_query(question: str, history: list[HistoryMessage]) -> str:
    """Une question courte ('Et le Génie Financier ?') est complétée par la
    question précédente pour que la recherche sache de quoi on parle."""
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


def build_messages(question: str, points, history: list[HistoryMessage]) -> list[dict]:
    context = "\n\n".join(
        f"[Page {p.payload['page']}] {p.payload['text']}" for p in points
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *recent_history(history),
        {
            "role": "user",
            "content": f"Contexte :\n{context}\n\nQuestion : {question}",
        },
    ]


def to_sources(points) -> list[Source]:
    return [
        Source(page=p.payload["page"], score=p.score, text=p.payload["text"][:200])
        for p in points
    ]


def ndjson(event: dict) -> str:
    """Un événement = une ligne JSON (format NDJSON)."""
    return json.dumps(event, ensure_ascii=False) + "\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Version sans streaming : la réponse arrive d'un bloc."""
    if GREETINGS.match(req.question):
        return ChatResponse(answer=GREETING_ANSWER, sources=[])

    points = retrieve(retrieval_query(req.question, req.history))
    response = ollama.chat(
        model=LLM_MODEL,
        messages=build_messages(req.question, points, req.history),
        options=OLLAMA_OPTIONS,
        keep_alive=KEEP_ALIVE,
    )
    return ChatResponse(
        answer=response["message"]["content"], sources=to_sources(points)
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Version streaming : événements envoyés au fil de la génération.

    Types d'événements : sources, token, done, error.
    """

    def generate():
        if GREETINGS.match(req.question):
            yield ndjson({"type": "token", "content": GREETING_ANSWER})
            yield ndjson({"type": "done"})
            return
        try:
            t0 = time.perf_counter()
            points = retrieve(retrieval_query(req.question, req.history))
            t1 = time.perf_counter()
            yield ndjson(
                {
                    "type": "sources",
                    "sources": [s.model_dump() for s in to_sources(points)],
                }
            )

            first_token_at = None
            for chunk in ollama.chat(
                model=LLM_MODEL,
                messages=build_messages(req.question, points, req.history),
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
                f"total={t2 - t0:.1f}s | historique={len(req.history)} msg"
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