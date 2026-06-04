from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import os
import sqlite3
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML = open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html')).read()

# Database setup
def get_db():
    db = sqlite3.connect('chat.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            username TEXT PRIMARY KEY,
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

# Save profile
@app.route("/profile", methods=["POST"])
def save_profile():
    data = request.json
    db = get_db()
    db.execute('''
        INSERT INTO profiles (username, bio, status, avatar)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            bio=excluded.bio,
            status=excluded.status,
            avatar=excluded.avatar
    ''', (data['username'], data['bio'], data['status'], data['avatar']))
    db.commit()
    db.close()
    return jsonify({"success": True})

# Load profile
@app.route("/profile/<username>", methods=["GET"])
def load_profile(username):
    db = get_db()
    profile = db.execute('SELECT * FROM profiles WHERE username = ?', (username,)).fetchone()
    db.close()
    if profile:
        return jsonify(dict(profile))
    return jsonify(None)

# Load recent messages
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