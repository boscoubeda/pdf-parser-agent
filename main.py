from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
import base64
import os

app = Flask(__name__)

@app.route('/parse', methods=['POST'])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file received (request.files is empty)'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join('/tmp', filename)
    file.save(filepath)

    try:
        doc = fitz.open(filepath)
        pages_data = []

        for page_num, page in enumerate(doc, start=1):
            text_instances = page.get_text("dict")
            lines = []
            for block in text_instances.get("blocks", []):
                for line in block.get("lines", []):
                    line_text = " ".join([span["text"] for span in line.get("spans", [])])
                    lines.append({
                        "text": line_text,
                        "y": line["bbox"][1]
                    })

            images = []
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]
                img_b64 = base64.b64encode(img_bytes).decode('utf-8')

                # Obtener bbox aproximado (posición en página)
                img_rects = page.get_image_bbox(xref)
                img_y = img_rects.y0 if img_rects else 0

                # Buscar texto más cercano en Y
                closest_text = min(lines, key=lambda l: abs(l['y'] - img_y))['text'] if lines else ""

                images.append({
                    "index": img_index + 1,
                    "page": page_num,
                    "y": img_y,
                    "text_near": closest_text,
                    "image_base64": img_b64,
                    "ext": img_ext
                })

            pages_data.append({
                "page": page_num,
                "text_lines": lines,
                "images": images
            })

        return jsonify(pages_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        os.remove(filepath)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
