import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ds548-secret-key-change-me'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///ds548.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки загрузки файлов
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'tasks')
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # Максимум 32 МБ на файл
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', '7z', 
                          'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'xls', 'csv', 'py', 'ipynb'}