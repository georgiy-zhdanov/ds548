from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    questions = db.relationship('Question', backref='author', lazy=True)
    answers = db.relationship('Answer', backref='author', lazy=True)
    articles = db.relationship('Article', backref='author', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    answers = db.relationship('Answer', backref='question', lazy=True, cascade='all, delete-orphan')

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))  # Место проведения
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)  # Одобрено админом
    is_rejected = db.Column(db.Boolean, default=False)  # Отклонено админом
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='events')
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    difficulty = db.Column(db.String(20), default='medium')
    solution = db.Column(db.Text)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    questions_data = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='tests')

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='folders')
    parent = db.relationship('Folder', remote_side=[id], backref='subfolders')
    files = db.relationship('File', backref='folder', lazy=True, cascade='all, delete-orphan')

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)  # UUID-имя на диске
    file_path = db.Column(db.String(500), nullable=False)    # Путь на диске
    size = db.Column(db.Integer, nullable=False)             # Размер в байтах
    mime_type = db.Column(db.String(100))
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='files')

# ============================================
# МОДЕЛИ ДЛЯ КОНТЕСТОВ
# ============================================

class Contest(db.Model):
    """Соревнование/контест"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='contests')
    problems = db.relationship('Problem', backref='contest', lazy=True, cascade='all, delete-orphan')
    participants = db.relationship('ContestParticipant', backref='contest', lazy=True, cascade='all, delete-orphan')

class ContestParticipant(db.Model):
    """Участник контеста"""
    id = db.Column(db.Integer, primary_key=True)
    contest_id = db.Column(db.Integer, db.ForeignKey('contest.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer, default=0)
    
    __table_args__ = (db.UniqueConstraint('contest_id', 'user_id'),)
    
    user = db.relationship('User', backref='contest_participations')

class Problem(db.Model):
    """Задача в контесте"""
    id = db.Column(db.Integer, primary_key=True)
    contest_id = db.Column(db.Integer, db.ForeignKey('contest.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    problem_type = db.Column(db.String(20), nullable=False)  # 'code', 'math', 'csv'
    difficulty = db.Column(db.String(20), default='medium')  # 'easy', 'medium', 'hard'
    max_score = db.Column(db.Integer, default=100)
    time_limit = db.Column(db.Integer, default=2)  # секунды (для code)
    memory_limit = db.Column(db.Integer, default=256)  # МБ (для code)

    solution_path = db.Column(db.String(500))  # Путь к эталонному CSV
    test_data_path = db.Column(db.String(500))  # Путь к тестовым данным (для скачивания участниками)
    

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tests = db.relationship('ProblemTest', backref='problem', lazy=True, cascade='all, delete-orphan')
    questions = db.relationship('MathQuestion', backref='problem', lazy=True, cascade='all, delete-orphan')
    submissions = db.relationship('Submission', backref='problem', lazy=True, cascade='all, delete-orphan')

class ProblemTest(db.Model):
    """Тесты для code-задач (формат Polygon/Codeforces)"""
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=False)
    expected_output = db.Column(db.Text, nullable=False)
    is_sample = db.Column(db.Boolean, default=False)  # Пример теста (виден участникам)
    order_num = db.Column(db.Integer, default=0)

class MathQuestion(db.Model):
    """Вопросы для math-задач"""
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text)  # JSON: ["вариант1", "вариант2", ...]
    correct_answer = db.Column(db.String(200), nullable=False)  # Для числовых ответов
    correct_option = db.Column(db.Integer)  # Для вопросов с вариантами (0, 1, 2, ...)
    points = db.Column(db.Integer, default=10)
    order_num = db.Column(db.Integer, default=0)

class Submission(db.Model):
    """Отправка решения"""
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contest_id = db.Column(db.Integer, db.ForeignKey('contest.id'), nullable=False)
    submission_type = db.Column(db.String(20), nullable=False)  # 'code', 'math', 'csv'
    
    # Для code
    code = db.Column(db.Text)
    language = db.Column(db.String(20), default='python')
    
    # Для math
    answers = db.Column(db.Text)  # JSON: {"question_id": answer, ...}
    
    # Для csv
    csv_filename = db.Column(db.String(255))
    csv_path = db.Column(db.String(500))
    
    # Результат проверки
    status = db.Column(db.String(50), default='pending')  # 'pending', 'accepted', 'wrong_answer', 'error', 'partial'
    score = db.Column(db.Integer, default=0)
    details = db.Column(db.Text)  # JSON с деталями проверки
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='submissions')
