"""Merkezi yapılandırma modülü.

.env dosyasından değerleri yükler; .env yoksa mevcut default'lar kullanılır.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyası proje kökünde aranır
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env')

# ---- Yollar ----
DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'aikodanaliz.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

# ---- Flask ----
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# ---- LM Studio ----
_lm_host = os.getenv('LMSTUDIO_HOST', 'localhost')
_lm_port = os.getenv('LMSTUDIO_PORT', '1234')
# LMSTUDIO_API_URL manuel belirtilmişse onu kullan; yoksa host+port'tan oluştur
LMSTUDIO_API_URL = os.getenv('LMSTUDIO_API_URL', f'http://{_lm_host}:{_lm_port}/v1')
LMSTUDIO_DEFAULT_MODEL = os.getenv('LMSTUDIO_DEFAULT_MODEL', 'local-model')
LMSTUDIO_MAX_TOKENS = int(os.getenv('LMSTUDIO_MAX_TOKENS', '1000'))
LMSTUDIO_TEMPERATURE = float(os.getenv('LMSTUDIO_TEMPERATURE', '0.7'))
LMSTUDIO_TOP_P = float(os.getenv('LMSTUDIO_TOP_P', '0.9'))

# ---- Veritabanı ----
DB_CONNECTION_TYPE = os.getenv('DB_CONNECTION_TYPE', 'sqlite')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'aikodanaliz')
DB_USER = os.getenv('DB_USER', 'admin')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# ---- Admin ----
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# ---- Proje Limitleri ----
SUPPORTED_LANGUAGES = ['java', 'python', 'javascript', 'typescript', 'php',
                       'css', 'html', 'go', 'rust', 'c', 'cpp']
MAX_PROJECT_SIZE_MB = int(os.getenv('MAX_PROJECT_SIZE_MB', '100'))
CONTEXT_LIMIT_TOKENS = int(os.getenv('CONTEXT_LIMIT_TOKENS', '4000'))
