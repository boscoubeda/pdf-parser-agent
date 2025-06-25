from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import base64
from io import BytesIO
from PIL import Image
import os

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

def extract_pdf_data(file_stream):
    doc = fitz.open(stream=file_stream.read(), filetype="pdf")
    results = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        images = []

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(BytesIO(image_bytes))

            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            images.append({
                "page": page_num + 1,
                "index": img_index + 1,
                "image_base64": img_str
            })

        results.append({
            "page": page_num + 1,
            "text": text.strip(),
            "images": images
        })

    return results

@app.route("/", methods=["GET"])
def home():
    return "PDF Parser Agent is running", 200

@app.route("/upload", methods=["POST"])
def upload_pdf():
    print(">> Request received (binary)")
    if 'file' not in request.files:
        print(">> No file found in request")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    parsed_data = extract_pdf_data(file)
    return jsonify(parsed_data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
