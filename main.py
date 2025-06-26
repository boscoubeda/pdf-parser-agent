from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import base64
from PIL import Image
import io

app = Flask(__name__)
CORS(app)

def extract_text_by_y(page):
    lines = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                text = s.get("text", "").strip()
                if text:
                    lines.append({"text": text, "y": s["bbox"][1]})
    return sorted(lines, key=lambda x: x["y"])  # ordenar de arriba a abajo

def get_nearest_text(text_lines, y_img):
    closest = None
    min_distance = float('inf')
    for line in text_lines:
        distance = abs(line['y'] - y_img)
        if distance < min_distance:
            min_distance = distance
            closest = line["text"]
    return closest

def extract_images(page):
    images_info = []
    pix = page.get_pixmap(dpi=150)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    # Detectar bloques con imágenes raster
    for img_index, img_dict in enumerate(page.get_images(full=True)):
        xref = img_dict[0]
        bbox = page.get_image_bbox(xref)
        y_pos = bbox.y0  # posición vertical

        base_image = fitz.Pixmap(page.parent, xref)
        if base_image.n > 4:  # convertir CMYK
            base_image = fitz.Pixmap(fitz.csRGB, base_image)

        image_bytes = base_image.tobytes("png")
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        images_info.append({
            "index": img_index + 1,
            "y": y_pos,
            "image_base64": encoded,
        })
    return images_info

@app.route("/parse", methods=["POST"])
def parse():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    doc = fitz.open(stream=file.read(), filetype="pdf")

    output = []
    for i, page in enumerate(doc):
        page_text = extract_text_by_y(page)
        page_images = extract_images(page)

        # asociar texto cercano a cada imagen
        for img in page_images:
            img["text_snippet"] = get_nearest_text(page_text, img["y"])

        output.append({
            "page": i + 1,
            "text_lines": page_text,
            "images": page_images
        })

    return jsonify(output)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
