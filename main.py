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

    for page_num, page in enumerate(doc, start=1):
        # Extraer texto línea por línea con posición vertical Y
        lines = page.get_text("dict")["blocks"]
        text_lines = []
        for block in lines:
            for line in block.get("lines", []):
                line_text = " ".join([span["text"] for span in line["spans"]]).strip()
                if line_text:
                    text_lines.append({
                        "text": line_text,
                        "y": line["bbox"][1]  # posición vertical
                    })

        # Extraer imágenes
        image_data = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n < 5:  # sin canal alfa
                    pix_bytes = pix.tobytes("png")
                else:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    pix_bytes = pix.tobytes("png")
                encoded = base64.b64encode(pix_bytes).decode("utf-8")
                # buscar la posición aproximada de la imagen (si se puede)
                img_info = page.get_image_info(xref)
                y_position = img_info["bbox"][1] if "bbox" in img_info else 0

                # buscar snippet de texto cercano
                nearby_text = ""
                for t in text_lines:
                    if abs(t["y"] - y_position) < 50:
                        nearby_text = t["text"]
                        break

                image_data.append({
                    "image_base64": encoded,
                    "index": img_index + 1,
                    "y": y_position,
                    "text_snippet": nearby_text
                })
            except Exception as e:
                continue  # si falla una imagen, seguimos con las otras

        result.append({
            "page": page_num,
            "text_lines": text_lines,
            "images": image_data
        })

    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
