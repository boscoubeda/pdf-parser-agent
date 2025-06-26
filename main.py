from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import base64
import io
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/parse', methods=['POST'])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file received (request.files is empty)'}), 400

    file = request.files['file']
    pdf_bytes = file.read()

    doc = fitz.open(stream=pdf_bytes, filetype='pdf')

    result = []

    for page_number in range(len(doc)):
        page = doc.load_page(page_number)
        blocks = page.get_text("dict")["blocks"]

        text_lines = []
        for block in blocks:
            if block["type"] == 0:  # text block
                for line in block["lines"]:
                    line_text = " ".join(span["text"] for span in line["spans"]).strip()
                    if line_text:
                        y_pos = line["bbox"][1]  # y0 of the line
                        text_lines.append({"text": line_text, "y": y_pos})

        images_data = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            # Get image position
            image_rects = page.get_image_rects(xref)
            if image_rects:
                y_pos = image_rects[0].y0  # vertical position
            else:
                y_pos = 0  # fallback

            base64_img = base64.b64encode(image_bytes).decode("utf-8")
            images_data.append({
                "y": y_pos,
                "image_base64": base64_img,
                "ext": image_ext
            })

        result.append({
            "page": page_number + 1,
            "text_lines": text_lines,
            "images": images_data
        })

    return jsonify(result)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
