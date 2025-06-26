from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import io
import base64

app = Flask(__name__)
CORS(app)

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file received (request.files is empty)"}), 400

    file = request.files["file"]
    pdf_bytes = file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    result = []

    for page_number, page in enumerate(doc, start=1):
        page_data = {
            "page": page_number,
            "text_lines": [],
            "images": []
        }

        # 1. Extraer texto con coordenadas
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # texto
                for line in block.get("lines", []):
                    line_text = " ".join([span["text"] for span in line["spans"]]).strip()
                    if line_text:
                        page_data["text_lines"].append({
                            "text": line_text,
                            "y": line["bbox"][1]
                        })

        # 2. Extraer imágenes incrustadas y renderizadas
        img_list = page.get_images(full=True)
        for idx, img in enumerate(img_list):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n < 5:
                    img_bytes = pix.tobytes("png")
                else:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_bytes = pix.tobytes("png")

                img_base64 = base64.b64encode(img_bytes).decode("utf-8")

                # Obtener posición (si es posible)
                image_info = page.get_image_info(xref)
                y_pos = image_info[0].get("bbox", [0, 0, 0, 0])[1] if image_info else 0

                # Buscar texto cercano
                snippet = ""
                min_dist = 9999
                for t in page_data["text_lines"]:
                    dist = abs(t["y"] - y_pos)
                    if dist < min_dist:
                        min_dist = dist
                        snippet = t["text"]

                page_data["images"].append({
                    "index": idx + 1,
                    "y": y_pos,
                    "text_snippet": snippet,
                    "image_base64": img_base64
                })

            except Exception:
                continue

        result.append(page_data)

    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
