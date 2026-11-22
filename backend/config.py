import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement manquante : {name} (voir .env.example)"
        )
    return value


QDRANT_URL = _require("QDRANT_URL")
COLLECTION = os.getenv("QDRANT_COLLECTION", "emsi_text")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
TOP_K = int(os.getenv("TOP_K", "5"))

IMAGE_COLLECTION = os.getenv("IMAGE_COLLECTION", "emsi_images")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "clip-ViT-B-32")
TEXT_IMAGE_MODEL = os.getenv(
    "TEXT_IMAGE_MODEL", "sentence-transformers/clip-ViT-B-32-multilingual-v1"
)
IMAGE_CAPTION_COLLECTION = os.getenv("IMAGE_CAPTION_COLLECTION", "emsi_image_captions")