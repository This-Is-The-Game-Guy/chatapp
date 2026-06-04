from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML = open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html')).read()

def get_db():
    db = sqlite3.connect('chat.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            bio TEXT,
            status TEXT,
            avatar TEXT
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.commit()
    db.close()

init_db()

@app.route("/")
def home():
    return HTML

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"})
    db = get_db()
    existing = db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone()
    if existing:
        db.close()
        return jsonify({"success": False, "error": "Username already taken"})
    hashed = generate_password_hash(password)
    db.execute('''
        INSERT INTO users (username, password, bio, status, avatar)
        VALUES (?, ?, ?, ?, ?)
    ''', (username, hashed, data.get('bio', ''), data.get('status', 'online'), data.get('avatar', f'https://api.dicebear.com/7.x/bottts/svg?seed={username}')))
    db.commit()
    db.close()
    session['username'] = username
    return jsonify({"success": True})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    db.close()
    if not user or not check_password_hash(user['password'], password):
        return jsonify({"success": False, "error": "Wrong username or password"})
    session['username'] = username
    return jsonify({"success": True, "user": {
        "username": user['username'],
        "bio": user['bio'],
        "status": user['status'],
        "avatar": user['avatar']
    }})

@app.route("/profile", methods=["POST"])
def save_profile():
    data = request.json
    db = get_db()
    db.execute('''
        UPDATE users SET bio=?, status=?, avatar=? WHERE username=?
    ''', (data['bio'], data['status'], data['avatar'], data['username']))
    db.commit()
    db.close()
    return jsonify({"success": True})

@app.route("/profile/<username>", methods=["GET"])
def load_profile(username):
    db = get_db()
    user = db.execute('SELECT username, bio, status, avatar FROM users WHERE username = ?', (username,)).fetchone()
    db.close()
    if user:
        return jsonify(dict(user))
    return jsonify(None)

@app.route("/messages", methods=["GET"])
def get_messages():
    db = get_db()
    msgs = db.execute('SELECT * FROM messages ORDER BY timestamp DESC LIMIT 50').fetchall()
    db.close()
    return jsonify([dict(m) for m in reversed(msgs)])

@socketio.on("message")
def handle_message(data):
    if not data.get('system'):
        db = get_db()
        db.execute('INSERT INTO messages (username, content) VALUES (?, ?)',
                   (data['username'], data['content']))
        db.commit()
        db.close()
    emit("message", data, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)