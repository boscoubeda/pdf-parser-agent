from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import base64
from io import BytesIO

app = Flask(__name__)

@app.route('/parse', methods=['POST'])
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file received (request.files is empty)"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        result = []

        for page_index in range(len(doc)):
            page = doc[page_index]
            text_lines = []
            blocks = page.get_text("dict")['blocks']
            for b in blocks:
                if b['type'] == 0:
                    for l in b['lines']:
                        line_text = " ".join([s['text'] for s in l['spans']])
                        text_lines.append({
                            "text": line_text,
                            "y": l['bbox'][1]
                        })

            image_list = []
            try:
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        y_pos = 0

                        # Intentar estimar posición y
                        for b in blocks:
                            if b['type'] == 1 and b['image'] == xref:
                                y_pos = b['bbox'][1]

                        image_list.append({
                            "image_base64": image_base64,
                            "index": img_index + 1,
                            "page": page_index + 1,
                            "y": y_pos
                        })
                    except Exception as e:
                        print(f"Error processing image on page {page_index + 1}: {e}")
                        continue
            except Exception as e:
                print(f"Failed to get images from page {page_index + 1}: {e}")

            result.append({
                "page": page_index + 1,
                "text_lines": text_lines,
                "images": image_list
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
