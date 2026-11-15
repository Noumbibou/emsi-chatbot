import json
import re
import time
from contextlib import asynccontextmanager

import ollama
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import COLLECTION, EMBEDDING_MODEL, LLM_MODEL, QDRANT_URL, TOP_K

SYSTEM_PROMPT = (
    "Tu es l'assistant officiel de l'EMSI (École Marocaine des Sciences de l'Ingénieur). "
    "Réponds en français, de façon claire et concise, en te basant UNIQUEMENT sur le "
    "contexte fourni. Si l'information n'est pas dans le contexte, dis que tu ne la "
    "trouves pas dans la brochure. N'invente rien."
)

GREETINGS = re.compile(
    r"^\s*(bonjour|salut|salam|bonsoir|hello|hi|coucou)\b[\s!.?]*$", re.IGNORECASE
)
GREETING_ANSWER = (
    "Bonjour ! Posez-moi une question sur l'EMSI : filières, admission, campus…"
)

OLLAMA_OPTIONS = {"num_ctx": 2048, "num_predict": 250, "temperature": 0.2}
KEEP_ALIVE = "30m"

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


class ChatRequest(BaseModel):
    question: str


class Source(BaseModel):
    page: int
    score: float
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


def retrieve(question: str):
    """Retrieval : question -> vecteur -> chunks les plus proches dans Qdrant."""
    vec = state["embedder"].encode(question, normalize_embeddings=True).tolist()
    result = state["qdrant"].query_points(
        collection_name=COLLECTION, query=vec, limit=TOP_K
    )
    return result.points


def build_messages(question: str, points) -> list[dict]:
    context = "\n\n".join(
        f"[Page {p.payload['page']}] {p.payload['text']}" for p in points
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
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

    points = retrieve(req.question)
    response = ollama.chat(
        model=LLM_MODEL,
        messages=build_messages(req.question, points),
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
            points = retrieve(req.question)
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
                messages=build_messages(req.question, points),
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
                f"total={t2 - t0:.1f}s"
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