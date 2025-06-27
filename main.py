from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import hashlib

app = Flask(__name__)
CORS(app)

def extract_text_by_y(page):
    blocks = page.get_text("dict")["blocks"]
    lines = []
    for b in blocks:
        if b["type"] == 0:
            for line in b["lines"]:
                for span in line["spans"]:
                    lines.append({
                        "text": span["text"],
                        "y": span["bbox"][1]
                    })
    return lines

def get_nearest_text(lines, y, threshold=50):
    nearest = None
    min_dist = float('inf')
    for line in lines:
        dist = abs(line["y"] - y)
        if dist < min_dist and dist < threshold:
            min_dist = dist
            nearest = line["text"]
    return nearest or ""

def image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

def extract_images_from_rendered(page, text_lines):
    mat = fitz.Matrix(2, 2)  # zoom x2
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    # Detect image-like blocks
    blocks = page.get_text("dict")["blocks"]
    images = []
    hashes = set()

    for b in blocks:
        if b["type"] == 1:  # image block
            x0, y0, x1, y1 = b["bbox"]
            width = int(x1 - x0)
            height = int(y1 - y0)
            if width < 20 or height < 20:
                continue  # descartar imágenes pequeñas

            crop = img.crop((int(x0 * 2), int(y0 * 2), int(x1 * 2), int(y1 * 2)))
            buffered = io.BytesIO()
            crop.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            img_hash = image_hash(img_bytes)

            if img_hash in hashes:
                continue  # imagen duplicada
            hashes.add(img_hash)

            image_data = {
                "image_base64": base64.b64encode(img_bytes).decode("utf-8"),
                "y": y0,
                "text_snippet": get_nearest_text(text_lines, y0)
            }
            images.append(image_data)

    return images

@app.route("/", methods=["POST"])
def parse():
    file = request.files["file"]
    doc = fitz.open(stream=file.read(), filetype="pdf")
    output = []

    for i, page in enumerate(doc):
        text_lines = extract_text_by_y(page)
        images = extract_images_from_rendered(page, text_lines)
        for idx, img in enumerate(images):
            img["page"] = i + 1
            img["index"] = idx + 1
        output.extend(images)

    return jsonify({"images": output})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
