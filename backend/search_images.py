import argparse

from PIL import Image
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import (
    EMBEDDING_MODEL,
    IMAGE_CAPTION_COLLECTION,
    IMAGE_COLLECTION,
    IMAGE_MODEL,
    QDRANT_URL,
    TEXT_IMAGE_MODEL,
)

parser = argparse.ArgumentParser()
parser.add_argument("query", nargs="*", help="texte de la recherche")
parser.add_argument("--image", help="chemin d'une image : cherche les images proches")
parser.add_argument(
    "--captions",
    action="store_true",
    help="cherche dans le texte qui accompagne les images (BGE-M3)",
)
args = parser.parse_args()

collection = IMAGE_COLLECTION
if args.image:
    model = SentenceTransformer(IMAGE_MODEL)
    vec = model.encode(Image.open(args.image).convert("RGB"), normalize_embeddings=True)
    label = f"image {args.image}"
elif args.captions:
    collection = IMAGE_CAPTION_COLLECTION
    query = " ".join(args.query) or "photo du directeur"
    model = SentenceTransformer(EMBEDDING_MODEL)
    vec = model.encode(query, normalize_embeddings=True)
    label = f"légendes « {query} »"
else:
    query = " ".join(args.query) or "photo du campus"
    model = SentenceTransformer(TEXT_IMAGE_MODEL)
    vec = model.encode(query, normalize_embeddings=True)
    label = f"apparence « {query} »"

client = QdrantClient(url=QDRANT_URL)
results = client.query_points(collection_name=collection, query=vec.tolist(), limit=5)

print(f"\nRecherche : {label}\n")
for p in results.points:
    print(f"[score {p.score:.3f} | page {p.payload['page']}] data/images/{p.payload['file']}")
    print(f"   texte proche : {p.payload['context'][:200]}\n")