from contextlib import asynccontextmanager

import ollama
from fastapi import FastAPI
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

state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Chargé une seule fois au démarrage, pas à chaque requête
    state["embedder"] = SentenceTransformer(EMBEDDING_MODEL)
    state["qdrant"] = QdrantClient(url=QDRANT_URL)
    yield
    state.clear()


app = FastAPI(title="EMSI ChatBot API", lifespan=lifespan)


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 1. Retrieval
    points = retrieve(req.question)
    context = "\n\n".join(
        f"[Page {p.payload['page']}] {p.payload['text']}" for p in points
    )

    # 2. Augmented Generation
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Contexte :\n{context}\n\nQuestion : {req.question}",
            },
        ],
    )

    return ChatResponse(
        answer=response["message"]["content"],
        sources=[
            Source(page=p.payload["page"], score=p.score, text=p.payload["text"][:200])
            for p in points
        ],
    )