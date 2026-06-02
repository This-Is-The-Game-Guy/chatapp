# v2
from flask import Flask
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML = open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html')).read()

@app.route("/")
def home():
    return HTML

@socketio.on("message")
def handle_message(data):
    emit("message", data, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)