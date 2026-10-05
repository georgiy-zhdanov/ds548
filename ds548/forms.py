from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class QuestionForm(FlaskForm):
    title = StringField('Заголовок', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Вопрос', validators=[DataRequired()])
    submit = SubmitField('Задать вопрос')

class AnswerForm(FlaskForm):
    content = TextAreaField('Ответ', validators=[DataRequired()])
    submit = SubmitField('Ответить')

class TestForm(FlaskForm):
    title = StringField('Название теста', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Описание', validators=[Optional()])
    questions_data = TextAreaField('Вопросы (JSON)', validators=[DataRequired()])
    submit = SubmitField('Сохранить тест')

class ArticleForm(FlaskForm):
    title = StringField('Название статьи', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Содержание', validators=[DataRequired()])
    submit = SubmitField('Сохранить статью')

from flask_wtf.file import FileField, FileRequired, FileAllowed
from config import Config

class FolderForm(FlaskForm):
    name = StringField('Название папки', validators=[DataRequired(), Length(max=200)])
    parent = IntegerField('Родительская папка', validators=[Optional()])
    submit = SubmitField('Создать папку')

class FileUploadForm(FlaskForm):
    file = FileField('Файл', validators=[
        FileRequired(),
        FileAllowed(Config.ALLOWED_EXTENSIONS, 'Недопустимый тип файла!')
    ])
    folder = IntegerField('Папка', validators=[Optional()])
    submit = SubmitField('Загрузить')

from wtforms import DateTimeLocalField

class EventForm(FlaskForm):
    title = StringField('Название мероприятия', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Описание', validators=[DataRequired()])
    event_date = DateTimeLocalField('Дата и время', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    location = StringField('Место проведения', validators=[Optional(), Length(max=200)])
    submit = SubmitField('Предложить мероприятие')