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
    return {'networks': {}, 'images': {}, 'stickers': {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_ext(filename):
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return 'png'

def allowed_file(filename):
    ext = get_ext(filename)
    return ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

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
    for img_id in network.get('image_ids', []):
        if img_id in db['images']:
            images.append({
                'id': img_id,
                'data': db['images'][img_id]
            })
    
    return jsonify({'name': network.get('name', 'My Photo Network'), 'nodes': images})

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
            ext = get_ext(file.filename)
            mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            
            db['images'][img_id] = f'data:{mime_type};base64,{img_data}'
            if network_id in db['networks']:
                db['networks'][network_id]['image_ids'].append(img_id)
            uploaded.append({'id': img_id, 'filename': file.filename})
    
    save_data(db)
    return jsonify({'uploaded': uploaded})

@app.route('/api/stickers')
def get_stickers():
    db = load_data()
    stickers = list(db.get('stickers', {}).values())
    return jsonify({'stickers': stickers})

@app.route('/api/sticker', methods=['POST'])
def upload_sticker():
    files = request.files.getlist('stickers')
    
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    db = load_data()
    
    existing_stickers = db.get('stickers', {})
    new_stickers = {}
    
    idx = len(existing_stickers)
    for file in files:
        if file and allowed_file(file.filename):
            sticker_id = str(uuid.uuid4())[:8]
            img_data = base64.b64encode(file.read()).decode('utf-8')
            ext = get_ext(file.filename)
            mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            
            new_stickers[str(idx)] = f'data:{mime_type};base64,{img_data}'
            idx += 1
    
    all_stickers = {**existing_stickers, **new_stickers}
    db['stickers'] = all_stickers
    save_data(db)
    
    return jsonify({'stickers': list(all_stickers.values())})

@app.route('/api/stickers', methods=['POST'])
def save_stickers():
    data = request.json
    stickers = data.get('stickers', [])
    db = load_data()
    db['stickers'] = {str(i): s for i, s in enumerate(stickers)}
    save_data(db)
    return jsonify({'success': True})

@app.route('/api/image/<img_id>')
def get_image(img_id):
    db = load_data()
    img = db['images'].get(img_id)
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    return jsonify({'data': img})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
