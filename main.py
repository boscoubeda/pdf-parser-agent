from flask import Flask, request, jsonify
from flask_cors import CORS
import fitz  # PyMuPDF
import numpy as np
from PIL import Image
import io
import base64
import cv2

app = Flask(__name__)
CORS(app)

def extract_images_with_context(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_results = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_np = np.array(img)

        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        image_results = []
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            if w < 30 or h < 30:
                continue  # descarta elementos muy pequeños

            cropped = img_np[y:y+h, x:x+w]
            cropped_pil = Image.fromarray(cropped)
            buffer = io.BytesIO()
            cropped_pil.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

            snippet = ""
            for block in page.get_text("dict")["blocks"]:
                if block["type"] == 0:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if abs(span["bbox"][1] - y) < 50:  # cerca verticalmente
                                snippet = span["text"]
                                break
                        if snippet:
                            break
                if snippet:
                    break

            image_results.append({
                "image_base64": img_str,
                "y": y,
                "text_snippet": snippet.strip(),
                "page": page_index + 1,
                "index": len(image_results) + 1
            })

        all_results.append({
            "page": page_index + 1,
            "images": image_results,
            "text_lines": [
                {"text": span["text"], "y": span["bbox"][1]}
                for block in page.get_text("dict")["blocks"]
                if block["type"] == 0
                for line in block["lines"]
                for span in line["spans"]
            ]
        })

    return all_results

@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file received (request.files is empty)"}), 400

    file = request.files["file"]
    try:
        results = extract_images_with_context(file.read())
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
