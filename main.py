from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
from PIL import Image
import io
import os

app = Flask(__name__)
CORS(app)

def extract_text_by_y(page):
    """Extrae líneas de texto ordenadas por su posición vertical"""
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            line_text = " ".join([span["text"] for span in line["spans"]])
            y = line["bbox"][1]
            lines.append({"text": line_text, "y": y})
    return lines

def get_nearest_text(lines, image_y, threshold=50):
    """Busca el texto más cercano hacia arriba a la imagen (por coordenada y)"""
    lines_sorted = sorted(lines, key=lambda l: abs(l["y"] - image_y))
    for line in lines_sorted:
        if line["y"] < image_y:
            return line["text"]
    return ""

def extract_images(page):
    """Extrae imágenes renderizadas visualmente de la página"""
    images = []
    mat = fitz.Matrix(2, 2)  # mayor resolución
    pix = page.get_pixmap(matrix=mat, alpha=False)

    # usamos rects detectados por get_drawings para intentar identificar regiones raster
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "image":
                bbox = item[1]
                x0, y0, x1, y1 = bbox
                width, height = int(x1 - x0), int(y1 - y0)
                cropped = pix.crop((int(x0), int(y0), int(x1), int(y1)))
                image_bytes = cropped.tobytes("png")
                images.append({
                    "image": image_bytes,
                    "y": y0,
                    "text_snippet": ""
                })
    return images

@app.route("/", methods=["GET"])
def home():
    return "PDF parser online"

@app.route("/parse", methods=["POST"])
def parse():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

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

# Render: usar host 0.0.0.0 y puerto desde env var
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
