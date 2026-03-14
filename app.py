import os
import uuid
import base64
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_FILE = 'photo_network.db'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS networks
                 (id TEXT PRIMARY KEY, name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS images
                 (id TEXT PRIMARY KEY, network_id TEXT, data TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stickers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, x REAL, y REAL, size REAL)''')
    conn.commit()
    conn.close()

init_db()

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
    
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO networks (id, name) VALUES (?, ?)',
              (network_id, data.get('name', 'My Photo Network')))
    conn.commit()
    conn.close()
    
    return jsonify({'network_id': network_id})

@app.route('/api/network/<network_id>')
def get_network(network_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT name FROM networks WHERE id = ?', (network_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Network not found'}), 404
    
    c.execute('SELECT id, data FROM images WHERE network_id = ?', (network_id,))
    images = [{'id': row['id'], 'data': row['data']} for row in c.fetchall()]
    conn.close()
    
    return jsonify({'name': row['name'], 'nodes': images})

@app.route('/api/upload', methods=['POST'])
def upload_images():
    network_id = request.form.get('network_id')
    files = request.files.getlist('images')
    
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    uploaded = []
    conn = get_db()
    c = conn.cursor()
    
    for file in files:
        if file and allowed_file(file.filename):
            img_id = str(uuid.uuid4())[:8]
            img_data = base64.b64encode(file.read()).decode('utf-8')
            ext = get_ext(file.filename)
            mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            
            c.execute('INSERT INTO images (id, network_id, data) VALUES (?, ?, ?)',
                      (img_id, network_id, f'data:{mime_type};base64,{img_data}'))
            uploaded.append({'id': img_id, 'filename': file.filename})
    
    conn.commit()
    conn.close()
    return jsonify({'uploaded': uploaded})

@app.route('/api/stickers')
def get_stickers():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT data, x, y, size FROM stickers')
    stickers = []
    for row in c.fetchall():
        stickers.append({
            'src': row['data'],
            'x': row['x'] if row['x'] else 50,
            'y': row['y'] if row['y'] else 50,
            'size': row['size'] if row['size'] else 55
        })
    conn.close()
    return jsonify({'stickers': stickers})

import random

@app.route('/api/sticker', methods=['POST'])
def upload_sticker():
    files = request.files.getlist('stickers')
    
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    for file in files:
        if file and allowed_file(file.filename):
            img_data = base64.b64encode(file.read()).decode('utf-8')
            ext = get_ext(file.filename)
            mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            
            x = 5 + random.random() * 85
            y = 5 + random.random() * 85
            size = 60 + random.random() * 30
            
            c.execute('INSERT INTO stickers (data, x, y, size) VALUES (?, ?, ?, ?)',
                      (f'data:{mime_type};base64,{img_data}', x, y, size))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/stickers', methods=['POST'])
def save_stickers():
    data = request.json
    stickers = data.get('stickers', [])
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('DELETE FROM stickers')
    
    for sticker in stickers:
        if isinstance(sticker, dict):
            c.execute('INSERT INTO stickers (data, x, y, size) VALUES (?, ?, ?, ?)',
                      (sticker.get('src', ''), sticker.get('x', 50), sticker.get('y', 50), sticker.get('size', 55)))
        else:
            c.execute('INSERT INTO stickers (data, x, y, size) VALUES (?, ?, ?, ?)',
                      (sticker, 50, 50, 55))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/image/<img_id>')
def get_image(img_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT data FROM images WHERE id = ?', (img_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Image not found'}), 404
    return jsonify({'data': row['data']})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

@app.route('/api/share', methods=['POST'])
def share_to_gist():
    if not GITHUB_TOKEN:
        return jsonify({'error': 'Share feature not configured'}), 500
    
    data = request.json
    html_content = data.get('content', '')
    
    if not html_content:
        return jsonify({'error': 'No content'}), 400
    
    gist_data = {
        'description': 'Time Capsule - Photo Network',
        'public': True,
        'files': {
            'time-capsule.html': {
                'content': html_content
            }
        }
    }
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    resp = requests.post('https://api.github.com/gists', json=gist_data, headers=headers)
    
    if resp.status_code == 201:
        result = resp.json()
        gist_id = result.get('id')
        raw_url = f'https://gist.githubusercontent.com/savannaliu9-source/{gist_id}/raw/time-capsule.html'
        view_url = f'https://htmlpreview.github.io/?{raw_url}'
        return jsonify({'url': view_url, 'raw_url': raw_url})
    else:
        return jsonify({'error': 'Failed to create gist'}), 500
