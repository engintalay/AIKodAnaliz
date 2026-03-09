from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import sys

# Disable proxy usage inside application process
for _proxy_var in [
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy'
]:
    os.environ.pop(_proxy_var, None)
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import DATABASE_PATH, UPLOAD_DIR
from backend.database import db
from backend.routes import project, analysis, user, ai_settings, diagram, report
from backend.logger import logger

# Setup Flask app with static and template folders
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(FRONTEND_DIR, '')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

app = Flask(__name__, 
    static_folder=os.path.join(FRONTEND_DIR, ''),
    static_url_path='/static',
    template_folder=FRONTEND_DIR)

# Configure session
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = 7 * 24 * 3600  # 7 days

CORS(app)

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

logger.info("="*60)
logger.info("AIKodAnaliz Backend Starting...")
logger.info(f"Upload directory: {UPLOAD_DIR}")
logger.info(f"Logs directory: {LOGS_DIR}")
logger.info(f"Database: {DATABASE_PATH}")

# Check analyzer status
try:
    from backend.analyzers.advanced_analyzer import TREE_SITTER_REQUIRED
    if TREE_SITTER_REQUIRED:
        logger.info("✓ Tree-Sitter analyzer: AVAILABLE")
    else:
        logger.warning("⚠ Tree-Sitter analyzer: NOT AVAILABLE")
except Exception as e:
    logger.warning(f"⚠ Tree-Sitter check failed: {e}")

logger.info("="*60)

# Register blueprints
app.register_blueprint(project.bp)
app.register_blueprint(analysis.bp)
app.register_blueprint(user.bp)
app.register_blueprint(ai_settings.bp)
app.register_blueprint(diagram.bp)
app.register_blueprint(report.bp)

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/test')
def test_dashboard():
    return send_from_directory(FRONTEND_DIR, 'test-dashboard.html')

@app.route('/static/css/<path:filename>')
def send_css(filename):
    from flask import make_response
    response = make_response(send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/static/js/<path:filename>')
def send_js(filename):
    from flask import make_response
    response = make_response(send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'database': 'connected' if os.path.exists(DATABASE_PATH) else 'not connected'
    })

@app.route('/api/heartbeat', methods=['GET', 'POST'])
def heartbeat():
    # Frontend veya harici servislerin uygulamanın ayakta olup olmadığını kontrol ettiği endpoint
    return jsonify({'status': 'alive'})

@app.route('/.well-known/assetlinks.json')
def assetlinks():
    # Android App Links veya Google tarayıcılarının doğrulama isteklerini karşılamak için (404 hatasını önler)
    return jsonify([])

if __name__ == '__main__':
    # Threaded mode keeps UI/API responsive while long AI requests are running.
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
