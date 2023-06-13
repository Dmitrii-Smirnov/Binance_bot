from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
sock = SocketIO(app)


if __name__ == "__main__":
    sock.run(app, debug=True, port=5123)
