import json
from pathlib import Path

import pymupdf

PDF_PATH = "data/Brochure-EMSI.pdf"
OUT_DIR = Path("data/images")
MIN_SIDE = 150  # ignore les petites icônes et logos

def save_pixmap(doc, xref, path):
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:  # CMYK -> RGB
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)  # retire la transparence
    pix.save(str(path))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(PDF_PATH)
    manifest, seen = [], set()

    for page in doc:
        page_no = page.number + 1
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)
            width, height = img[2], img[3]
            if min(width, height) < MIN_SIDE:
                continue
            name = f"p{page_no:02d}_x{xref}.jpg"
            try:
                save_pixmap(doc, xref, OUT_DIR / name)
            except Exception as e:
                print(f"  ! page {page_no} xref {xref} ignorée ({e})")
                continue
            rects = page.get_image_rects(xref)
            bbox = [round(v) for v in rects[0]] if rects else None
            manifest.append(
                {
                    "file": name,
                    "page": page_no,
                    "width": width,
                    "height": height,
                    "bbox": bbox,
                }
            )

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{len(manifest)} images enregistrées dans {OUT_DIR}")
    for m in manifest:
        print(f"  page {m['page']:>2} | {m['file']} | {m['width']}x{m['height']}")


if __name__ == "__main__":
    main()