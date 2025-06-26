import io
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
from PIL import Image

app = Flask(__name__)
CORS(app)

def extract_text_by_y(page):
    """Extrae líneas de texto y las ordena por coordenada vertical."""
    lines = []
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if block["type"] == 0:  # texto
            for line in block["lines"]:
                line_text = " ".join([span["text"] for span in line["spans"]]).strip()
                y = line["bbox"][1]
                if line_text:
                    lines.append({"text": line_text, "y": y})
    return sorted(lines, key=lambda x: x["y"])

def extract_images(page):
    """Renderiza la página y detecta visualmente bloques de imagen."""
    images = []
    pix = page.get_pixmap()
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    width, height = img.size
    gray = img.convert("L")
    binarized = gray.point(lambda p: 0 if p < 250 else 255, mode="1")
    binarized = binarized.convert("L")

    pixels = binarized.load()

    visited = set()
    threshold = 10  # mínimo tamaño

    def flood_fill(x, y):
        """Detecta un grupo de píxeles conectados oscuros."""
        stack = [(x, y)]
        bounds = [x, y, x, y]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited or cx < 0 or cy < 0 or cx >= width or cy >= height:
                continue
            if pixels[cx, cy] < 255:
                visited.add((cx, cy))
                bounds[0] = min(bounds[0], cx)
                bounds[1] = min(bounds[1], cy)
                bounds[2] = max(bounds[2], cx)
                bounds[3] = max(bounds[3], cy)
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        stack.append((cx + dx, cy + dy))
        return bounds

    for y in range(height):
        for x in range(width):
            if (x, y) not in visited and pixels[x, y] < 255:
                x0, y0, x1, y1 = flood_fill(x, y)
                if (x1 - x0) > threshold and (y1 - y0) > threshold:
                    crop = img.crop((x0, y0, x1, y1))
                    buffered = io.BytesIO()
                    crop.save(buffered, format="PNG")
                    encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    center_y = (y0 + y1) // 2
                    images.append({
                        "image_base64": encoded,
                        "y": center_y,
                    })
    return images

def get_nearest_text(text_lines, y_img):
    """Relaciona una imagen con el texto más cercano verticalmente."""
    if not text_lines:
        return ""
    closest = min(text_lines, key=lambda t: abs(t["y"] - y_img))
    return closest["text"]

@app.route("/", methods=["POST"])
def parse():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
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
            "images": page_images,
        })

    return jsonify(output)
