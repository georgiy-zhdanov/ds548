from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Question, Answer, Event, Task, Test, Article, Folder, File
from forms import (RegisterForm, LoginForm, QuestionForm, AnswerForm, 
                   TestForm, ArticleForm, FolderForm, FileUploadForm, EventForm)
import json
import os
import uuid
import mimetypes
from werkzeug.utils import secure_filename, send_from_directory

import pandas as pd
import numpy as np

from models import (db, User, Question, Answer, Event, Task, Test, Article, 
                    Folder, File, Contest, ContestParticipant, Problem, 
                    ProblemTest, MathQuestion, Submission)
from forms import (RegisterForm, LoginForm, QuestionForm, AnswerForm, 
                   TestForm, ArticleForm, FolderForm, FileUploadForm, EventForm,
                   ContestForm, ProblemForm, CodeSubmissionForm, CSVSubmissionForm)

import subprocess
import tempfile

from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.template_filter('from_json')
def from_json_filter(s):
    """Фильтр для парсинга JSON в шаблонах"""
    import json
    try:
        return json.loads(s)
    except:
        return {}

# ============================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================

@app.route('/')
def index():
    # АВТО-ВХОД: Если база пустая, создаем админа и сразу входим под ним
    if User.query.count() == 0:
        admin = User(username='admin', email='admin@ds548.ru', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        login_user(admin)
        flash('Добро пожаловать! Вы автоматически вошли как администратор (admin / admin123).', 'success')
    
    events = Event.query.filter_by(is_approved=True).order_by(Event.event_date.desc()).limit(5).all()
    return render_template('index.html', events=events)

# ============================================
# АУТЕНТИФИКАЦИЯ
# ============================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=form.email.data).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Войдите в аккаунт.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверное имя пользователя или пароль', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    articles = Article.query.filter_by(author_id=current_user.id).order_by(Article.updated_at.desc()).all()
    tests = Test.query.filter_by(author_id=current_user.id).order_by(Test.created_at.desc()).all()
    return render_template('profile.html', articles=articles, tests=tests)

# ============================================
# STACK OVERFLOW
# ============================================

@app.route('/stackoverflow')
def stackoverflow():
    questions = Question.query.order_by(Question.created_at.desc()).all()
    return render_template('stackoverflow.html', questions=questions)

@app.route('/stackoverflow/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    form = QuestionForm()
    if form.validate_on_submit():
        q = Question(title=form.title.data, content=form.content.data, author_id=current_user.id)
        db.session.add(q)
        db.session.commit()
        flash('Вопрос создан!', 'success')
        return redirect(url_for('stackoverflow'))
    return render_template('ask_question.html', form=form)

@app.route('/stackoverflow/<int:qid>', methods=['GET', 'POST'])
def question_detail(qid):
    q = Question.query.get_or_404(qid)
    form = AnswerForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Войдите, чтобы отвечать', 'warning')
            return redirect(url_for('login'))
        a = Answer(content=form.content.data, author_id=current_user.id, question_id=qid)
        db.session.add(a)
        db.session.commit()
        flash('Ответ добавлен!', 'success')
        return redirect(url_for('question_detail', qid=qid))
    return render_template('question_detail.html', question=q, form=form)

# ============================================
# МЕРОПРИЯТИЯ (С МОДЕРАЦИЕЙ)
# ============================================

@app.route('/events')
def events():
    # Показываем только одобренные мероприятия
    approved_events = Event.query.filter_by(is_approved=True).order_by(Event.event_date.desc()).all()
    return render_template('events.html', events=approved_events)

@app.route('/events/propose', methods=['GET', 'POST'])
@login_required
def propose_event():
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            title=form.title.data,
            description=form.description.data,
            event_date=form.event_date.data,
            location=form.location.data,
            author_id=current_user.id,
            is_approved=False,
            is_rejected=False
        )
        db.session.add(event)
        db.session.commit()
        flash('Ваше мероприятие предложено и ожидает одобрения администратора!', 'success')
        return redirect(url_for('profile'))
    return render_template('propose_event.html', form=form)

@app.route('/events/my')
@login_required
def my_events():
    my_events = Event.query.filter_by(author_id=current_user.id).order_by(Event.created_at.desc()).all()
    return render_template('my_events.html', events=my_events)

# ============================================
# ДОКУМЕНТАЦИЯ (СТАТЬИ)
# ============================================

@app.route('/docs')
def docs():
    articles = Article.query.order_by(Article.updated_at.desc()).all()
    return render_template('docs.html', articles=articles)

# ============================================
# ЗАДАНИЯ ПРОШЛЫХ ЛЕТ (ФАЙЛОВОЕ ХРАНИЛИЩЕ)
# ============================================

def get_breadcrumbs(folder):
    breadcrumbs = []
    current = folder
    while current:
        breadcrumbs.insert(0, current)
        current = current.parent
    return breadcrumbs

@app.route('/tasks')
@app.route('/tasks/folder/<int:fid>')
def tasks_view(fid=None):
    if fid:
        folder = Folder.query.get_or_404(fid)
        breadcrumbs = get_breadcrumbs(folder)
    else:
        folder = None
        breadcrumbs = []
    
    subfolders = Folder.query.filter_by(parent_id=fid).order_by(Folder.name).all()
    files = File.query.filter_by(folder_id=fid).order_by(File.original_name).all()
    all_folders = Folder.query.order_by(Folder.name).all()
    
    upload_form = FileUploadForm()
    folder_form = FolderForm()
    
    return render_template('tasks.html', 
                           folder=folder,
                           breadcrumbs=breadcrumbs,
                           subfolders=subfolders,
                           files=files,
                           all_folders=all_folders,
                           upload_form=upload_form,
                           folder_form=folder_form)

@app.route('/tasks/folder/new', methods=['POST'])
@login_required
def create_folder():
    form = FolderForm()
    parent_id = request.form.get('parent', type=int)
    
    if parent_id:
        Folder.query.get_or_404(parent_id)
    
    new_folder = Folder(
        name=secure_filename(form.name.data) or form.name.data.strip(),
        parent_id=parent_id,
        author_id=current_user.id
    )
    db.session.add(new_folder)
    db.session.commit()
    
    flash(f'Папка "{new_folder.name}" создана', 'success')
    return redirect(url_for('tasks_view', fid=parent_id))

@app.route('/tasks/upload', methods=['POST'])
@login_required
def upload_file():
    form = FileUploadForm()
    folder_id = request.form.get('folder', type=int)
    
    if folder_id:
        Folder.query.get_or_404(folder_id)
    
    if form.validate_on_submit():
        file = form.file.data
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        file.save(file_path)
        
        mime_type, _ = mimetypes.guess_type(file.filename)
        
        new_file = File(
            original_name=secure_filename(file.filename) or file.filename,
            stored_name=stored_name,
            file_path=file_path,
            size=os.path.getsize(file_path),
            mime_type=mime_type or 'application/octet-stream',
            folder_id=folder_id,
            author_id=current_user.id
        )
        db.session.add(new_file)
        db.session.commit()
        
        flash(f'Файл "{new_file.original_name}" загружен', 'success')
        return redirect(url_for('tasks_view', fid=folder_id))
    
    flash('Ошибка загрузки файла', 'danger')
    return redirect(url_for('tasks_view', fid=folder_id))

@app.route('/tasks/file/<int:file_id>/download')
def download_file(file_id):
    file = File.query.get_or_404(file_id)
    
    upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
    file_dir = os.path.abspath(os.path.dirname(file.file_path))
    if not file_dir.startswith(upload_dir):
        flash('Ошибка безопасности', 'danger')
        return redirect(url_for('tasks_view'))
    
    return send_from_directory(
        upload_dir,
        file.stored_name,
        as_attachment=True,
        download_name=file.original_name
    )

@app.route('/tasks/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    if file.author_id != current_user.id and not current_user.is_admin:
        flash('Вы можете удалять только свои файлы', 'danger')
        return redirect(url_for('tasks_view', fid=file.folder_id))
    
    if os.path.exists(file.file_path):
        os.remove(file.file_path)
    
    folder_id = file.folder_id
    db.session.delete(file)
    db.session.commit()
    
    flash('Файл удалён', 'success')
    return redirect(url_for('tasks_view', fid=folder_id))

@app.route('/tasks/folder/<int:fid>/delete', methods=['POST'])
@login_required
def delete_folder(fid):
    folder = Folder.query.get_or_404(fid)
    if folder.author_id != current_user.id and not current_user.is_admin:
        flash('Вы можете удалять только свои папки', 'danger')
        return redirect(url_for('tasks_view', fid=folder.parent_id))
    
    for file in folder.files:
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
    
    parent_id = folder.parent_id
    db.session.delete(folder)
    db.session.commit()
    
    flash('Папка удалена', 'success')
    return redirect(url_for('tasks_view', fid=parent_id))

# ============================================
# ТЕСТЫ
# ============================================

@app.route('/tests')
def tests():
    all_tests = Test.query.order_by(Test.created_at.desc()).all()
    return render_template('tests.html', tests=all_tests)

@app.route('/tests/new', methods=['GET', 'POST'])
@login_required
def create_test():
    form = TestForm()
    if form.validate_on_submit():
        try:
            json.loads(form.questions_data.data)
        except json.JSONDecodeError:
            flash('Ошибка: Вопросы должны быть в корректном формате JSON', 'danger')
            return render_template('test_form.html', form=form, title='Создать тест')
            
        test = Test(
            title=form.title.data,
            description=form.description.data,
            questions_data=form.questions_data.data,
            author_id=current_user.id
        )
        db.session.add(test)
        db.session.commit()
        flash('Тест успешно создан и доступен всем!', 'success')
        return redirect(url_for('tests'))
    return render_template('test_form.html', form=form, title='Создать тест')

@app.route('/tests/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
def edit_test(tid):
    test = Test.query.get_or_404(tid)
    if test.author_id != current_user.id and not current_user.is_admin:
        flash('Вы можете редактировать только свои тесты', 'danger')
        return redirect(url_for('tests'))
        
    form = TestForm(obj=test)
    if form.validate_on_submit():
        test.title = form.title.data
        test.description = form.description.data
        test.questions_data = form.questions_data.data
        db.session.commit()
        flash('Тест обновлён', 'success')
        return redirect(url_for('tests'))
    return render_template('test_form.html', form=form, title='Редактировать тест')

@app.route('/tests/<int:tid>/delete', methods=['POST'])
@login_required
def delete_test(tid):
    test = Test.query.get_or_404(tid)
    if test.author_id != current_user.id and not current_user.is_admin:
        flash('Вы можете удалять только свои тесты', 'danger')
        return redirect(url_for('tests'))
        
    db.session.delete(test)
    db.session.commit()
    flash('Тест удалён', 'success')
    return redirect(url_for('tests'))

@app.route('/tests/<int:tid>')
def take_test(tid):
    t = Test.query.get_or_404(tid)
    try:
        questions = json.loads(t.questions_data)
    except:
        questions = []
    return render_template('take_test.html', test=t, questions=questions)

# ============================================
# СТАТЬИ
# ============================================

@app.route('/article/new', methods=['GET', 'POST'])
@login_required
def create_article():
    form = ArticleForm()
    if form.validate_on_submit():
        article = Article(
            title=form.title.data,
            content=form.content.data,
            author_id=current_user.id
        )
        db.session.add(article)
        db.session.commit()
        flash('Статья создана', 'success')
        return redirect(url_for('view_article', aid=article.id))
    return render_template('article_form.html', form=form, title='Создать статью')

@app.route('/article/<int:aid>')
def view_article(aid):
    article = Article.query.get_or_404(aid)
    return render_template('article_view.html', article=article)

@app.route('/article/<int:aid>/edit', methods=['GET', 'POST'])
@login_required
def edit_article(aid):
    article = Article.query.get_or_404(aid)
    if article.author_id != current_user.id and not current_user.is_admin:
        flash('Вы можете редактировать только свои статьи', 'danger')
        return redirect(url_for('view_article', aid=aid))
    form = ArticleForm(obj=article)
    if form.validate_on_submit():
        article.title = form.title.data
        article.content = form.content.data
        db.session.commit()
        flash('Статья обновлена', 'success')
        return redirect(url_for('view_article', aid=aid))
    return render_template('article_form.html', form=form, title='Редактировать статью')

@app.route('/article/<int:aid>/delete', methods=['POST'])
@login_required
def delete_article(aid):
    article = Article.query.get_or_404(aid)
    if article.author_id != current_user.id and not current_user.is_admin:
        flash('Вы можете удалять только свои статьи', 'danger')
        return redirect(url_for('view_article', aid=aid))
    db.session.delete(article)
    db.session.commit()
    flash('Статья удалена', 'success')
    return redirect(url_for('profile'))

# ============================================
# API ДЛЯ INLINE-РЕДАКТИРОВАНИЯ СТАТЕЙ
# ============================================

@app.route('/api/article/<int:aid>/save', methods=['POST'])
@login_required
def api_save_article(aid):
    article = Article.query.get_or_404(aid)
    if article.author_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Нет прав'}), 403
    
    data = request.get_json()
    article.title = data.get('title', article.title)
    article.content = data.get('content', article.content)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'title': article.title,
        'content': article.content,
        'updated_at': article.updated_at.strftime('%d.%m.%Y %H:%M')
    })

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    users_count = User.query.count()
    articles_count = Article.query.count()
    tests_count = Test.query.count()
    questions_count = Question.query.count()
    pending_events_count = Event.query.filter_by(is_approved=False, is_rejected=False).count()
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    return render_template('admin.html', 
                           users_count=users_count,
                           articles_count=articles_count,
                           tests_count=tests_count,
                           questions_count=questions_count,
                           pending_events_count=pending_events_count,
                           users=users)

@app.route('/admin/events')
@login_required
def admin_events():
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    pending_events = Event.query.filter_by(is_approved=False, is_rejected=False).order_by(Event.created_at.desc()).all()
    approved_events = Event.query.filter_by(is_approved=True).order_by(Event.event_date.desc()).all()
    rejected_events = Event.query.filter_by(is_rejected=True).order_by(Event.created_at.desc()).all()
    
    return render_template('admin_events.html', 
                           pending_events=pending_events,
                           approved_events=approved_events,
                           rejected_events=rejected_events)

@app.route('/admin/events/<int:eid>/approve', methods=['POST'])
@login_required
def approve_event(eid):
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    event = Event.query.get_or_404(eid)
    event.is_approved = True
    event.is_rejected = False
    db.session.commit()
    flash(f'Мероприятие "{event.title}" одобрено!', 'success')
    return redirect(url_for('admin_events'))

@app.route('/admin/events/<int:eid>/reject', methods=['POST'])
@login_required
def reject_event(eid):
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    event = Event.query.get_or_404(eid)
    event.is_approved = False
    event.is_rejected = True
    db.session.commit()
    flash(f'Мероприятие "{event.title}" отклонено', 'warning')
    return redirect(url_for('admin_events'))

@app.route('/admin/events/<int:eid>/delete', methods=['POST'])
@login_required
def delete_event(eid):
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    event = Event.query.get_or_404(eid)
    db.session.delete(event)
    db.session.commit()
    flash('Мероприятие удалено', 'success')
    return redirect(url_for('admin_events'))


# ============================================
# DS548 CONTEST
# ============================================

@app.route('/contest')
def contest_list():
    """Список всех контестов (без строгой фильтрации по времени для отладки)"""
    # Показываем просто все контесты, отсортированные по дате создания
    all_contests = Contest.query.order_by(Contest.created_at.desc()).all()
    
    return render_template('contest/list_all.html', all_contests=all_contests)

@app.route('/contest/new', methods=['GET', 'POST'])
@login_required
def create_contest():
    """Создание нового контеста (только админ)"""
    if not current_user.is_admin:
        flash('Только администратор может создавать контесты', 'danger')
        return redirect(url_for('contest_list'))
    
    form = ContestForm()
    if form.validate_on_submit():
        contest = Contest(
            title=form.title.data,
            description=form.description.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            author_id=current_user.id
        )
        db.session.add(contest)
        db.session.commit()
        flash('Контест создан!', 'success')
        return redirect(url_for('contest_detail', cid=contest.id))
    
    return render_template('contest/create.html', form=form)

@app.route('/contest/<int:cid>')
def contest_detail(cid):
    """Детали контеста и список задач"""
    contest = Contest.query.get_or_404(cid)
    now = datetime.now()
    
    # Проверка участия
    participation = None
    if current_user.is_authenticated:
        participation = ContestParticipant.query.filter_by(
            contest_id=cid, user_id=current_user.id
        ).first()
    
    # Таблица лидеров
    leaderboard = ContestParticipant.query.filter_by(contest_id=cid).order_by(
        ContestParticipant.score.desc()
    ).limit(50).all()
    
    return render_template('contest/detail.html', 
                           contest=contest,
                           participation=participation,
                           leaderboard=leaderboard,
                           now=now)

@app.route('/contest/<int:cid>/join', methods=['POST'])
@login_required
def join_contest(cid):
    """Регистрация на контест"""
    contest = Contest.query.get_or_404(cid)
    
    # Проверка, не участвует ли уже
    existing = ContestParticipant.query.filter_by(
        contest_id=cid, user_id=current_user.id
    ).first()
    
    if existing:
        flash('Вы уже участвуете в этом контесте', 'info')
    else:
        participant = ContestParticipant(
            contest_id=cid,
            user_id=current_user.id
        )
        db.session.add(participant)
        db.session.commit()
        flash('Вы зарегистрировались на контест!', 'success')
    
    return redirect(url_for('contest_detail', cid=cid))

@app.route('/contest/<int:cid>/problem/<int:pid>')
def problem_detail(cid, pid):
    """Просмотр задачи"""
    contest = Contest.query.get_or_404(cid)
    problem = Problem.query.get_or_404(pid)
    
    # Проверка доступа
    now = datetime.now()
    if now < contest.start_time or now > contest.end_time:
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Контест ещё не начался или уже закончился', 'warning')
            return redirect(url_for('contest_detail', cid=cid))
    
    # Проверка участия
    participation = None
    if current_user.is_authenticated:
        participation = ContestParticipant.query.filter_by(
            contest_id=cid, user_id=current_user.id
        ).first()
    
    # Для code-задач: показать примеры тестов
    sample_tests = []
    if problem.problem_type == 'code':
        sample_tests = ProblemTest.query.filter_by(
            problem_id=pid, is_sample=True
        ).order_by(ProblemTest.order_num).all()
    
    # Для math-задач: показать вопросы и проверить наличие попытки
    questions = []
    existing_math_submission = None
    if problem.problem_type == 'math':
        questions = MathQuestion.query.filter_by(
            problem_id=pid
        ).order_by(MathQuestion.order_num).all()
        
        # Проверяем, есть ли уже попытка
        if current_user.is_authenticated:
            existing_math_submission = Submission.query.filter_by(
                problem_id=pid,
                user_id=current_user.id,
                submission_type='math'
            ).first()
    
    # Форма отправки
    if problem.problem_type == 'code':
        form = CodeSubmissionForm()
    elif problem.problem_type == 'csv':
        form = CSVSubmissionForm()
    else:
        form = None
    
    # История попыток пользователя
    user_submissions = []
    if current_user.is_authenticated:
        user_submissions = Submission.query.filter_by(
            problem_id=pid, user_id=current_user.id
        ).order_by(Submission.submitted_at.desc()).limit(10).all()
    
    return render_template('contest/problem.html',
                           contest=contest,
                           problem=problem,
                           participation=participation,
                           sample_tests=sample_tests,
                           questions=questions,
                           form=form,
                           user_submissions=user_submissions,
                           existing_math_submission=existing_math_submission)

@app.route('/contest/<int:cid>/problem/<int:pid>/submit', methods=['POST'])
@login_required
def submit_solution(cid, pid):
    """Отправка решения"""
    contest = Contest.query.get_or_404(cid)
    problem = Problem.query.get_or_404(pid)
    
    # Проверка участия
    participation = ContestParticipant.query.filter_by(
        contest_id=cid, user_id=current_user.id
    ).first()
    
    if not participation:
        flash('Вы не зарегистрированы на этот контест', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    # Проверка времени
    now = datetime.now()
    if now < contest.start_time or now > contest.end_time:
        flash('Контест ещё не начался или уже закончился', 'warning')
        return redirect(url_for('contest_detail', cid=cid))
    
    if problem.problem_type == 'code':
        return submit_code_solution(cid, pid, problem, participation)
    elif problem.problem_type == 'math':
        return submit_math_solution(cid, pid, problem, participation, contest)
    elif problem.problem_type == 'csv':
        return submit_csv_solution(cid, pid, problem, participation)
    
    flash('Неизвестный тип задачи', 'danger')
    return redirect(url_for('problem_detail', cid=cid, pid=pid))

def check_code_submission(submission, problem):
    """Проверяет код пользователя на всех тестах задачи"""
    tests = ProblemTest.query.filter_by(problem_id=problem.id).order_by(ProblemTest.order_num).all()
    
    if not tests:
        return 'error', 0, {'message': 'Нет тестов для проверки'}
    
    passed = 0
    total = len(tests)
    details = []
    
    # Сохраняем код во временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(submission.code)
        temp_file = f.name
    
    try:
        for i, test in enumerate(tests, 1):
            try:
                # Запускаем код с входными данными через stdin
                result = subprocess.run(
                    ['python3', temp_file],
                    input=test.input_data,
                    capture_output=True,
                    text=True,
                    timeout=problem.time_limit
                )
                
                # Сравниваем вывод (убираем лишние пробелы и переносы)
                actual = result.stdout.strip()
                expected = test.expected_output.strip()
                
                if actual == expected:
                    passed += 1
                    details.append({'test': i, 'status': 'passed'})
                else:
                    details.append({
                        'test': i, 
                        'status': 'wrong_answer',
                        'expected': expected[:100],
                        'actual': actual[:100] if actual else '(пусто)'
                    })
            except subprocess.TimeoutExpired:
                details.append({'test': i, 'status': 'time_limit_exceeded'})
            except Exception as e:
                details.append({'test': i, 'status': 'runtime_error', 'message': str(e)[:100]})
    
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # Подсчитываем баллы
    score = int((passed / total) * problem.max_score) if total > 0 else 0
    
    # Определяем статус
    if passed == total:
        status = 'accepted'
    elif passed > 0:
        status = 'partial'
    else:
        status = 'wrong_answer'
    
    return status, score, {'tests': details, 'passed': passed, 'total': total}

def submit_code_solution(cid, pid, problem, participation):
    """Отправка и проверка code-решения"""
    form = CodeSubmissionForm()
    if form.validate_on_submit():
        submission = Submission(
            problem_id=pid,
            user_id=current_user.id,
            contest_id=cid,
            submission_type='code',
            code=form.code.data,
            language='python',
            status='testing'
        )
        db.session.add(submission)
        db.session.commit()
        
        # Запускаем проверку кода
        try:
            status, score, details = check_code_submission(submission, problem)
            
            submission.status = status
            submission.score = score
            submission.details = json.dumps(details)
            db.session.commit()
            
            # Обновляем счёт участника (вычитаем старый балл, если была попытка, и добавляем новый)
            # Находим лучшую попытку пользователя
            best_submission = Submission.query.filter_by(
                problem_id=pid, 
                user_id=current_user.id
            ).order_by(Submission.score.desc()).first()
            
            # Пересчитываем общий счёт участника для этой задачи
            old_score = 0
            for sub in Submission.query.filter_by(problem_id=pid, user_id=current_user.id).all():
                if sub.id != best_submission.id:
                    pass  # Не учитываем другие попытки
            
            # Обновляем participation.score
            # Сначала убираем старый балл за эту задачу (если был)
            # Проще пересчитать все баллы участника
            total_score = 0
            for p in Contest.query.get(cid).problems:
                best = Submission.query.filter_by(
                    problem_id=p.id,
                    user_id=current_user.id
                ).order_by(Submission.score.desc()).first()
                if best:
                    total_score += best.score
            
            participation.score = total_score
            db.session.commit()
            
            flash(f'Решение проверено! Статус: {status}, Баллы: {score}/{problem.max_score}', 'success')
            
        except Exception as e:
            submission.status = 'error'
            submission.details = json.dumps({'message': str(e)})
            db.session.commit()
            flash(f'Ошибка при проверке кода: {str(e)}', 'danger')
    
    return redirect(url_for('problem_detail', cid=cid, pid=pid))

def submit_math_solution(cid, pid, problem, participation, contest):
    """Отправка math-решения с ограничением в одну попытку"""
    
    # Проверяем, есть ли уже попытка
    existing = Submission.query.filter_by(
        problem_id=pid,
        user_id=current_user.id,
        submission_type='math'
    ).first()
    
    if existing:
        flash('Вы уже отправляли ответы на эту задачу. Повторная отправка невозможна.', 'warning')
        return redirect(url_for('problem_detail', cid=cid, pid=pid))
    
    # Собираем ответы
    questions = MathQuestion.query.filter_by(problem_id=pid).all()
    answers = {}
    total_score = 0
    max_score = 0
    question_results = []
    
    for q in questions:
        max_score += q.points
        answer_key = f'question_{q.id}'
        user_answer = request.form.get(answer_key, '').strip()
        answers[q.id] = user_answer
        
        # Проверка ответа
        is_correct = False
        if q.correct_option is not None:
            # Вопрос с вариантами
            if user_answer == str(q.correct_option):
                total_score += q.points
                is_correct = True
        elif q.correct_answer:
            # Числовой/текстовый ответ (регистронезависимое сравнение)
            if user_answer.lower() == q.correct_answer.lower():
                total_score += q.points
                is_correct = True
        
        question_results.append({
            'question_id': q.id,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'points': q.points if is_correct else 0
        })
    
    # Создаём отправку
    submission = Submission(
        problem_id=pid,
        user_id=current_user.id,
        contest_id=cid,
        submission_type='math',
        answers=json.dumps(answers),
        score=total_score,
        status='graded',
        details=json.dumps({
            'max_score': max_score,
            'earned': total_score,
            'questions': question_results
        })
    )
    db.session.add(submission)
    
    # Пересчитываем общий счёт участника
    total_contest_score = 0
    for p in contest.problems:
        best = Submission.query.filter_by(
            problem_id=p.id,
            user_id=current_user.id
        ).order_by(Submission.score.desc()).first()
        if best:
            total_contest_score += best.score
    
    participation.score = total_contest_score
    db.session.commit()
    
    flash(f'Ответы отправлены! Ваш результат: {total_score} из {max_score} баллов', 'success')
    return redirect(url_for('problem_detail', cid=cid, pid=pid))

def check_csv_submission(submission_path, solution_path):
    """Проверяет CSV-файл участника, сравнивая с эталоном"""
    try:
        # Загружаем файлы
        submission = pd.read_csv(submission_path)
        solution = pd.read_csv(solution_path)
        
        # Определяем колонки автоматически
        if len(submission.columns) < 2:
            return 'error', 0, {'message': 'CSV должен содержать минимум 2 колонки'}
        
        if len(solution.columns) < 2:
            return 'error', 0, {'message': 'Эталонный CSV имеет некорректный формат'}
        
        # Берём первые две колонки: id и prediction
        id_col = submission.columns[0]
        pred_col = submission.columns[1]
        
        sol_id_col = solution.columns[0]
        sol_pred_col = solution.columns[1]
        
        # Сортируем по id для корректного сравнения
        submission = submission.sort_values(id_col).reset_index(drop=True)
        solution = solution.sort_values(sol_id_col).reset_index(drop=True)
        
        # Проверяем длину
        if len(submission) != len(solution):
            return 'error', 0, {
                'message': f'Количество строк не совпадает: {len(submission)} вместо {len(solution)}'
            }
        
        # Сравниваем предсказания (приводим к строке для сравнения)
        sub_pred = submission[pred_col].astype(str).str.strip()
        sol_pred = solution[sol_pred_col].astype(str).str.strip()
        
        correct = (sub_pred == sol_pred).sum()
        total = len(solution)
        accuracy = correct / total if total > 0 else 0
        
        # Находим примеры ошибок (до 5 штук)
        errors_mask = sub_pred != sol_pred
        sample_errors = []
        if errors_mask.any():
            error_df = submission[errors_mask].head(5)
            for idx, row in error_df.iterrows():
                sample_errors.append({
                    'id': str(row[id_col]),
                    'your_answer': str(row[pred_col]),
                    'correct_answer': str(solution.loc[idx, sol_pred_col])
                })
        
        details = {
            'accuracy': f'{accuracy:.2%}',
            'accuracy_value': accuracy,
            'correct': int(correct),
            'total': total,
            'sample_errors': sample_errors
        }
        
        if accuracy == 1.0:
            status = 'accepted'
        elif accuracy > 0:
            status = 'partial'
        else:
            status = 'wrong_answer'
        
        return status, accuracy, details
        
    except Exception as e:
        return 'error', 0, {'message': f'Ошибка обработки CSV: {str(e)}'}

def submit_csv_solution(cid, pid, problem, participation):
    """Отправка и проверка CSV-решения"""
    form = CSVSubmissionForm()
    if form.validate_on_submit():
        # Проверяем, что у задачи есть эталон
        if not problem.solution_path or not os.path.exists(problem.solution_path):
            flash('Эталонное решение ещё не загружено для этой задачи', 'warning')
            return redirect(url_for('problem_detail', cid=cid, pid=pid))
        
        # Сохраняем файл участника
        file = form.csv_file.data
        stored_name = f"{uuid.uuid4().hex}.csv"
        upload_dir = os.path.join(app.config['CONTEST_UPLOAD_FOLDER'], str(cid))
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, stored_name)
        file.save(file_path)
        
        # Создаём отправку
        submission = Submission(
            problem_id=pid,
            user_id=current_user.id,
            contest_id=cid,
            submission_type='csv',
            csv_filename=file.filename,
            csv_path=file_path,
            status='testing'
        )
        db.session.add(submission)
        db.session.commit()
        
        # Проверяем CSV
        try:
            status, accuracy, details = check_csv_submission(file_path, problem.solution_path)
            
            # Считаем баллы: accuracy * max_score
            score = int(accuracy * problem.max_score)
            
            submission.status = status
            submission.score = score
            submission.details = json.dumps(details)
            db.session.commit()
            
            # Обновляем общий счёт участника
            total_score = 0
            for p in Contest.query.get(cid).problems:
                best = Submission.query.filter_by(
                    problem_id=p.id,
                    user_id=current_user.id
                ).order_by(Submission.score.desc()).first()
                if best:
                    total_score += best.score
            
            participation.score = total_score
            db.session.commit()
            
            accuracy_pct = details.get('accuracy', '0%')
            flash(f'CSV проверен! Точность: {accuracy_pct}, Баллы: {score}/{problem.max_score}', 'success')
            
        except Exception as e:
            submission.status = 'error'
            submission.details = json.dumps({'message': str(e)})
            db.session.commit()
            flash(f'Ошибка проверки: {str(e)}', 'danger')
    
    return redirect(url_for('problem_detail', cid=cid, pid=pid))

@app.route('/contest/<int:cid>/problem/new', methods=['GET', 'POST'])
@login_required
def create_problem(cid):
    """Создание задачи в контесте (только админ)"""
    if not current_user.is_admin:
        flash('Только администратор может создавать задачи', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    contest = Contest.query.get_or_404(cid)
    form = ProblemForm()
    
    if form.validate_on_submit():
        problem = Problem(
            contest_id=cid,
            title=form.title.data,
            description=form.description.data,
            problem_type=form.problem_type.data,
            difficulty=form.difficulty.data,
            max_score=form.max_score.data,
            time_limit=form.time_limit.data,
            memory_limit=form.memory_limit.data
        )
        db.session.add(problem)
        db.session.commit()
        
        flash('Задача создана! Теперь добавьте тесты/вопросы.', 'success')
        return redirect(url_for('edit_problem', cid=cid, pid=problem.id))
    
    return render_template('contest/create_problem.html', form=form, contest=contest)

@app.route('/contest/<int:cid>/problem/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def edit_problem(cid, pid):
    """Редактирование задачи и добавление тестов"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    contest = Contest.query.get_or_404(cid)
    problem = Problem.query.get_or_404(pid)
    
    # Получаем тесты и вопросы
    tests = ProblemTest.query.filter_by(problem_id=pid).order_by(ProblemTest.order_num).all()
    questions = MathQuestion.query.filter_by(problem_id=pid).order_by(MathQuestion.order_num).all()
    
    return render_template('contest/edit_problem.html',
                           contest=contest,
                           problem=problem,
                           tests=tests,
                           questions=questions)

# Маршруты для добавления тестов и вопросов будут в следующем сообщении

@app.route('/contest/<int:cid>/problem/<int:pid>/test/add', methods=['POST'])
@login_required
def contest_add_test(cid, pid):
    """Добавление теста к code-задаче"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    input_data = request.form.get('input_data')
    expected_output = request.form.get('expected_output')
    order_num = request.form.get('order_num', type=int)
    is_sample = request.form.get('is_sample') == 'on'
    
    test = ProblemTest(
        problem_id=pid,
        input_data=input_data,
        expected_output=expected_output,
        order_num=order_num,
        is_sample=is_sample
    )
    db.session.add(test)
    db.session.commit()
    
    flash('Тест добавлен', 'success')
    return redirect(url_for('edit_problem', cid=cid, pid=pid))

@app.route('/contest/<int:cid>/problem/<int:pid>/test/<int:tid>/delete', methods=['POST'])
@login_required
def contest_delete_test(cid, pid, tid):
    """Удаление теста"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    test = ProblemTest.query.get_or_404(tid)
    db.session.delete(test)
    db.session.commit()
    
    flash('Тест удалён', 'success')
    return redirect(url_for('edit_problem', cid=cid, pid=pid))

@app.route('/contest/<int:cid>/problem/<int:pid>/question/add', methods=['POST'])
@login_required
def contest_add_question(cid, pid):
    """Добавление вопроса к math-задаче"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    question_text = request.form.get('question_text')
    correct_answer = request.form.get('correct_answer')
    correct_option = request.form.get('correct_option', type=int)
    options = request.form.get('options')
    points = request.form.get('points', type=int)
    order_num = request.form.get('order_num', type=int)
    
    question = MathQuestion(
        problem_id=pid,
        question_text=question_text,
        correct_answer=correct_answer,
        correct_option=correct_option,
        options=options,
        points=points,
        order_num=order_num
    )
    db.session.add(question)
    db.session.commit()
    
    flash('Вопрос добавлен', 'success')
    return redirect(url_for('edit_problem', cid=cid, pid=pid))

@app.route('/contest/<int:cid>/problem/<int:pid>/question/<int:qid>/delete', methods=['POST'])
@login_required
def contest_delete_question(cid, pid, qid):
    """Удаление вопроса"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    question = MathQuestion.query.get_or_404(qid)
    db.session.delete(question)
    db.session.commit()
    
    flash('Вопрос удалён', 'success')
    return redirect(url_for('edit_problem', cid=cid, pid=pid))

@app.route('/contest/<int:cid>/problem/<int:pid>/upload_solution', methods=['POST'])
@login_required
def upload_solution(cid, pid):
    """Загрузка эталонного CSV"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    problem = Problem.query.get_or_404(pid)
    contest = Contest.query.get_or_404(cid)
    
    if 'solution_file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('edit_problem', cid=cid, pid=pid))
    
    file = request.files['solution_file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('edit_problem', cid=cid, pid=pid))
    
    # Сохраняем файл
    upload_dir = os.path.join(app.config['CONTEST_UPLOAD_FOLDER'], str(cid), 'solutions')
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"solution_{uuid.uuid4().hex}.csv"
    file_path = os.path.join(upload_dir, stored_name)
    file.save(file_path)
    
    problem.solution_path = file_path
    db.session.commit()
    
    flash('Эталонный CSV загружен!', 'success')
    return redirect(url_for('edit_problem', cid=cid, pid=pid))


@app.route('/contest/<int:cid>/problem/<int:pid>/upload_test_data', methods=['POST'])
@login_required
def upload_test_data(cid, pid):
    """Загрузка тестовых данных для скачивания участниками"""
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('contest_detail', cid=cid))
    
    problem = Problem.query.get_or_404(pid)
    
    if 'test_data_file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('edit_problem', cid=cid, pid=pid))
    
    file = request.files['test_data_file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('edit_problem', cid=cid, pid=pid))
    
    # Сохраняем файл
    upload_dir = os.path.join(app.config['CONTEST_UPLOAD_FOLDER'], str(cid), 'test_data')
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"test_{uuid.uuid4().hex}.csv"
    file_path = os.path.join(upload_dir, stored_name)
    file.save(file_path)
    
    problem.test_data_path = file_path
    db.session.commit()
    
    flash('Тестовые данные загружены!', 'success')
    return redirect(url_for('edit_problem', cid=cid, pid=pid))


@app.route('/contest/<int:cid>/problem/<int:pid>/download_test_data')
@login_required
def download_test_data(cid, pid):
    """Скачивание тестовых данных участником"""
    problem = Problem.query.get_or_404(pid)
    
    if not problem.test_data_path or not os.path.exists(problem.test_data_path):
        flash('Тестовые данные ещё не загружены', 'warning')
        return redirect(url_for('problem_detail', cid=cid, pid=pid))
    
    directory = os.path.dirname(problem.test_data_path)
    filename = os.path.basename(problem.test_data_path)
    
    return send_from_directory(
        directory,
        filename,
        as_attachment=True,
        download_name=f'test_data_{problem.id}.csv'
    )

# ============================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
