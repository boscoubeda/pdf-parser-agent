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
        text = page.get_text("text")
        images = []

        for img_index, img in enumerate(page.get_images(full=True)):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image = Image.open(BytesIO(image_bytes))

                # ⛔ Filtrar imágenes "raras": pequeñas o transparentes
                if image.width < 50 or image.height < 50:
                    print(f"Skipped tiny image {img_index + 1} on page {page_num + 1}")
                    continue

                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

                images.append({
                    "page": page_num + 1,
                    "index": img_index + 1,
                    "image_base64": img_str
                })
            except Exception as e:
                print(f"Skipped image {img_index + 1} on page {page_num + 1}: {e}")
                continue

        results.append({
            "page": page_num + 1,
            "text": text.strip(),
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
