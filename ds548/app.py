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

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)