import os
from flask import Flask, request, render_template_string

app = Flask(__name__)

UPLOAD_FOLDER = '/app/certs'
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
    except PermissionError:
        # Fallback to current directory for local testing
        UPLOAD_FOLDER = os.path.join(os.getcwd(), 'certs')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!doctype html>
<title>Upload Certificate</title>
<h1>Upload .pfx Certificate</h1>
<form method=post enctype=multipart/form-data action="/upload">
  <input type=file name=file>
  <input type=submit value=Upload>
</form>
"""

@app.route('/', methods=['GET'])
def index():
    return HTML_TEMPLATE

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return f'File successfully uploaded to {filepath}'

if __name__ == '__main__':
    # Listen on all interfaces to be accessible
    app.run(host='0.0.0.0', port=8080)
