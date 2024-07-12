# pip install flask
# pip install flask-socketio
from flask import Flask, render_template, request, session, url_for, redirect, jsonify
from flask_socketio import join_room, leave_room, send, SocketIO
from datetime import datetime
import random
import string

app = Flask(__name__)

socketio = SocketIO(app)
app.config["SECRET_KEY"] = "234d334ddas534"

rooms = {}


def make_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(string.ascii_uppercase + string.digits)
        if code not in rooms:
            break
    return code


@app.route("/", methods=["POST", "GET"])
def home():
    if request.method == "GET":
        session.clear()

    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template(
                "index.html", error="Please enter your name", code=code, name=name
            )
        if join != False and not code:
            return render_template(
                "index.html", error="Please enter a room code.", code=code, name=name
            )

        room = code
        if create != False:
            room = make_code(5)
            room_name = request.form.get("room_name", f"Room {room}")
            room_description = request.form.get("room_description", "")
            is_private = request.form.get("is_private") == "on"
            theme = request.form.get("theme", "dark")
            rooms[room] = {
                "members": 0,
                "messages": [],
                "name": room_name,
                "description": room_description,
                "is_private": is_private,
                "user_names": set(),
                "theme": theme,
            }
        elif code not in rooms:
            return render_template(
                "index.html", error="Room does not exist.", code=code, name=name
            )

        if name in rooms[room]["user_names"]:
            return render_template(
                "index.html",
                error="This name is taken, choose another.",
                code=code,
                name=name,
            )

        session["room"] = room
        session["name"] = name
        session["theme"] = rooms[room]["theme"]
        return redirect(url_for("room"))

    public_rooms = {
        code: room for code, room in rooms.items() if not room["is_private"]
    }
    return render_template("index.html", public_rooms=public_rooms)


@app.route("/get_public_rooms")
def get_public_rooms():
    try:
        public_rooms = {}
        for code, room in rooms.items():
            if not room["is_private"]:
                room_copy = room.copy()
                room_copy["user_names"] = list(room_copy["user_names"])
                public_rooms[code] = room_copy
        return jsonify(public_rooms)
    except Exception as e:
        app.logger.error(f"Error in get_public_rooms: {str(e)}")
        return jsonify({"error": "An error occurred while fetching rooms"}), 500


@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    return render_template("room.html", code=room, messages=[])


@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    content = {
        "name": session.get("name"),
        "message": data["data"],
        "isCode": data.get("isCode", False),
        "timestamp": datetime.now().isoformat(),
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)

    log_message = "[CODE BLOCK]" if content["isCode"] else content["message"]
    print(f"{session.get('name')} said: {log_message}")


@socketio.on("connect")
def connect():
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    if name in rooms[room]["user_names"]:
        socketio.emit(
            "redirect",
            {"message": "This name is taken, choose another."},
            to=request.sid,
        )
        return

    join_room(room)
    rooms[room]["members"] += 1
    rooms[room]["user_names"].add(name)

    socketio.emit("clear_messages", room=request.sid)

    for msg in rooms[room]["messages"]:
        socketio.emit("message", msg, to=request.sid)

    entry_message = {
        "name": name,
        "message": "has entered the room",
        "timestamp": datetime.now().isoformat(),
    }
    send(entry_message, to=room)
    rooms[room]["messages"].append(entry_message)

    print(f"{name} joined the room {room}")


@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        rooms[room]["user_names"].remove(name)
        if rooms[room]["members"] <= 0:
            del rooms[room]
        else:
            exit_message = {
                "name": name,
                "message": "has left the room",
                "timestamp": datetime.now().isoformat(),
            }
            send(exit_message, to=room)
            rooms[room]["messages"].append(exit_message)

    print(f"{name} has left the room {room}")


if __name__ == "__main__":
    socketio.run(app, host= "0.0.0.0", port = 3000, debug=True)
