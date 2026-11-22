import argparse

from PIL import Image
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import IMAGE_COLLECTION, IMAGE_MODEL, QDRANT_URL, TEXT_IMAGE_MODEL

parser = argparse.ArgumentParser()
parser.add_argument("query", nargs="*", help="texte de la recherche")
parser.add_argument("--image", help="chemin d'une image : cherche les images proches")
args = parser.parse_args()

if args.image:
    model = SentenceTransformer(IMAGE_MODEL)
    vec = model.encode(Image.open(args.image).convert("RGB"), normalize_embeddings=True)
    label = f"image {args.image}"
else:
    query = " ".join(args.query) or "photo du campus"
    model = SentenceTransformer(TEXT_IMAGE_MODEL)
    vec = model.encode(query, normalize_embeddings=True)
    label = f"« {query} »"

client = QdrantClient(url=QDRANT_URL)
results = client.query_points(
    collection_name=IMAGE_COLLECTION, query=vec.tolist(), limit=5
)

print(f"\nRecherche : {label}\n")
for p in results.points:
    print(f"[score {p.score:.3f} | page {p.payload['page']}] data/images/{p.payload['file']}")
    print(f"   texte proche : {p.payload['context'][:150]}\n")