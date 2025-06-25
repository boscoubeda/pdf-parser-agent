from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

def extract_pdf_data(file_stream):
    doc = fitz.open(stream=file_stream.read(), filetype="pdf")
    results = []

    for page_num, page in enumerate(doc):
        # Extraer líneas de texto con su posición
        lines_info = []
        try:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block["type"] == 0:  # text block
                    for line in block["lines"]:
                        y_pos = line["bbox"][1]
                        text_line = " ".join([span["text"] for span in line["spans"]]).strip()
                        if text_line:
                            lines_info.append({"y": y_pos, "text": text_line})
        except Exception as e:
            print(f"Error extracting text on page {page_num + 1}: {str(e)}")

        # Extraer imágenes
        images = []
        try:
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                y_image = img[7] if len(img) > 7 else 0
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image = Image.open(BytesIO(image_bytes))

                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

                # Buscar texto más cercano por coordenada Y
                closest_text = ""
                if lines_info:
                    closest_text = min(lines_info, key=lambda l: abs(l["y"] - y_image))["text"]

                images.append({
                    "index": img_index + 1,
                    "y": y_image,
                    "text_snippet": closest_text,
                    "image_base64": img_str
                })
        except Exception as e:
            print(f"Error extracting image on page {page_num + 1}: {str(e)}")

        results.append({
            "page": page_num + 1,
            "text_lines": lines_info,
            "images": images
        })

    return results

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if not request.files or 'file' not in request.files:
        return jsonify({"error": "No file received (request.files is empty)"}), 400

    try:
        file = request.files['file']
        parsed_data = extract_pdf_data(file)
        return jsonify(parsed_data)
    except Exception as e:
        return jsonify({"error": "Processing error", "details": str(e)}), 500

app.run(host="0.0.0.0", port=8080, debug=False)
