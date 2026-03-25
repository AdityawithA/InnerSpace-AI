from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
from groq import Groq
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "test_secret_key"
CORS(app, supports_credentials=True)

@app.route("/")
def home():
    return render_template("index.html")

# 🔑 PUT YOUR NEW WORKING API KEY HERE
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ================= DB SETUP =================
def init_db():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    # users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # chats table
    c.execute("""
    CREATE TABLE IF NOT EXISTS chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        message TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ================= HELPERS =================
def save_message(user_id, role, message):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO chats (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, role, message)
    )

    conn.commit()
    conn.close()


def get_history(user_id):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute(
        "SELECT role, message FROM chats WHERE user_id=?",
        (user_id,)
    )

    rows = c.fetchall()
    conn.close()

    return rows


def safety_check(text):
    danger_words = [
        "suicide", "kill myself", "die",
        "end my life", "want to disappear"
    ]
    text = text.lower()
    return any(word in text for word in danger_words)


# ================= AUTH =================
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json

    try:
        conn = sqlite3.connect("chat.db")
        c = conn.cursor()

        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (data["username"], data["password"])
        )

        conn.commit()
        conn.close()

        return jsonify({"msg": "Signup successful"})

    except:
        return jsonify({"error": "User already exists"})


@app.route("/login", methods=["POST"])
def login():
    data = request.json

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute(
        "SELECT id FROM users WHERE username=? AND password=?",
        (data["username"], data["password"])
    )

    user = c.fetchone()
    conn.close()

    if user:
        session["user_id"] = user[0]
        return jsonify({"msg": "Login successful"})

    return jsonify({"error": "Invalid credentials"})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"msg": "Logged out"})


@app.route("/me", methods=["GET"])
def me():
    if "user_id" in session:
        return jsonify({"user_id": session["user_id"]})

    return jsonify({"error": "Not logged in"})


# ================= CHAT =================
@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return jsonify({"reply": "Please login first"})

    user_id = session["user_id"]
    user_input = request.json.get("message", "")

    if not user_input:
        return jsonify({"reply": "Say something..."})

    # 🚨 Safety
    if safety_check(user_input):
        return jsonify({
            "reply": "I'm really sorry you're feeling this way. Please talk to someone you trust ❤️"
        })

    # 💾 Save user message
    save_message(user_id, "user", user_input)

    # 🧠 AI call
    response = client.chat.completions.create(
       model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a kind emotional support AI. Keep responses short, natural, and supportive."
            },
            {
                "role": "user",
                "content": user_input
            }
        ],
        temperature=0.7
    )

    reply = response.choices[0].message.content

    # 💾 Save bot reply
    save_message(user_id, "bot", reply)

    return jsonify({"reply": reply})


# ================= HISTORY =================
@app.route("/history", methods=["GET"])
def history():
    if "user_id" not in session:
        return jsonify([])

    user_id = session["user_id"]

    data = get_history(user_id)

    return jsonify(data)


# ================= RUN =================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
