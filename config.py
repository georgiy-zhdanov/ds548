import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-me-in-render-env'
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///ds548.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'tasks')
    CONTEST_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'contests')
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', '7z', 
                          'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'xls', 'csv', 'py', 'ipynb'}