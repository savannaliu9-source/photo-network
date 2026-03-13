import os
import json
import uuid
import base64
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DATA_FILE = 'data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'networks': {}, 'images': {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/network', methods=['POST'])
def create_network():
    data = request.json
    network_id = str(uuid.uuid4())[:8]
    
    db = load_data()
    db['networks'][network_id] = {
        'name': data.get('name', 'My Photo Network'),
        'image_ids': []
    }
    save_data(db)
    
    return jsonify({'network_id': network_id})

@app.route('/api/network/<network_id>')
def get_network(network_id):
    db = load_data()
    network = db['networks'].get(network_id)
    
    if not network:
        return jsonify({'error': 'Network not found'}), 404
    
    images = []
    for img_id in network['image_ids']:
        if img_id in db['images']:
            images.append({
                'id': img_id,
                'data': db['images'][img_id]
            })
    
    return jsonify({'name': network['name'], 'nodes': images})

@app.route('/api/upload', methods=['POST'])
def upload_images():
    network_id = request.form.get('network_id')
    files = request.files.getlist('images')
    
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    uploaded = []
    db = load_data()
    
    for file in files:
        if file and allowed_file(file.filename):
            img_id = str(uuid.uuid4())[:8]
            img_data = base64.b64encode(file.read()).decode('utf-8')
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
            mime_type = f'image/{ext}'
            if ext == 'jpg':
                mime_type = 'image/jpeg'
            
            db['images'][img_id] = f'data:{mime_type};base64,{img_data}'
            db['networks'][network_id]['image_ids'].append(img_id)
            uploaded.append({'id': img_id, 'filename': file.filename})
    
    save_data(db)
    return jsonify({'uploaded': uploaded})

@app.route('/api/image/<img_id>')
def get_image(img_id):
    db = load_data()
    img = db['images'].get(img_id)
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    return jsonify({'data': img})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
