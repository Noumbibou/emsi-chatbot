import sys

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import COLLECTION, EMBEDDING_MODEL, QDRANT_URL

question = " ".join(sys.argv[1:]) or "Quelles sont les filières de l'EMSI ?"

model = SentenceTransformer(EMBEDDING_MODEL)
client = QdrantClient(url=QDRANT_URL)

vec = model.encode(question, normalize_embeddings=True).tolist()
results = client.query_points(collection_name=COLLECTION, query=vec, limit=3)

print(f"\nQuestion : {question}\n")
for p in results.points:
    print(f"[score {p.score:.3f} | page {p.payload['page']}]")
    print(p.payload["text"][:300], "...\n")