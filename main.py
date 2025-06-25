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
        blocks = page.get_text("dict")["blocks"]
        lines_info = []
        for block in blocks:
            if block["type"] == 0:  # text block
                for line in block["lines"]:
                    text_line = " ".join([span["text"] for span in line["spans"]]).strip()
                    if text_line:
                        y_pos = line["bbox"][1]
                        lines_info.append({
                            "text": text_line,
                            "y": y_pos
                        })

        images = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            y_image = img[7]  # y-position of the image
            image = Image.open(BytesIO(image_bytes))

            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Find closest text line by vertical position
            closest_text = ""
            if lines_info:
                closest_text = min(lines_info, key=lambda l: abs(l["y"] - y_image))["text"]

            images.append({
                "index": img_index + 1,
                "y": y_image,
                "text_snippet": closest_text,
                "image_base64": img_str
            })

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

    file = request.files['file']
    parsed_data = extract_pdf_data(file)
    return jsonify(parsed_data)

app.run(host="0.0.0.0", port=8080, debug=False)
