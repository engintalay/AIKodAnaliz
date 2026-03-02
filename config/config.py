import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'aikodanaliz.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

# LMStudio Configuration
LMSTUDIO_API_URL = "http://localhost:1234/v1"
LMSTUDIO_DEFAULT_MODEL = "local-model"
LMSTUDIO_MAX_TOKENS = 1000
LMSTUDIO_TEMPERATURE = 0.7
LMSTUDIO_TOP_P = 0.9

# Database Configuration
DB_CONNECTION_TYPE = "sqlite"  # "sqlite" or "postgresql"
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "aikodanaliz"
DB_USER = "admin"
DB_PASSWORD = ""

# Application Settings
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # TODO: Change in production
SUPPORTED_LANGUAGES = ["java", "python", "javascript", "typescript", "php", "css", "html", "go", "rust", "c", "cpp"]
MAX_PROJECT_SIZE_MB = 100
CONTEXT_LIMIT_TOKENS = 4000
