import io
import base64
import fitz  # PyMuPDF
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import os

app = Flask(__name__)
CORS(app)

def extract_text_by_y(page):
    blocks = page.get_text("dict")["blocks"]
    lines = []
    for b in blocks:
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    lines.append({
                        "text": s["text"],
                        "y": s["bbox"][1]
                    })
    return sorted(lines, key=lambda x: x["y"])

def get_nearest_text(text_lines, y, threshold=50):
    nearest = [
        line["text"] for line in text_lines
        if abs(line["y"] - y) < threshold and line["text"].strip()
    ]
    return " ".join(nearest[:3])

def extract_images(page):
    images = []
    for img_index, img_dict in enumerate(page.get_images(full=True)):
        xref = img_dict[0]
        try:
            bbox = page.get_image_bbox(xref)
            y_pos = bbox.y0
        except Exception:
            y_pos = 0

        base_image = fitz.Pixmap(page.parent, xref)
        if base_image.n > 4:
            base_image = fitz.Pixmap(fitz.csRGB, base_image)

        image_bytes = base_image.tobytes("png")
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        images.append({
            "image_base64": image_base64,
            "y": y_pos,
            "index": img_index + 1
        })
    return images

@app.route('/parse', methods=['POST'])
def parse():
    file = request.files['file']
    doc = fitz.open(stream=file.read(), filetype="pdf")

    output = []
    for i, page in enumerate(doc):
        page_text = extract_text_by_y(page)
        page_images = extract_images(page)

        for img in page_images:
            img["text_snippet"] = get_nearest_text(page_text, img["y"])

        output.append({
            "page": i + 1,
            "text_lines": page_text,
            "images": page_images
        })

    return jsonify(output)

# === ESTE BLOQUE ES NECESARIO PARA RENDER ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
