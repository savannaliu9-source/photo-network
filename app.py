import os
import uuid
import base64
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

SUPABASE_URL = 'https://zjgkohdajelhuyevksho.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpqZ2tvaGRhamVsaHV5ZXZrc2hvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0NzQ0ODIsImV4cCI6MjA4OTA1MDQ4Mn0.WcD8Alx5BJOM8UEIE_4dry_df9sKQ00pfc52sGiYQwU'
BUCKET_NAME = 'photos'

def get_db():
    import psycopg
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://photo_network_user:56zWIQKw4MCNJ7wJirU9RgDwSrghIoGp@dpg-d6qhetvgi27c73a3cos0-a/photo_network')
    conn = psycopg.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS networks
                 (id TEXT PRIMARY KEY, name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS images
                 (id TEXT PRIMARY KEY, network_id TEXT, data TEXT, supabase_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stickers
                 (id SERIAL PRIMARY KEY, data TEXT, x REAL, y REAL, size REAL)''')
    conn.commit()
    conn.close()

try:
    init_db()
except:
    pass

def get_ext(filename):
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return 'png'

def allowed_file(filename):
    ext = get_ext(filename)
    return ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def upload_to_supabase(file_data, filename, content_type):
    headers = {
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': content_type,
        'x-upsert': 'true'
    }
    file_path = f'{uuid.uuid4()}_{filename}'
    url = f'{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{file_path}'
    resp = requests.post(url, headers=headers, data=file_data)
    if resp.status_code in [200, 201]:
        return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{file_path}'
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/network', methods=['POST'])
def create_network():
    data = request.json
    network_id = str(uuid.uuid4())[:8]
    
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO networks (id, name) VALUES (%s, %s)',
              (network_id, data.get('name', 'My Photo Network')))
    conn.commit()
    conn.close()
    
    return jsonify({'network_id': network_id})

@app.route('/api/network/<network_id>')
def get_network(network_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT name FROM networks WHERE id = %s', (network_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Network not found'}), 404
    
    c.execute('SELECT id, data, supabase_url FROM images WHERE network_id = %s', (network_id,))
    images = []
    for r in c.fetchall():
        img_data = r[1]
        if r[2]:
            img_data = r[2]
        images.append({'id': r[0], 'data': img_data})
    conn.close()
    
    return jsonify({'name': row[0], 'nodes': images})

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
            file_content = file.read()
            ext = get_ext(file.filename)
            mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            
            supabase_url = upload_to_supabase(file_content, file.filename, mime_type)
            
            if supabase_url:
                c.execute('INSERT INTO images (id, network_id, supabase_url) VALUES (%s, %s, %s)',
                          (img_id, network_id, supabase_url))
                uploaded.append({'id': img_id, 'filename': file.filename, 'data': supabase_url})
            else:
                img_data = base64.b64encode(file_content).decode('utf-8')
                c.execute('INSERT INTO images (id, network_id, data) VALUES (%s, %s, %s)',
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
            'src': row[0],
            'x': row[1] if row[1] else 50,
            'y': row[2] if row[2] else 50,
            'size': row[3] if row[3] else 55
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
            
            c.execute('INSERT INTO stickers (data, x, y, size) VALUES (%s, %s, %s, %s)',
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
            c.execute('INSERT INTO stickers (data, x, y, size) VALUES (%s, %s, %s, %s)',
                      (sticker.get('src', ''), sticker.get('x', 50), sticker.get('y', 50), sticker.get('size', 55)))
        else:
            c.execute('INSERT INTO stickers (data, x, y, size) VALUES (%s, %s, %s, %s)',
                      (sticker, 50, 50, 55))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/image/<img_id>')
def get_image(img_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT data, supabase_url FROM images WHERE id = %s', (img_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Image not found'}), 404
    
    img_data = row[0] if row[0] else row[1]
    return jsonify({'data': img_data})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
