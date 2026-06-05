from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
import os
import sqlite3
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

ADMIN_USERNAME = "Indian_IV"
online_users = set()

HTML = open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html')).read()
ADMIN_HTML = open(os.path.join(os.path.dirname(__file__), 'templates', 'admin.html')).read()

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
            avatar TEXT,
            banned INTEGER DEFAULT 0
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
    try:
        db.execute('ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0')
    except:
        pass
    db.commit()
    db.close()

init_db()

@app.route("/")
def home():
    return HTML

@app.route("/admin")
def admin():
    admin_key = request.args.get('key')
    if admin_key != os.environ.get('ADMIN_KEY', 'supersecret'):
        return "403 Forbidden", 403
    return ADMIN_HTML

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
        INSERT INTO users (username, password, bio, status, avatar, banned)
        VALUES (?, ?, ?, ?, ?, 0)
    ''', (username, hashed, data.get('bio', ''), data.get('status', 'online'), data.get('avatar', f'https://api.dicebear.com/7.x/bottts/svg?seed={username}')))
    db.commit()
    db.close()
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
    if user['banned']:
        return jsonify({"success": False, "error": "You have been banned from this chat."})
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
    db.execute('UPDATE users SET bio=?, status=?, avatar=? WHERE username=?',
               (data['bio'], data['status'], data['avatar'], data['username']))
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

@app.route("/online", methods=["GET"])
def get_online():
    return jsonify({"count": len(online_users), "users": list(online_users)})

@app.route("/ai", methods=["POST"])
def ai_chat():
    data = request.json
    messages = data.get('messages', [])
    personality = data.get('personality', 'You are a helpful assistant.')
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": personality}] + messages
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

@app.route("/admin/users", methods=["GET"])
def admin_users():
    if request.args.get('key') != os.environ.get('ADMIN_KEY', 'supersecret'):
        return jsonify({"error": "Forbidden"}), 403
    db = get_db()
    users = db.execute('SELECT username, bio, status, banned FROM users').fetchall()
    db.close()
    return jsonify([dict(u) for u in users])

@app.route("/admin/messages", methods=["GET"])
def admin_messages():
    if request.args.get('key') != os.environ.get('ADMIN_KEY', 'supersecret'):
        return jsonify({"error": "Forbidden"}), 403
    db = get_db()
    msgs = db.execute('SELECT * FROM messages ORDER BY timestamp DESC LIMIT 100').fetchall()
    db.close()
    return jsonify([dict(m) for m in msgs])

@app.route("/admin/ban", methods=["POST"])
def admin_ban():
    if request.json.get('key') != os.environ.get('ADMIN_KEY', 'supersecret'):
        return jsonify({"error": "Forbidden"}), 403
    username = request.json.get('username')
    db = get_db()
    db.execute('UPDATE users SET banned=1 WHERE username=?', (username,))
    db.commit()
    db.close()
    socketio.emit('kicked', {'username': username})
    return jsonify({"success": True})

@app.route("/admin/unban", methods=["POST"])
def admin_unban():
    if request.json.get('key') != os.environ.get('ADMIN_KEY', 'supersecret'):
        return jsonify({"error": "Forbidden"}), 403
    username = request.json.get('username')
    db = get_db()
    db.execute('UPDATE users SET banned=0 WHERE username=?', (username,))
    db.commit()
    db.close()
    return jsonify({"success": True})

@app.route("/admin/kick", methods=["POST"])
def admin_kick():
    if request.json.get('key') != os.environ.get('ADMIN_KEY', 'supersecret'):
        return jsonify({"error": "Forbidden"}), 403
    username = request.json.get('username')
    socketio.emit('kicked', {'username': username})
    return jsonify({"success": True})

@app.route("/admin/delete_message", methods=["POST"])
def admin_delete_message():
    if request.json.get('key') != os.environ.get('ADMIN_KEY', 'supersecret'):
        return jsonify({"error": "Forbidden"}), 403
    msg_id = request.json.get('id')
    db = get_db()
    db.execute('DELETE FROM messages WHERE id=?', (msg_id,))
    db.commit()
    db.close()
    socketio.emit('message_deleted', {'id': msg_id})
    return jsonify({"success": True})

@socketio.on("join")
def handle_join(data):
    username = data.get('username')
    if username:
        online_users.add(username)
        socketio.emit('online_update', {'count': len(online_users), 'users': list(online_users)})

@socketio.on("disconnect")
def handle_disconnect():
    to_remove = None
    for u in online_users:
        to_remove = u
        break
    if to_remove:
        online_users.discard(to_remove)
        socketio.emit('online_update', {'count': len(online_users), 'users': list(online_users)})

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