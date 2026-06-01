from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

messages = []

@app.route("/")
def home():
    return render_template("index.html")

@socketio.on("message")
def handle_message(data):
    messages.append(data)
    emit("message", data, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)