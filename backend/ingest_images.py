import gc
import json
import uuid
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from config import (
    EMBEDDING_MODEL,
    IMAGE_CAPTION_COLLECTION,
    IMAGE_COLLECTION,
    IMAGE_MODEL,
    QDRANT_URL,
)

PDF_PATH = "data/Brochure-EMSI.pdf"
IMAGES_DIR = Path("data/images")
DETAIL_MIN = 3.0  # en dessous : image quasi uniforme (dégradé, aplat), ignorée
NEAREST_BLOCKS = 4  # nombre de blocs de texte rattachés à chaque image
BLOCK_CHARS = 200  # longueur maximale conservée par bloc
LONG_BLOCK = 200  # au-dessus : paragraphe (passe après les blocs courts)
CONTEXT_MAX = 700  # longueur totale du texte rattaché
MIN_CAPTION_CHARS = 15  # en dessous : pas de légende exploitable


def detail_score(img: Image.Image) -> float:
    """Mesure de détails : proche de 0 pour un dégradé ou un aplat."""
    small = np.asarray(img.convert("L").resize((64, 64)), dtype=np.float32)
    dx = np.abs(np.diff(small, axis=1)).mean()
    dy = np.abs(np.diff(small, axis=0)).mean()
    return float((dx + dy) / 2)


def rect_distance(a, b) -> float:
    """Distance entre deux rectangles (0 s'ils se touchent ou se chevauchent)."""
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dy * dy) ** 0.5


def is_noise(text: str) -> bool:
    """Ignore les blocs vides et les en-têtes à lettres espacées ('L A G R A N D E')."""
    tokens = text.split()
    if len(text) < 3:
        return True
    return len(tokens) >= 6 and sum(len(t) == 1 for t in tokens) / len(tokens) > 0.5


def nearby_text(page, bbox) -> str:
    """Texte de la page le plus proche de l'image (nom, légende, titre)."""
    if not bbox:
        return ""
    candidates = []
    for block in page.get_text("blocks"):
        if block[6] != 0:  # blocs d'image
            continue
        text = " ".join(block[4].split())
        if is_noise(text):
            continue
        candidates.append((rect_distance(bbox, block[:4]), text))

    nearest = sorted(candidates, key=lambda c: c[0])[:NEAREST_BLOCKS]
    # Les blocs courts (nom, titre, légende) d'abord, les longs paragraphes ensuite.
    nearest.sort(key=lambda c: (len(c[1]) > LONG_BLOCK, c[0]))
    return " | ".join(text[:BLOCK_CHARS] for _, text in nearest)[:CONTEXT_MAX]


def recreate_collection(client: QdrantClient, name: str, size: int) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=size, distance=Distance.COSINE),
    )


def payload(entry: dict, context: str) -> dict:
    return {
        "file": entry["file"],
        "page": entry["page"],
        "width": entry["width"],
        "height": entry["height"],
        "context": context,
        "source": Path(PDF_PATH).name,
    }


def main():
    manifest = json.loads((IMAGES_DIR / "manifest.json").read_text(encoding="utf-8"))
    doc = pymupdf.open(PDF_PATH)

    kept, skipped = [], []
    for entry in manifest:
        img = Image.open(IMAGES_DIR / entry["file"]).convert("RGB")
        score = detail_score(img)
        if score < DETAIL_MIN:
            skipped.append((entry["file"], score))
            continue
        img.thumbnail((768, 768))  # CLIP réduit de toute façon à 224 px
        context = nearby_text(doc[entry["page"] - 1], entry["bbox"])
        kept.append((entry, img, context))

    print(f"{len(kept)} images retenues, {len(skipped)} ignorées (trop uniformes) :")
    for name, score in skipped:
        print(f"  ignorée : {name} (détails = {score:.2f})")

    client = QdrantClient(url=QDRANT_URL)

    # 1) Vecteurs CLIP : recherche par apparence visuelle
    print("Chargement de CLIP...")
    clip = SentenceTransformer(IMAGE_MODEL)
    clip_vectors = clip.encode(
        [k[1] for k in kept],
        batch_size=8,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    recreate_collection(client, IMAGE_COLLECTION, clip_vectors.shape[1])
    client.upsert(
        collection_name=IMAGE_COLLECTION,
        points=[
            PointStruct(
                id=str(uuid.uuid4()), vector=vec.tolist(), payload=payload(e, ctx)
            )
            for (e, _img, ctx), vec in zip(kept, clip_vectors)
        ],
    )
    print(f"{len(kept)} images stockées dans '{IMAGE_COLLECTION}'")

    # On libère la mémoire de CLIP avant de charger BGE-M3.
    del clip
    gc.collect()

    # 2) Vecteurs BGE-M3 du texte voisin : recherche par légende
    captioned = [(e, ctx) for e, _img, ctx in kept if len(ctx) >= MIN_CAPTION_CHARS]
    print("Chargement de BGE-M3 pour les légendes...")
    text_model = SentenceTransformer(EMBEDDING_MODEL)
    text_vectors = text_model.encode(
        [ctx for _e, ctx in captioned],
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    recreate_collection(client, IMAGE_CAPTION_COLLECTION, text_vectors.shape[1])
    client.upsert(
        collection_name=IMAGE_CAPTION_COLLECTION,
        points=[
            PointStruct(
                id=str(uuid.uuid4()), vector=vec.tolist(), payload=payload(e, ctx)
            )
            for (e, ctx), vec in zip(captioned, text_vectors)
        ],
    )
    print(f"{len(captioned)} légendes stockées dans '{IMAGE_CAPTION_COLLECTION}'")

    # Contrôle : texte rattaché aux images de la page 5
    print("\nContrôle, images de la page 5 :")
    for e, _img, ctx in kept:
        if e["page"] == 5:
            print(f"  {e['file']} -> {ctx}")


if __name__ == "__main__":
    main()