from flask import Flask, render_template, request, redirect, flash, url_for, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_, inspect
from datetime import datetime, timedelta
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))
os.makedirs(app.instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'bubble.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
MAX_MESSAGE_LENGTH = 1000

def allowed_file(filename):
    return True


def get_user_display_name(user):
    if not user:
        return ''
    return (user.display_name or user.username or '').strip()


def build_user_search_filter(query):
    return or_(
        User.username.ilike(f'%{query}%'),
        User.display_name.ilike(f'%{query}%')
    )

def user_room(user_id):
    return f'user:{user_id}'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), nullable=True)
    about = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(255), nullable=True)
    boosts = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    last_online = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    friend = db.relationship('User', foreign_keys=[friend_id])


class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(255), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    boosts = db.Column(db.Integer, default=0, nullable=False)
    owner = db.relationship('User')
    channels = db.relationship('Channel', backref='server', cascade='all, delete-orphan', lazy='dynamic')
    members = db.relationship('ServerMember', backref='server', cascade='all, delete-orphan', lazy='dynamic')


class ServerMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(50), default='member', nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User')


class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), default='text', nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    messages = db.relationship('Message', backref='channel', cascade='all, delete-orphan', lazy='dynamic')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User')


class DMConversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])


class DMMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('dm_conversation.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('dm_message.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    conversation = db.relationship('DMConversation')
    user = db.relationship('User')
    reply_to = db.relationship('DMMessage', remote_side=[id])


class GroupConversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    icon = db.Column(db.String(255), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    owner = db.relationship('User')


class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group_conversation.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User')


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False, unique=True)
    mime_type = db.Column(db.String(100), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User')


class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group_conversation.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('group_message.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User')
    reply_to = db.relationship('GroupMessage', remote_side=[id])


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'success': False, 'message': 'Файл слишком большой'}), 413


class FileAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    size = db.Column(db.Integer, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship('User')


def ensure_schema():
    inspector = inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('user')}
    with db.engine.begin() as connection:
        if 'display_name' not in user_columns:
            connection.exec_driver_sql('ALTER TABLE user ADD COLUMN display_name VARCHAR(80)')
        if 'about' not in user_columns:
            connection.exec_driver_sql('ALTER TABLE user ADD COLUMN about VARCHAR(255)')

    missing_names = User.query.filter(or_(User.display_name.is_(None), User.display_name == '')).all()
    for user in missing_names:
        user.display_name = user.username
    if missing_names:
        db.session.commit()


def serialize_user_profile(user, is_me=False):
    return {
        'id': user.id,
        'name': get_user_display_name(user),
        'username': user.username,
        'about': user.about or '',
        'avatar': user.avatar or '',
        'is_me': is_me,
        'is_online': user.is_online,
    }


def group_room(group_id):
    return f'group:{group_id}'


def build_group_entries(user):
    groups = GroupConversation.query.join(GroupMember).filter(GroupMember.user_id == user.id).all()
    entries = []
    for group in groups:
        last_message = GroupMessage.query.filter_by(group_id=group.id).order_by(GroupMessage.created_at.desc()).first()
        last_activity = last_message.created_at if last_message else group.created_at
        entries.append({
            'type': 'group',
            'group': group,
            'last_message': last_message,
            'last_activity': last_activity,
        })
    entries.sort(key=lambda entry: (entry['last_activity']), reverse=True)
    return entries


def get_group_members(group_id):
    return GroupMember.query.filter_by(group_id=group_id).all()


class ServerRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20), default='#8B5CF6', nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    permissions = db.Column(db.Text, default='', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    server = db.relationship('Server')


class ServerMemberRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_member_id = db.Column(db.Integer, db.ForeignKey('server_member.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('server_role.id'), nullable=False)
    server_member = db.relationship('ServerMember')
    role = db.relationship('ServerRole')


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    inviter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('server_role.id'), nullable=True)
    max_uses = db.Column(db.Integer, default=0, nullable=False)
    uses = db.Column(db.Integer, default=0, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    server = db.relationship('Server')
    inviter = db.relationship('User', foreign_keys=[inviter_id])
    role = db.relationship('ServerRole')


class ServerBoost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    boosted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    server = db.relationship('Server')
    user = db.relationship('User')


class ServerSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=True)
    icon = db.Column(db.String(255), nullable=True)
    banner = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    server = db.relationship('Server')


class UserSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    status = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    banner = db.Column(db.String(255), nullable=True)
    user = db.relationship('User')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def channel_room(channel_id):
    return f'channel:{channel_id}'


def dm_room(dm_id):
    return f'dm:{dm_id}'


def get_user_servers(user):
    owned_servers = Server.query.filter_by(owner_id=user.id).order_by(Server.created_at.asc()).all()
    member_servers = Server.query.join(ServerMember).filter(ServerMember.user_id == user.id).order_by(Server.created_at.asc()).all()
    merged = {}
    for server in owned_servers + member_servers:
        merged[server.id] = server
    return list(merged.values())


def get_accepted_friendships(user_id):
    return Friendship.query.filter(
        or_(Friendship.user_id == user_id, Friendship.friend_id == user_id),
        Friendship.status == 'accepted'
    ).order_by(Friendship.created_at.asc()).all()


def get_friend_user(friendship, user_id):
    if friendship.user_id == user_id:
        return friendship.friend
    return friendship.user


def get_friend_users(user):
    return [get_friend_user(friendship, user.id) for friendship in get_accepted_friendships(user.id)]


def get_dm_with_user(user_id, other_user_id):
    return DMConversation.query.filter(
        or_(
            and_(DMConversation.user1_id == user_id, DMConversation.user2_id == other_user_id),
            and_(DMConversation.user1_id == other_user_id, DMConversation.user2_id == user_id)
        )
    ).first()


def ensure_dm_with_user(user_id, other_user_id):
    conversation = get_dm_with_user(user_id, other_user_id)
    if conversation:
        return conversation
    conversation = DMConversation(user1_id=user_id, user2_id=other_user_id)
    db.session.add(conversation)
    db.session.commit()
    return conversation


def build_dm_entries(user):
    conversations = DMConversation.query.filter(
        or_(DMConversation.user1_id == user.id, DMConversation.user2_id == user.id)
    ).all()
    entries = []
    for conversation in conversations:
        other_user = conversation.user1 if conversation.user1_id != user.id else conversation.user2
        last_message = DMMessage.query.filter_by(conversation_id=conversation.id).order_by(DMMessage.created_at.desc()).first()
        last_activity = last_message.created_at if last_message else conversation.created_at
        entries.append({
            'dm': conversation,
            'user': other_user,
            'last_message': last_message,
            'last_activity': last_activity,
        })
    entries.sort(key=lambda entry: (entry['last_activity'], get_user_display_name(entry['user']).lower()), reverse=True)
    return entries


def build_member_users(selected_server):
    ordered_users = {}
    ordered_users[selected_server.owner.id] = selected_server.owner
    for member in selected_server.members.order_by(ServerMember.joined_at.asc()).all():
        ordered_users[member.user.id] = member.user
    return list(ordered_users.values())


def user_in_server(server_id, user_id):
    server = Server.query.get(server_id)
    if not server:
        return False
    if server.owner_id == user_id:
        return True
    member = ServerMember.query.filter_by(server_id=server_id, user_id=user_id).first()
    return member is not None


def generate_invite_code():
    return secrets.token_urlsafe(8)[:10]


def get_server_roles(server_id):
    return ServerRole.query.filter_by(server_id=server_id).order_by(ServerRole.position.asc(), ServerRole.created_at.asc()).all()


def get_server_invites(server_id):
    return Invite.query.filter_by(server_id=server_id).order_by(Invite.created_at.desc()).all()


def ensure_default_server_role(server):
    existing = ServerRole.query.filter_by(server_id=server.id, name='@everyone').first()
    if not existing:
        role = ServerRole(server_id=server.id, name='@everyone', position=0, permissions='')
        db.session.add(role)
        db.session.commit()
        return role
    return existing


@app.route('/invite/<code>')
def join_invite(code):
    invite = Invite.query.filter_by(code=code).first()
    if not invite:
        flash('Приглашение недействительно', 'danger')
        return redirect(url_for('index'))
    
    if invite.expires_at and datetime.utcnow() > invite.expires_at:
        flash('Приглашение истекло', 'danger')
        return redirect(url_for('index'))
    
    if invite.max_uses > 0 and invite.uses >= invite.max_uses:
        flash('Приглашение использовано максимальное число раз', 'danger')
        return redirect(url_for('index'))
    
    if not current_user.is_authenticated:
        flash('Сначала войдите в аккаунт', 'info')
        return redirect(url_for('login'))
    
    if user_in_server(invite.server_id, current_user.id):
        flash('Вы уже на этом сервере', 'info')
        return redirect(url_for('app_page', view='server', server_id=invite.server_id))
    
    invite.uses += 1
    member = ServerMember(server_id=invite.server_id, user_id=current_user.id, role='member')
    db.session.add(member)
    db.session.commit()
    
    if invite.role_id:
        member_role = ServerMemberRole(server_member_id=member.id, role_id=invite.role_id)
        db.session.add(member_role)
        db.session.commit()
    
    return redirect(url_for('app_page', view='server', server_id=invite.server_id))


@app.route('/api/servers/<int:server_id>/invites', methods=['POST'])
@login_required
def create_invite(server_id):
    if not user_in_server(server_id, current_user.id):
        return jsonify({'success': False, 'message': 'Нет доступа к серверу'}), 403
    server = Server.query.get(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Сервер не найден'}), 404
    
    invites_count = Invite.query.filter_by(server_id=server_id).count()
    if invites_count >= 50:
        return jsonify({'success': False, 'message': 'Достигнут лимит инвайтов (50)'}), 400
    
    data = request.get_json() or {}
    max_uses = parse_int(data.get('max_uses', 0)) or 0
    expires_hours = parse_int(data.get('expires_hours', 0)) or 0
    role_id = parse_int(data.get('role_id'))
    
    code = generate_invite_code()
    while Invite.query.filter_by(code=code).first():
        code = generate_invite_code()
    
    expires_at = None
    if expires_hours > 0:
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    invite = Invite(
        code=code,
        server_id=server_id,
        inviter_id=current_user.id,
        role_id=role_id,
        max_uses=max_uses,
        expires_at=expires_at
    )
    db.session.add(invite)
    db.session.commit()
    
    ensure_default_server_role(server)
    
    return jsonify({
        'success': True,
        'invite': {
            'code': invite.code,
            'url': f'https://bubble.gg/{invite.code}'
        }
    })


@app.route('/api/servers/<int:server_id>/channels', methods=['POST'])
@login_required
def create_channel(server_id):
    if not user_in_server(server_id, current_user.id):
        return jsonify({'success': False, 'message': 'Нет доступа к серверу'}), 403
    server = Server.query.get(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Сервер не найден'}), 404
    
    data = request.get_json() or {}
    name = data.get('name', '').strip().lower()
    channel_type = data.get('type', 'text').strip().lower()
    if not name:
        return jsonify({'success': False, 'message': 'Введите название канала'}), 400
    if channel_type not in {'text', 'voice'}:
        return jsonify({'success': False, 'message': 'Неверный тип канала'}), 400
    existing = Channel.query.filter_by(server_id=server.id, name=name).first()
    if existing:
        return jsonify({'success': False, 'message': 'Канал с таким именем уже существует'}), 400
    last_channel = server.channels.order_by(Channel.position.desc()).first()
    next_position = last_channel.position + 1 if last_channel else 0
    channel = Channel(server_id=server.id, name=name, type=channel_type, position=next_position)
    db.session.add(channel)
    db.session.commit()
    return jsonify({
        'success': True,
        'channel': {'id': channel.id, 'name': channel.name, 'type': channel.type},
        'redirect_url': url_for('app_page', view='server', server_id=server.id, channel_id=channel.id)
    })


@app.route('/api/servers/<int:server_id>', methods=['PUT'])
@login_required
def update_server(server_id):
    server = Server.query.get(server_id)
    if not server or server.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    data = request.get_json() or {}
    if 'name' in data and data['name'].strip():
        server.name = data['name'].strip()
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    if user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    data = request.get_json() or {}
    if 'status' in data:
        current_user.status = data['status']
    db.session.commit()
    return jsonify({'success': True})


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('app_page'))
    return render_template('index.html')


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/app')
@login_required
def app_page():
    search_query = request.args.get('q', '').strip()
    requested_chat_id = parse_int(request.args.get('chat_id'))
    requested_group_id = parse_int(request.args.get('group_id'))
    selected_dm = None
    selected_dm_user = None
    selected_group = None
    active_messages = []
    active_room_kind = None
    active_room_id = None
    composer_placeholder = 'Напишите сообщение...'
    composer_enabled = False
    dm_entries = build_dm_entries(current_user)
    group_entries = build_group_entries(current_user)

    all_entries = []
    for entry in dm_entries:
        all_entries.append({
            'type': 'dm',
            'dm': entry['dm'],
            'user': entry['user'],
            'last_message': entry['last_message'],
            'last_activity': entry['last_activity'],
        })
    all_entries.extend(group_entries)
    all_entries.sort(key=lambda x: x['last_activity'], reverse=True)

    if requested_group_id:
        selected_group = GroupConversation.query.get(requested_group_id)
        if not selected_group:
            selected_group = None
        else:
            is_member = GroupMember.query.filter_by(group_id=selected_group.id, user_id=current_user.id).first()
            if not is_member:
                selected_group = None

    if requested_chat_id and not selected_group:
        selected_dm = db.session.get(DMConversation, requested_chat_id)
        if not selected_dm or current_user.id not in {selected_dm.user1_id, selected_dm.user2_id}:
            selected_dm = None

    if not selected_dm and not selected_group and all_entries:
        first_entry = all_entries[0]
        if first_entry['type'] == 'dm':
            selected_dm = first_entry['dm']
        else:
            selected_group = first_entry['group']

    if selected_dm:
        selected_dm_user = selected_dm.user1 if selected_dm.user1_id != current_user.id else selected_dm.user2
        active_messages = DMMessage.query.filter_by(conversation_id=selected_dm.id).order_by(DMMessage.created_at.asc()).all()
        active_room_kind = 'dm'
        active_room_id = selected_dm.id
        composer_placeholder = f'Сообщение для {get_user_display_name(selected_dm_user)}'
        composer_enabled = True
    elif selected_group:
        active_messages = GroupMessage.query.filter_by(group_id=selected_group.id).order_by(GroupMessage.created_at.asc()).all()
        active_room_kind = 'group'
        active_room_id = selected_group.id
        composer_placeholder = f'Сообщение в {selected_group.name or "группе"}'
        composer_enabled = True

    search_results = []
    if search_query:
        search_results = User.query.filter(
            User.id != current_user.id,
            build_user_search_filter(search_query)
        ).order_by(User.display_name.asc(), User.username.asc()).limit(12).all()

    return render_template(
        'app.html',
        dm_entries=all_entries,
        selected_dm=selected_dm,
        selected_dm_user=selected_dm_user,
        selected_group=selected_group,
        active_messages=active_messages,
        active_room_kind=active_room_kind,
        active_room_id=active_room_id,
        composer_placeholder=composer_placeholder,
        composer_enabled=composer_enabled,
        search_query=search_query,
        search_results=search_results,
    )


@app.route('/api/groups', methods=['POST'])
@login_required
def create_group():
    data = request.get_json() or {}
    name = data.get('name', '').strip() or 'Новая группа'
    member_usernames = data.get('members', [])

    group = GroupConversation(name=name, owner_id=current_user.id)
    db.session.add(group)
    db.session.commit()

    db.session.add(GroupMember(group_id=group.id, user_id=current_user.id))

    for username in member_usernames:
        user = User.query.filter_by(username=username).first()
        if user and user.id != current_user.id:
            db.session.add(GroupMember(group_id=group.id, user_id=user.id))

    db.session.commit()

    for member in get_group_members(group.id):
        socketio.emit('new_chat', {
            'type': 'group',
            'group_id': group.id,
            'name': group.name
        }, room=user_room(member.user_id))

    return jsonify({
        'success': True,
        'group': {
            'id': group.id,
            'name': group.name
        },
        'redirect_url': url_for('app_page', group_id=group.id)
    })


@app.route('/api/users/profile/<username>', methods=['GET'])
@login_required
def get_user_profile_by_username(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    return jsonify({
        'success': True,
        'user': serialize_user_profile(user, is_me=(user.id == current_user.id))
    })


@app.route('/api/users/<int:user_id>/profile')
@login_required
def get_user_profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    return jsonify({
        'success': True,
        'user': serialize_user_profile(user, is_me=(user.id == current_user.id))
    })


@app.route('/api/users/profile', methods=['PUT'])
@login_required
def update_user_profile():
    data = request.get_json() or {}
    display_name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip()
    about = (data.get('bio') or '').strip()
    avatar = (data.get('avatar') or '').strip()

    if not display_name:
        return jsonify({'success': False, 'message': 'Введите имя'}), 400
    if not username:
        return jsonify({'success': False, 'message': 'Введите username'}), 400

    existing_user = User.query.filter(User.username == username, User.id != current_user.id).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'Этот username уже занят'}), 400

    current_user.display_name = display_name[:80]
    current_user.username = username[:80]
    current_user.about = about[:255]
    current_user.avatar = avatar[:255] if avatar else None
    db.session.commit()

    return jsonify({
        'success': True,
        'user': serialize_user_profile(current_user, is_me=True)
    })


@app.route('/api/groups/<int:group_id>', methods=['PUT'])
@login_required
def update_group(group_id):
    group = GroupConversation.query.get(group_id)
    if not group:
        return jsonify({'success': False, 'message': 'Группа не найдена'}), 404
    if group.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Только создатель может изменять группу'}), 403

    data = request.get_json() or {}
    if 'name' in data:
        group.name = data['name'].strip()
    db.session.commit()

    for member in get_group_members(group.id):
        socketio.emit('chat_updated', {
            'type': 'group',
            'group_id': group.id,
            'name': group.name
        }, room=user_room(member.user_id))

    return jsonify({'success': True})


@app.route('/api/groups/<int:group_id>/members', methods=['POST'])
@login_required
def add_group_member(group_id):
    group = GroupConversation.query.get(group_id)
    if not group:
        return jsonify({'success': False, 'message': 'Группа не найдена'}), 404
    if group.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Только создатель может добавлять участников'}), 403

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

    existing = GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Пользователь уже в группе'}), 400

    db.session.add(GroupMember(group_id=group.id, user_id=user.id))
    db.session.commit()

    socketio.emit('new_chat', {
        'type': 'group',
        'group_id': group.id,
        'name': group.name
    }, room=user_room(user.id))

    for member in get_group_members(group.id):
        socketio.emit('chat_updated', {
            'type': 'group',
            'group_id': group.id,
            'name': group.name
        }, room=user_room(member.user_id))

    return jsonify({'success': True})


@app.route('/api/messages/dm/<int:message_id>', methods=['DELETE'])
@login_required
def delete_dm_message(message_id):
    message = DMMessage.query.get(message_id)
    if not message:
        return jsonify({'success': False, 'message': 'Сообщение не найдено'}), 404
    if message.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403

    conversation = message.conversation
    db.session.delete(message)
    db.session.commit()

    socketio.emit('delete_message', {
        'room_kind': 'dm',
        'room_id': conversation.id,
        'message_id': message.id
    }, room=dm_room(conversation.id))

    return jsonify({'success': True})


@app.route('/api/messages/group/<int:message_id>', methods=['DELETE'])
@login_required
def delete_group_message(message_id):
    message = GroupMessage.query.get(message_id)
    if not message:
        return jsonify({'success': False, 'message': 'Сообщение не найдено'}), 404
    group = GroupConversation.query.get(message.group_id)
    if message.user_id != current_user.id and group.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403

    db.session.delete(message)
    db.session.commit()

    socketio.emit('delete_message', {
        'room_kind': 'group',
        'room_id': group.id,
        'message_id': message.id
    }, room=group_room(group.id))

    return jsonify({'success': True})


@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Нет файла'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f'{secrets.token_hex(16)}_{filename}'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        file_size = os.path.getsize(file_path)

        attachment = FileAttachment(
            filename=unique_filename,
            original_filename=filename,
            mime_type=file.content_type,
            size=file_size,
            uploaded_by=current_user.id
        )
        db.session.add(attachment)
        db.session.commit()

        return jsonify({
            'success': True,
            'file': {
                'id': attachment.id,
                'url': url_for('uploaded_file', filename=unique_filename),
                'name': filename,
                'size': file_size,
                'mime_type': file.content_type
            }
        })
    return jsonify({'success': False, 'message': 'Недопустимый тип файла'}), 400


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('register.html')
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    if not username or not password:
        flash('Заполните все поля', 'danger')
        return redirect(url_for('register'))
    if password != confirm_password:
        flash('Пароли не совпадают', 'danger')
        return redirect(url_for('register'))
    if User.query.filter_by(username=username).first():
        flash('Пользователь с таким именем уже существует', 'danger')
        return redirect(url_for('register'))
    if email and User.query.filter_by(email=email).first():
        flash('Email уже используется', 'danger')
        return redirect(url_for('register'))
    user = User(
        username=username,
        display_name=username,
        email=email if email else None,
        password_hash=generate_password_hash(password)
    )
    db.session.add(user)
    db.session.commit()
    flash('Регистрация успешно завершена! Теперь вы можете войти.', 'success')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('login.html')
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        flash('Неверный логин или пароль', 'danger')
        return redirect(url_for('login'))
    user.is_online = True
    user.last_online = datetime.utcnow()
    db.session.commit()
    login_user(user)
    return redirect(url_for('app_page'))


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_online = datetime.utcnow()
        db.session.commit()
        logout_user()
    return redirect(url_for('index'))


@app.route('/api/users/search')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': True, 'users': []})
    users = User.query.filter(
        User.id != current_user.id,
        build_user_search_filter(query)
    ).order_by(User.display_name.asc(), User.username.asc()).limit(12).all()
    return jsonify({
        'success': True,
        'users': [{
            'id': user.id,
            'name': get_user_display_name(user),
            'username': user.username,
            'about': user.about or '',
            'status': user.status or ('online' if user.is_online else 'offline'),
            'is_online': user.is_online,
            'avatar': user.avatar or '',
        } for user in users]
    })


@app.route('/api/chats/open', methods=['POST'])
@login_required
def open_chat():
    data = request.get_json() or {}
    query = (data.get('username') or data.get('query') or '').strip()
    if not query:
        return jsonify({'success': False, 'message': 'Введите имя или username'}), 400
    user = User.query.filter(User.username == query).first()
    if not user:
        user = User.query.filter(User.display_name == query).first()
    if not user:
        user = User.query.filter(
            User.id != current_user.id,
            build_user_search_filter(query)
        ).order_by(User.display_name.asc(), User.username.asc()).first()
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Нельзя открыть чат с самим собой'}), 400
    conversation = ensure_dm_with_user(current_user.id, user.id)
    return jsonify({
        'success': True,
        'chat': {
            'id': conversation.id,
            'username': user.username,
            'name': get_user_display_name(user),
        },
        'redirect_url': url_for('app_page', chat_id=conversation.id)
    })


@app.route('/api/servers', methods=['POST'])
@login_required
def create_server():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Введите название сервера'}), 400
    server = Server(name=name, owner_id=current_user.id)
    db.session.add(server)
    db.session.commit()
    db.session.add(ServerMember(server_id=server.id, user_id=current_user.id, role='owner'))
    text_channel = Channel(server_id=server.id, name='общий', type='text', position=0)
    voice_channel = Channel(server_id=server.id, name='голосовой', type='voice', position=1)
    db.session.add(text_channel)
    db.session.add(voice_channel)
    db.session.commit()
    return jsonify({
        'success': True,
        'server': {'id': server.id, 'name': server.name},
        'redirect_url': url_for('app_page', view='server', server_id=server.id, channel_id=text_channel.id)
    })





@app.route('/api/friends', methods=['POST'])
@login_required
def send_friend_request():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'message': 'Введите имя пользователя'}), 400
    if username == current_user.username:
        return jsonify({'success': False, 'message': 'Нельзя добавить себя в друзья'}), 400
    friend = User.query.filter_by(username=username).first()
    if not friend:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    existing = Friendship.query.filter(
        or_(
            and_(Friendship.user_id == current_user.id, Friendship.friend_id == friend.id),
            and_(Friendship.user_id == friend.id, Friendship.friend_id == current_user.id)
        )
    ).first()
    if existing:
        if existing.status == 'accepted':
            return jsonify({'success': False, 'message': 'Этот пользователь уже у вас в друзьях'}), 400
        return jsonify({'success': False, 'message': 'Запрос уже существует'}), 400
    friendship = Friendship(user_id=current_user.id, friend_id=friend.id, status='pending')
    db.session.add(friendship)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/friends/<int:friendship_id>/accept', methods=['POST'])
@login_required
def accept_friend_request(friendship_id):
    friendship = Friendship.query.get(friendship_id)
    if not friendship:
        return jsonify({'success': False, 'message': 'Запрос не найден'}), 404
    if friendship.friend_id != current_user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    friendship.status = 'accepted'
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/friends/<int:friendship_id>/decline', methods=['POST'])
@login_required
def decline_friend_request(friendship_id):
    friendship = Friendship.query.get(friendship_id)
    if not friendship:
        return jsonify({'success': False, 'message': 'Запрос не найден'}), 404
    if friendship.friend_id != current_user.id and friendship.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    db.session.delete(friendship)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/messages/channel/<int:channel_id>')
@login_required
def get_channel_messages(channel_id):
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({'success': False, 'message': 'Канал не найден'}), 404
    if not user_in_server(channel.server_id, current_user.id):
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    messages = Message.query.filter_by(channel_id=channel.id).order_by(Message.created_at.asc()).all()
    return jsonify({
        'success': True,
        'messages': [{
            'id': message.id,
            'username': message.user.username,
            'name': get_user_display_name(message.user),
            'user_id': message.user.id,
            'content': message.content,
            'created_at': message.created_at.isoformat()
        } for message in messages]
    })


@app.route('/api/messages/dm/<int:dm_id>')
@login_required
def get_dm_messages(dm_id):
    conversation = DMConversation.query.get(dm_id)
    if not conversation:
        return jsonify({'success': False, 'message': 'Диалог не найден'}), 404
    if current_user.id not in {conversation.user1_id, conversation.user2_id}:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    messages = DMMessage.query.filter_by(conversation_id=conversation.id).order_by(DMMessage.created_at.asc()).all()
    return jsonify({
        'success': True,
        'messages': [{
            'id': message.id,
            'username': message.user.username,
            'name': get_user_display_name(message.user),
            'user_id': message.user.id,
            'content': message.content,
            'created_at': message.created_at.isoformat()
        } for message in messages]
    })


@socketio.on('connect')
def on_connect():
    if current_user.is_authenticated:
        join_room(user_room(current_user.id))


@socketio.on('join_room')
def on_join_room(data):
    room = (data or {}).get('room')
    if room:
        join_room(room)


@socketio.on('leave_room')
def on_leave_room(data):
    room = (data or {}).get('room')
    if room:
        leave_room(room)


@socketio.on('send_message')
def handle_send_message(data):
    if not current_user.is_authenticated:
        return
    room_kind = (data or {}).get('room_kind')
    room_id = parse_int((data or {}).get('room_id'))
    content = ((data or {}).get('content') or '').strip()
    reply_to_id = parse_int((data or {}).get('reply_to_id'))
    if not room_kind or not room_id or not content:
        return
    if len(content) > MAX_MESSAGE_LENGTH:
        emit('message_error', {'message': f'Сообщение не должно превышать {MAX_MESSAGE_LENGTH} символов'})
        return
    if room_kind == 'channel':
        channel = Channel.query.get(room_id)
        if not channel or channel.type != 'text' or not user_in_server(channel.server_id, current_user.id):
            return
        message = Message(channel_id=channel.id, user_id=current_user.id, content=content)
        db.session.add(message)
        db.session.commit()
        emit('new_message', {
            'room_kind': 'channel',
            'room_id': channel.id,
            'username': current_user.username,
            'name': get_user_display_name(current_user),
            'user_id': current_user.id,
            'avatar': current_user.avatar or '',
            'content': message.content,
            'created_at': message.created_at.isoformat()
        }, room=channel_room(channel.id))
        return
    if room_kind == 'dm':
        conversation = DMConversation.query.get(room_id)
        if not conversation or current_user.id not in {conversation.user1_id, conversation.user2_id}:
            return
        message = DMMessage(conversation_id=conversation.id, user_id=current_user.id, content=content, reply_to_id=reply_to_id)
        db.session.add(message)
        db.session.commit()
        reply_content = None
        if reply_to_id:
            reply_msg = DMMessage.query.get(reply_to_id)
            if reply_msg:
                reply_content = reply_msg.content
        emit('new_message', {
            'room_kind': 'dm',
            'room_id': conversation.id,
            'message_id': message.id,
            'username': current_user.username,
            'name': get_user_display_name(current_user),
            'user_id': current_user.id,
            'avatar': current_user.avatar or '',
            'content': message.content,
            'reply_to_id': reply_to_id,
            'reply_content': reply_content,
            'created_at': message.created_at.isoformat()
        }, room=dm_room(conversation.id))

        other_user_id = conversation.user2_id if conversation.user1_id == current_user.id else conversation.user1_id
        socketio.emit('new_chat', {
            'type': 'dm',
            'dm_id': conversation.id,
            'username': current_user.username,
            'name': get_user_display_name(current_user)
        }, room=user_room(other_user_id))
        return
    if room_kind == 'group':
        group = GroupConversation.query.get(room_id)
        if not group:
            return
        is_member = GroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        if not is_member:
            return
        message = GroupMessage(group_id=group.id, user_id=current_user.id, content=content, reply_to_id=reply_to_id)
        db.session.add(message)
        db.session.commit()
        reply_content = None
        if reply_to_id:
            reply_msg = GroupMessage.query.get(reply_to_id)
            if reply_msg:
                reply_content = reply_msg.content
        emit('new_message', {
            'room_kind': 'group',
            'room_id': group.id,
            'message_id': message.id,
            'username': current_user.username,
            'name': get_user_display_name(current_user),
            'user_id': current_user.id,
            'avatar': current_user.avatar or '',
            'content': message.content,
            'reply_to_id': reply_to_id,
            'reply_content': reply_content,
            'created_at': message.created_at.isoformat()
        }, room=group_room(group.id))

        for member in get_group_members(group.id):
            if member.user_id != current_user.id:
                socketio.emit('new_chat', {
                    'type': 'group',
                    'group_id': group.id,
                    'name': group.name
                }, room=user_room(member.user_id))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_schema()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
