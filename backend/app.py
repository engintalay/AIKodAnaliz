from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import DATABASE_PATH, UPLOAD_DIR
from backend.database import db
from backend.routes import project, analysis, user, ai_settings, diagram

# Setup Flask app with static and template folders
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(FRONTEND_DIR, '')

app = Flask(__name__, 
    static_folder=os.path.join(FRONTEND_DIR, ''),
    static_url_path='/static',
    template_folder=FRONTEND_DIR)

CORS(app)

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Register blueprints
app.register_blueprint(project.bp)
app.register_blueprint(analysis.bp)
app.register_blueprint(user.bp)
app.register_blueprint(ai_settings.bp)
app.register_blueprint(diagram.bp)

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/static/css/<path:filename>')
def send_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)

@app.route('/static/js/<path:filename>')
def send_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'database': 'connected' if os.path.exists(DATABASE_PATH) else 'not connected'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
