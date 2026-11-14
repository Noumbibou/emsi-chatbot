import uuid

import uuid

import pymupdf
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from config import COLLECTION, EMBEDDING_MODEL, QDRANT_URL

PDF_PATH = "data/brochure_emsi.pdf"
CHUNK_SIZE = 800   # caractères par chunk
OVERLAP = 150      # chevauchement entre deux chunks


def extract_pages(path):
    """Étape 0 : extraction du texte page par page (pymupdf)."""
    doc = pymupdf.open(path)
    return [(i + 1, page.get_text()) for i, page in enumerate(doc)]


def chunk_text(text, size, overlap):
    """Étape 1 : chunking, découpage en morceaux qui se chevauchent."""
    text = " ".join(text.split())  # nettoie les sauts de ligne et espaces multiples
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start:start + size].strip()
        if len(chunk) > 50:  # ignore les morceaux trop courts
            chunks.append(chunk)
        start += size - overlap
    return chunks


def main():
    pages = extract_pages(PDF_PATH)
    records = []  # (texte, numéro de page)
    for page_num, text in pages:
        for chunk in chunk_text(text, CHUNK_SIZE, OVERLAP):
            records.append((chunk, page_num))
    print(f"{len(pages)} pages -> {len(records)} chunks")

    # Étapes 2 et 3 : tokenisation + embedding, faites par BGE-M3
    print("Chargement de BGE-M3 (téléchargement au premier lancement)...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [r[0] for r in records]
    vectors = model.encode(
        texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True
    )

    # Stockage dans Qdrant
    client = QdrantClient(url=QDRANT_URL)
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec.tolist(),
            payload={"text": text, "page": page, "source": "brochure_emsi.pdf"},
        )
        for (text, page), vec in zip(records, vectors)
    ]
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"{len(points)} chunks stockés dans '{COLLECTION}'")


if __name__ == "__main__":
    main()