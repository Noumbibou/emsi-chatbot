import json
import uuid
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from config import IMAGE_COLLECTION, IMAGE_MODEL, QDRANT_URL

PDF_PATH = "data/Brochure-EMSI.pdf"
IMAGES_DIR = Path("data/images")
DETAIL_MIN = 3.0  # en dessous : image quasi uniforme (dégradé, aplat), ignorée
CONTEXT_CHARS = 300  # longueur du texte rattaché à chaque image


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


def nearby_text(page, bbox, max_chars: int) -> str:
    """Texte de la page le plus proche de l'image (légende, nom, titre)."""
    if not bbox:
        return ""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    nearest = sorted(blocks, key=lambda b: rect_distance(bbox, b[:4]))[:2]
    text = " ".join(" ".join(b[4].split()) for b in nearest)
    return text[:max_chars]


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
        context = nearby_text(doc[entry["page"] - 1], entry["bbox"], CONTEXT_CHARS)
        kept.append((entry, img, context))

    print(f"{len(kept)} images retenues, {len(skipped)} ignorées (trop uniformes) :")
    for name, score in skipped:
        print(f"  ignorée : {name} (détails = {score:.2f})")

    print("Chargement de CLIP (téléchargement au premier lancement)...")
    model = SentenceTransformer(IMAGE_MODEL)
    vectors = model.encode(
        [k[1] for k in kept],
        batch_size=8,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    client = QdrantClient(url=QDRANT_URL)
    if client.collection_exists(IMAGE_COLLECTION):
        client.delete_collection(IMAGE_COLLECTION)
    client.create_collection(
        collection_name=IMAGE_COLLECTION,
        vectors_config=VectorParams(size=vectors.shape[1], distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec.tolist(),
            payload={
                "file": entry["file"],
                "page": entry["page"],
                "width": entry["width"],
                "height": entry["height"],
                "context": context,
                "source": Path(PDF_PATH).name,
            },
        )
        for (entry, _img, context), vec in zip(kept, vectors)
    ]
    client.upsert(collection_name=IMAGE_COLLECTION, points=points)
    print(f"{len(points)} images stockées dans '{IMAGE_COLLECTION}'")


if __name__ == "__main__":
    main()