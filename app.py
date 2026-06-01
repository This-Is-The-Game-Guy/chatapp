from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
socketio = SocketIO(app, async_mode='threading')

messages = []

@app.route("/")
def home():
    return render_template("index.html")

@socketio.on("message")
def handle_message(data):
    messages.append(data)
    emit("message", data, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)