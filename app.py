# v2
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import os
print("FILES:", os.listdir(os.path.dirname(__file__)))
print("TEMPLATES:", os.path.exists(os.path.join(os.path.dirname(__file__), 'templates')))

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
socketio = SocketIO(app, cors_allowed_origins="*")

messages = []

@app.route("/")
def home():
    return render_template("index.html")

@socketio.on("message")
def handle_message(data):
    messages.append(data)
    emit("message", data, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)