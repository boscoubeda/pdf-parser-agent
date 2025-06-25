from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import base64
from io import BytesIO
from PIL import Image
import requests
import os

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

def extract_pdf_data_from_bytes(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
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

@app.route("/parse", methods=["POST"])
def parse_pdf_url():
    print(">> Request received")

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing 'url' in JSON body"}), 400

    pdf_url = data['url']
    print(">> Downloading PDF from:", pdf_url)

    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
        pdf_bytes = response.content
    except Exception as e:
        print(">> Error downloading PDF:", e)
        return jsonify({"error": "Failed to download PDF", "details": str(e)}), 400

    parsed_data = extract_pdf_data_from_bytes(pdf_bytes)
    return jsonify(parsed_data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
