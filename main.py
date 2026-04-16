import base64
from flask import Flask, render_template, request, redirect, session, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta, datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
from flask_session import Session
from flask_mail import Mail, Message
from flask_migrate import Migrate
import random
from dotenv import load_dotenv
from flask_wtf import CSRFProtect
from flask import jsonify
import uuid

load_dotenv()

# Конфиги

app = Flask(__name__)  # Инициализация приложения
app.secret_key = '123'
manager = LoginManager(app)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    days=31)  # Длительность сессии
app.config['SESSION_PERMANENT'] = True  # Сессия не исчезает после перезапуска
app.config['SESSION_TYPE'] = 'filesystem'  # Тип сессии
Session(app)  # Инициализация сессии
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///main.db'  # SQLAlchemy
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['AVATARS_FOLDER'] = 'static/avatars'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Сервер почты (Gmail)
app.config['MAIL_PORT'] = 587  # Порт почты (Gmail)
app.config['MAIL_USE_TLS'] = True  # Сертификаты безопасности
app.config['MAIL_USE_SSL'] = False  # Сертификаты безопасности
app.config['MAIL_USERNAME'] = 'nexusmcru@gmail.com'  # Имя почты
app.config['MAIL_PASSWORD'] = 'bugquvonzfttozus'  # Пароль приложения
# Чтобы не указывать отправителя
app.config['MAIL_DEFAULT_SENDER'] = 'nexusmcru@gmail.com'
db = SQLAlchemy(app)  # Инициализация дб
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# Инициализация почты

mail = Mail(app)

# Классы дб


class User(db.Model, UserMixin):  # Пользователи
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    description = db.Column(
        db.Text, default="Пользователь поленился и не добавил инфу о себе :[")
    email = db.Column(db.Text, unique=True)
    hash_password = db.Column(db.String)
    avatar = db.Column(db.String)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    is_moderator = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_frozen = db.Column(db.Boolean, default=False)

    def __init__(self, username, email, hash_password, is_moderator=None, is_admin=None, is_banned=None, is_frozen=None, description=None):
        self.username = username
        self.description = description or "Пользователь поленился и не добавил инфу о себе :["
        self.email = email
        self.hash_password = hash_password
        self.is_moderator = is_moderator or False
        self.is_admin = is_admin or False
        self.is_banned = is_banned or False
        self.is_frozen = is_frozen or False

    def __str__(self):
        return f"ID: {self.id}, Username: {self.username}, Email: {self.email}"


class Notifications(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message_id = db.Column(db.Integer, db.ForeignKey(
        'message.id'))
    type = db.Column(db.String(50))
    message = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, default=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, from_user_id, type, message, post_id=None, discuss_id=None):
        self.user_id = user_id
        self.from_user_id = from_user_id
        self.post_id = post_id or ''
        self.discuss_id = discuss_id or ''
        self.type = type
        self.message = message


class Email_cods(db.Model):  # Коды отправляемые на Email
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text)
    code = db.Column(db.String)
    is_activated = db.Column(db.Boolean, default=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, email, code, is_activated):
        self.email = email
        self.code = code
        self.is_activated = is_activated

    def __str__(self):
        return f"ID: {self.id}, Username: {self.username}, Email: {self.email}"


class Messages(db.Model):  # Сообщения
    id = db.Column(db.Integer, primary_key=True)
    id_sender = db.Column(db.Integer)
    id_recipient = db.Column(db.Integer, nullable=True)
    is_reply = db.Column(db.Boolean)
    reply_message_id = db.Column(db.Integer, nullable=True)
    text = db.Column(db.Text)
    reactions = db.Column(db.JSON, nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, id_sender, text, id_recipient=False, reply_message_id=False):
        self.id_sender = id_sender
        self.id_recipient = id_recipient
        self.reply_message_id = reply_message_id or ""
        self.text = Text


class Views(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer, nullable=True)
    session_id = db.Column(db.String, nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)


# Для проверки файлов
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}  # Расширения файлов
MAX_FILE_SIZE = 16 * 1024 * 1024  # Размер файлов 16MB


def time_ago(date):
    now = datetime.utcnow()
    diff = now - date
    
    total_seconds = int(diff.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds} секунд назад"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} минут назад"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} часов назад"
    elif total_seconds < 2592000:
        days = total_seconds // 86400
        return f"{days} дней назад"
    else:
        return date.strftime("%d.%m.%Y")


def generate_code():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/notifications', methods=['POST', 'GET'])
def notifications():
    user = current_user
    id = user.id
    notifications = Notification.query.filter_by(user_id=id).limit(3).all()
    if notifications:
        notice_author = ''
        for notification in notifications:
            notice_author = notification.from_user_id
        return render_template('notifications.html', notifications=notifications, notice_author=notice_author)
    return render_template('index.html')


@app.route('/mark_notice', methods=['POST'])
def mark_notice():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401

    try:
        Notification.query.filter_by(
            user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()

        return jsonify({'success': True, 'message': 'Прочитано'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/send_email', methods=['POST'])
def send_email():
    if request.method == 'POST':

        # Получение данных из формы для их сохранения
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        password_r = request.form.get('password_r', '')
        edition = request.form.get('version', 'java')

        if not email:  # Если нет почты
            print("Почта не введена!")
            return redirect(url_for('register'))
        else:
            # Добавление данных в сессию
            session["username"] = username
            session["email"] = email
            session["password"] = password
            session["password2"] = password_r
            session["edition"] = edition
            username = session["username"]
            email = session["email"]  # Получение почты из сессии
            Email_cods.query.filter_by(email=email).delete()
            db.session.commit()
            code = generate_code()  # Генерация кода
            new_code = Email_cods(email, code, False)  # Заготовка
            code_verify = Email_cods.query.filter_by(
                email=email, is_activated=True).first()
            if code_verify:
                db.session.delete(code_verify)
                db.session.commit()
            else:
                db.session.add(new_code)  # Добавление кода в бд
                db.session.commit()  # Подтверждение
            msg = Message(
                subject="Nexus MC: Код подтверждения",
                recipients=[email],
                body=f'''Привет, {username}.
        Вы регистрируетесь на Nexus MC!
        Подтвердите свою Электронную почту введя код снизу в поле ввода.
        {code}'''
            )  # Шаблон для Email

            mail.send(msg)  # Отправление Email

        return '', 204


@manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@app.context_processor
def inject_helpers():
    return dict(time_ago=time_ago)


@app.context_processor
def inject_user():
    user = current_user

    if user.is_authenticated:
        if user.is_banned:
            logout_user()
            return {}

        notifications = Notification.query.filter_by(
            user_id=user.id,
            is_read=False
        ).order_by(Notification.date.desc()).limit(3).all()

        for notice in notifications:
            notice.author = User.query.get(notice.from_user_id)

        return {
            'user': user,
            'notifications': notifications,
            'notifications_count': len(notifications)
        }

    return {}


@app.route('/')
def index():
    messages = Messages.query.get().all
    comments_len = 0
    if posts:
        for post in posts:
            comment = Comments.query.filter_by(id_post=post.id).all()
            post.author = User.query.get(post.id_author)
            comments_len = len(comment)
    return render_template("index.html", posts=posts, comments_len=comments_len)

@app.route('/moderate_posts')
def moderate_posts():
    if current_user.is_moderator:
        posts = Posts.query.filter_by(status='on_moderating').all()
        if posts:
            for post in posts:
                comment = Comments.query.filter_by(id_post=post.id).all()
                post.author = User.query.get(post.id_author)
                comments_len = len(comment)
        return render_template("moderate_posts.html", posts=posts)
    else:
        return redirect(url_for('index'))


@app.route('/news_nexus')
def news_nexus():
    return render_template("news_nexus.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        email = session["email"]
        return render_template("register.html", email=email)

    username = session["username"]
    email = session["email"]
    password = session["password"]
    edition = session["edition"]
    print(email, username)

    # Получение проверочного кода из формы в модальном окне
    verify_code = request.form.get('verify_code')
    user = User.query.filter_by(username=username).first()

    if user:
        flash('Имя пользователя занято!', 'danger')
        return redirect("/register")

    elif len(username) < 4:
        flash("Зачем в коде лазишь?!", 'danger')
        return redirect(url_for('register'))

    else:
        code_entry = Email_cods.query.filter_by(email=email).first()
        print(code_entry.code, verify_code)

        if code_entry:
            code = code_entry.code
        else:
            flash('Код не найден или уже активирован!', 'danger')
            return redirect("/register")

        if code == verify_code:
            hash_pwd = generate_password_hash(password)
            new_user = User(username, email, hash_pwd, edition)
            db.session.add(new_user)
            db.session.commit()
            user = db.session.get(User, new_user.id)
            login_user(user)
            session.permanent = True
            code_entry.is_activated = True
            db.session.commit()
            flash("Регистрация прошла успешно!", 'success')
            return redirect("/")

        else:
            flash("Неверный код!", 'danger')
            return redirect("/register")


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == "GET":

        if current_user.is_authenticated:  # Проверка на авторизацию
            flash("Вы уже авторизованы", 'warning')
            return redirect("/")

        return render_template("login.html")

    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()

    if user.is_banned:
        flash('Вы забанены!', 'danger')
        return redirect(url_for('index'))

    if user is None:

        flash('Такого пользователя не существует', 'danger')
        return redirect("/login")

    if check_password_hash(user.hash_password, password):

        login_user(user)
        session.permanent = True
        flash("Успешный вход!", "success")
        return redirect('/')

    flash("Неверный логин или пароль!", 'danger')
    return render_template("login.html")


@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect("/")


@app.route('/user/<int:id>', methods=['GET', 'POST'])
def user(id):

    avatar = request.files.get('avatar')
    user = User.query.filter_by(id=id).first()
    status = "Пользователь"
    if user.is_moderator:
        status = "Модератор"
    elif user.is_checked:
        status = "Проверенный"
    elif user.username == "Whyiok" or current_user.username == "Nexus":
        status = "Админ"

    return render_template("account.html", user=user, status=status)


@app.route('/update_user', methods=['GET', 'POST'])
def update_user():
    if request.method == 'POST':
        avatar = request.files.get('avatar')
        email = request.form.get('email')
        old_pass = request.form.get('old_pass')
        new_pass = request.form.get('new_pass')
        new_pass_repeat = request.form.get('new_pass_repeat')
        user = current_user
        updated = False
        id = current_user.id

        if email and email != '' and email != user.email:
            user.email = email
            updated = True
            flash('Email обновлен!', 'success')

        if old_pass and new_pass and new_pass_repeat:
            if check_password_hash(user.hash_password, old_pass):
                if new_pass == new_pass_repeat:
                    user.hash_password = generate_password_hash(new_pass)
                    updated = True
                    flash("Пароль сменён!", 'success')
                else:
                    flash("Пароли не совпадают!", 'danger')
            else:
                flash("Старый пароль неверный!", 'danger')

        if avatar and avatar.filename:

            if not allowed_file(avatar.filename):
                flash(
                    "Недопустимый формат файла! Разрешены: gif, png, jpg, jpeg", 'danger')
                return redirect(url_for('user', id=id))

            # Проверка размера файла
            avatar.seek(0, os.SEEK_END)
            file_size = avatar.tell()
            avatar.seek(0)  # Вернуть указатель в начало

            if file_size > MAX_FILE_SIZE:
                flash(
                    f"Файл слишком большой! Максимум {MAX_FILE_SIZE // 1024 // 1024}MB", 'danger')
                return redirect(url_for('user', id=id))

            filename = secure_filename(avatar.filename)
            filepath = os.path.join(app.config['AVATARS_FOLDER'], filename)

            avatar.save(filepath)
            flash("Аватар добавлен!", "success")
            user.avatar = filename
            updated = True

        if updated:
            db.session.commit()

    return redirect(url_for('user', id=id))


@app.route('/del_account', methods=['GET', 'POST'])
def del_account():

    db.session.delete(current_user)
    db.session.commit()
    flash("Аккаунт удален!", 'success')
    return redirect("/")


@app.route('/comment/<contentType>/<int:id>', methods=['GET', 'POST'])
def comment(contentType, id):
    if current_user.is_authenticated:
        if request.method == 'POST':
            if contentType == 'post':
                text = request.form.get('text')
                post_id = request.form.get('post_id')
                post = Posts.query.get(post_id)
                if len(text) > 500:
                    flash("Недопустимый запрос.", 'danger')
                    return redirect(url_for("index"))
                new_notification = Notification(post.id_author, current_user.id, post_id, 'прокомментировал ваш пост!', 'лол')
                new_comment = Comments(id_author=current_user.id, id_post=post_id, comment=text)
                db.session.add(new_notification)
                db.session.add(new_comment)
                db.session.commit()
                flash("Комментарий добавлен!", 'success')
                return redirect(url_for('post', id=id))

            elif contentType == 'discuss':
                text = request.form.get('text')
                discuss_id = request.form.get('discuss_id')
                discuss = Discuss.query.get(discuss_id)
                if len(text) > 500:
                    flash("Недопустимый запрос.", 'danger')
                    return redirect(url_for('forum'))
                new_notification = Notification(
                    discuss.id_author, current_user.id, discuss_id, 'ответил на вашу дискуссию!', 'лол')
                new_comment = Comments(id_author=current_user.id, id_discuss=discuss_id, comment=text)
                db.session.add(new_notification)
                db.session.add(new_comment)
                db.session.commit()
                flash("Ответ добавлен!", 'success')
                return redirect(url_for('discuss', id=id))
            else:
                flash("Пост или Дискуссия не найдены!", 'danger')
                return redirect(url_for('index'))
    else:
        flash("Пожалуйста, войдите в аккаунт!", 'danger')
        return redirect(url_for('login'))


@app.route('/forum', methods=['GET', 'POST'])
def forum():
    page = request.args.get('page', 1, type=int)
    per_page = 25
    pagination = Discuss.query.order_by(Discuss.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    discusses = pagination.items
    author = None
    comments_len = 0
    if len(discusses) != 0:
        for discuss in discusses:
            author = User.query.get(discuss.id_author)
            comment = Comments.query.filter_by(id_discuss=discuss.id).all()
            id = discuss.id
            if comment or len(comment) != 0:
                comments_len = len(comment)
            if current_user.is_authenticated:
                discuss.liked = Likes.query.filter_by(
                    id_author=current_user.id,
                    id_discuss=id
                ).first() is not None
            else:
                discuss.liked = False

    return render_template("forum.html", discusses=discusses, author=author, pagination=pagination, comments_len=comments_len)


@app.route('/add_post/<post_type>', methods=['GET', 'POST'])
def add_post(post_type):
    if current_user.is_authenticated:
        if request.method == 'POST':
            file = request.files.get('image')
            title = request.form.get('title')
            text = request.form.get('text')
            id_author = current_user.id
            views = 0
            true_types = ['article', 'server_java', 'server_bedrock', 'texture_pack']
            if not post_type in true_types:
                flash("Недопустимый тип поста.", 'danger')
                return redirect(url_for('index'))

            if title == '' or text == '':
                flash("Недопустимый запрос.", 'danger')
                return redirect(url_for('add_post'))

            else:
                if current_user.is_banned:
                    flash('Вы забанены!', 'success')
                    redirect(url_for('index'))
                else:
                    try:
                        image_data = None
                        if file and file.filename != '':

                            if not allowed_file(file.filename):
                                flash(
                                    "Недопустимый формат файла! Разрешены: gif, png, jpg, jpeg", 'danger')
                                return redirect(url_for('add_post'))

                            file_size = file.tell()

                            if file_size > MAX_FILE_SIZE:
                                flash(
                                    f"Файл слишком большой! Максимум {MAX_FILE_SIZE // 1024 // 1024}MB", 'danger')

                            filename = secure_filename(file.filename)
                            file.save(os.path.join(
                                app.config['UPLOAD_FOLDER'], filename))
                            flash("Картинка добавлена!", "success")
                            print("Файл загружен!")

                        else:
                            print("Файл не загружен.")
                            image_data = None

                        db.session.add(Posts(id_author=id_author, title=title, text=text,
                                       views=views, status='on_moderating', type=post_type, image_name=file.filename))
                        db.session.commit()
                        flash("Пост успешно добавлен!", 'success')
                        return redirect(url_for('index'))

                    except Exception as e:
                        print(f"Не удалось добавить пост! Ошибка: {e}")
                        db.session.rollback()

        return render_template("add_post.html", post_type=post_type)

    else:
        flash("Войдите в аккаунт!", 'danger')
        return redirect(url_for('login'))


@app.route('/add_discuss', methods=['GET', 'POST'])
def add_discuss():
    if current_user.is_authenticated:
        if request.method == 'POST':

            title = request.form.get('title')
            text = request.form.get('text')
            id_author = current_user.id
            views = 0
            categories = request.form.getlist('categories')

            if title == '' or text == '':
                flash("Недопустимый запрос.", 'danger')
                return redirect(url_for('add_discuss'))

            else:
                if current_user.is_banned:
                    flash('Вы забанены!', 'success')
                    redirect(url_for('index'))
                else:
                    try:
                        db.session.add(Discuss(
                            id_author=id_author, title=title, text=text, views=views, status='on_moderating', categories=categories))
                        db.session.commit()
                        flash("Дискуссия успешно добавлена!", 'success')
                        return redirect(url_for('forum'))

                    except Exception as e:
                        flash(
                            f"Не удалось добавить дискуссию! Ошибка: {e}", 'danger')
                        db.session.rollback()

        return render_template("add_discuss.html")

    else:
        flash("Войдите в аккаунт!", 'danger')
        return redirect(url_for('login'))


@app.route('/discuss/<int:id>', methods=['GET', 'POST'])
def discuss(id):
    discuss = db.session.get(Discuss, id)
    comments = Comments.query.filter_by(id_discuss=id).all()

    if comments:
        for comment in comments:
            comment.author = User.query.get(comment.id_author)
    user_a = db.session.get(User, discuss.id_author)
    liked = False
    disliked = False

    if not discuss:
        return redirect(url_for('forum'))

    if current_user.is_authenticated:
        viewer_id = current_user.id

        view = Views.query.filter_by(
            discuss_id=id,
            user_id=viewer_id
        ).first()

        liked = Likes.query.filter_by(
            id_author=current_user.id,
            id_discuss=id
        ).first() is not None
        disliked = Dislikes.query.filter_by(
            id_author=current_user.id,
            id_discuss=id
        ).first() is not None
    else:
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        viewer_id = session['session_id']
        view = Views.query.filter_by(
            discuss_id=id,
            user_id=viewer_id
        ).first()
    if not view:
        new_view = Views(
            discuss_id=id,
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=None if current_user.is_authenticated else viewer_id
        )
        db.session.add(new_view)
        discuss.views += 1
        db.session.commit()

    return render_template("discuss.html", discuss=discuss, liked=liked, disliked=disliked, user_a=user_a, comments=comments)

@app.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = db.session.get(Posts, id)
    comments = Comments.query.filter_by(id_post=id).all()

    if comments:
        for comment in comments:
            comment.author = User.query.get(comment.id_author)
    user_a = db.session.get(User, post.id_author)
    liked = False
    disliked = False

    if not post:
        return redirect(url_for('index'))

    if current_user.is_authenticated:
        viewer_id = current_user.id

        view = Views.query.filter_by(
            post_id=id,
            user_id=viewer_id
        ).first()

        liked = Likes.query.filter_by(
            id_author=current_user.id,
            id_post=id
        ).first() is not None
        disliked = Dislikes.query.filter_by(
            id_author=current_user.id,
            id_post=id
        ).first() is not None
    else:
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        viewer_id = session['session_id']
        view = Views.query.filter_by(
            post_id=id,
            user_id=viewer_id
        ).first()
    if not view:
        new_view = Views(
            post_id=id,
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=None if current_user.is_authenticated else viewer_id
        )
        db.session.add(new_view)
        post.views += 1
        db.session.commit()

    return render_template("post.html", post=post, liked=liked, disliked=disliked, user_a=user_a, comments=comments)


@app.route('/delete_post/<int:id>', methods=['GET', 'POST'])
def delete_post(id):
    if request.method == 'POST':
        word = 'Удалить'
        word_input = request.form .get('word')
        if word_input == word:
            post = db.session.get(Posts, id)
            user = current_user
            if not post:
                return redirect(url_for('forum'))

            if current_user.username == "Whyiok":
                db.session.delete(post)
                db.session.commit()
                flash("Удалено!", 'danger')
                return redirect(url_for('forum'))

            if user.id != post.id_author:
                flash("Вы не можете удалять чужие посты!", 'danger')
                return redirect(url_for('forum'))

            # если есть таблица лайков
            Likes.query.filter_by(id_post=id).delete()
            # если есть таблица комментариев
            Comments.query.filter_by(id_post=id).delete()

            db.session.delete(post)
            db.session.commit()
            return redirect(url_for('forum'))
        else:
            flash('Неверное слово!', 'warning')
            return redirect(url_for('post', id=id))


@app.route('/like/<contentType>/<int:id>', methods=['GET', 'POST'])
def like(contentType, id):
    if current_user.is_authenticated:
        if contentType == 'discuss':
            discuss = Discuss.query.filter_by(id=id).first()
            like = Likes.query.filter_by(
                id_author=current_user.id, id_discuss=id).first()
            if like:
                db.session.delete(like)
                discuss.rating -= 1
                db.session.commit()
                return jsonify({
                    "rating": discuss.rating,
                    "liked": False
                })
            else:
                new_like = Likes(id_author=current_user.id, id_discuss=id)
                new_notice = Notification(user_id=discuss.id_author, from_user_id=current_user.id,
                                          discuss_id=discuss.id, type="понравилась ваша ветка!", message="")
                discuss.rating += 1
                db.session.add(new_like)
                db.session.add(new_notice)
                db.session.commit()
                return jsonify({
                    "rating": discuss.rating,
                    "liked": True
                })
        elif contentType == 'post':
            post = Posts.query.filter_by(id=id).first()
            like = Likes.query.filter_by(
                id_author=current_user.id, id_post=id).first()
            if like:
                db.session.delete(like)
                post.rating -= 1
                db.session.commit()
                return jsonify({
                    "rating": post.rating,
                    "liked": False
                })
            else:
                new_like = Likes(id_author=current_user.id, id_post=id)
                new_notice = Notification(user_id=post.id_author, from_user_id=current_user.id,
                                          post_id=post.id, type="понравился ваш пост!", message="")
                post.rating += 1
                db.session.add(new_like)
                db.session.add(new_notice)
                db.session.commit()
                return jsonify({
                    "rating": post.rating,
                    "liked": True
                })
        else:
            flash('Нету такого поста или дискуссии!', 'danger')
            return redirect(url_for('forum'))

    else:
        flash("Авторизируйтесь!", 'danger')
        return redirect('/login')


@app.route('/report/<int:id>', methods=['GET', 'POST'])
def report(id):
    if current_user.is_authenticated:
        post = db.session.get(Posts, id)
        discuss = db.session.get(Discuss, id)
        moderators = User.query.filter_by(is_moderator=True).all()
        print(f"{len(moderators)} модераторов найдено")
        if post:
            for moderator in moderators:
                new_notice = Notification(user_id=moderator.id, from_user_id=current_user.id,
                                          post_id=post.id, message="отправил жалобу на пост!", type=5)
                db.session.add(new_notice)
            db.session.commit()
            flash('Спасибо за помощь!', 'success')
            return redirect(url_for('forum'))
            
        elif discuss:
            for moderator in moderators:
                new_notice = Notification(user_id=moderator.id, from_user_id=current_user.id,
                                          discuss_id=discuss.id, message="отправил жалобу на ветку!", type=5)
                db.session.add(new_notice)
            db.session.commit()
            flash('Спасибо за помощь!', 'success')
            return redirect(url_for('forum'))
            
        else:
            flash('Нету такого поста или дискуссии!', 'danger')
            return redirect(url_for('forum'))

    else:
        flash("Авторизируйтесь!", 'danger')
        return redirect('/login')


@app.route('/edit_post/<int:id>', methods=['GET', 'POST'])
def edit_post(id):
    if current_user.is_authenticated:
        if request.method == 'POST':
            file = request.files.get('image')
            title = request.form.get('title')
            text = request.form.get('text')
            post = Posts.query.get(id)

            categories = request.form.getlist('categories')

            if title == '' or text == '':
                flash("Недопустимый запрос.", 'danger')
                return redirect(url_for('add_post'))
            else:
                try:
                    image_data = None
                    if file and file.filename != '':
                        if not allowed_file(file.filename):
                            flash(
                                "Недопустимый формат файла! Разрешены: gif, png, jpg, jpeg", 'danger')
                            return redirect(url_for(f'edit_post{id}'))
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)

                        if file_size > MAX_FILE_SIZE:
                            flash(
                                f"Файл слишком большой! Максимум {MAX_FILE_SIZE // 1024 // 1024}MB", 'danger')
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(
                            app.config['UPLOAD_FOLDER'], filename))
                        flash("Картинка добавлена!", "success")
                        print("Файл загружен!")
                    else:
                        print("Файл не загружен.")

                        image_data = None
                    post = Posts.query.filter_by(id=id).first()
                    post.title = title
                    post.text = text
                    post.image_name = file.filename
                    post.categories = categories
                    db.session.commit()
                    flash("Пост успешно изменен!", 'success')
                    return redirect(url_for('forum'))
                except Exception as e:
                    print(f"Не удалось изменить пост! Ошибка: {e}")
                    db.session.rollback()
        return render_template("edit_post.html", post=post)
    else:
        flash("Войдите в аккаунт!", 'danger')
        return redirect(url_for('login'))


@app.route('/ban_user/<int:id>', methods=['GET', 'POST'])
def ban_user(id):
    user = User.query.filter_by(id=id).first()
    user.is_banned = True
    db.session.commit()
    return redirect(url_for('user', id=id))


@app.route('/unban_user/<int:id>', methods=['GET', 'POST'])
def unban_user(id):
    user = User.query.filter_by(id=id).first()
    user.is_banned = False
    db.session.commit()
    return redirect(url_for('user', id=id))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=5000)
