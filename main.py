import fitz  # PyMuPDF
import base64
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image

app = Flask(__name__)
CORS(app)

def extract_text_by_y(page):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" in block:
            for line in block["lines"]:
                line_text = " ".join([span["text"] for span in line["spans"]])
                y = line["bbox"][1]
                lines.append({"text": line_text, "y": y})
    return lines

def get_nearest_text(lines, y_value):
    lines_sorted = sorted(lines, key=lambda l: abs(l["y"] - y_value))
    return lines_sorted[0]["text"] if lines_sorted else ""

def extract_images(page):
    images = []
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        try:
            bbox = page.get_image_bbox(xref)
            y_pos = bbox.y0
        except Exception:
            # Si falla, se ignora esta imagen
            continue

        try:
            base_image = fitz.Pixmap(page.parent, xref)
            if base_image.n > 4:
                base_image = fitz.Pixmap(fitz.csRGB, base_image)
            img_data = base_image.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode("utf-8")
            images.append({
                "image_base64": img_base64,
                "y": y_pos,
                "index": img_index + 1,
            })
        except Exception:
            continue

    return images

@app.route("/parse", methods=["POST"])
def parse():
    if "file" not in request.files:
        return jsonify({"error": "no file uploaded"}), 400

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

if __name__ == "__main__":
    app.run(debug=True)
