from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os

app = Flask(__name__)
DB = "tutordao.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS tutors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                subject TEXT NOT NULL,
                bio TEXT,
                hourly_rate REAL DEFAULT 20.0,
                rating REAL DEFAULT 0.0,
                total_sessions INTEGER DEFAULT 0,
                verified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tutor_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                student_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                platform_fee REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tutor_id) REFERENCES tutors(id)
            );
        """)
        count = db.execute("SELECT COUNT(*) FROM tutors").fetchone()[0]
        if count == 0:
            demo_tutors = [
                ("Alex Johnson", "alex@demo.com", "Python & Machine Learning", "CS student with 2 years tutoring experience. Helped 30+ students pass their exams.", 25.0, 4.8, 42, 1),
                ("Maria Chen", "maria@demo.com", "Mathematics & Statistics", "Math major who loves breaking down complex problems into simple steps.", 20.0, 4.6, 28, 1),
                ("James Okafor", "james@demo.com", "Web Development (HTML/CSS/JS)", "Self-taught dev who built 5 real projects. I teach the way I wish I was taught.", 22.0, 4.9, 55, 1),
                ("Priya Sharma", "priya@demo.com", "Biology & Chemistry", "Pre-med student, top of my class. Patient and clear explanations guaranteed.", 18.0, 4.5, 19, 0),
                ("Tom Willis", "tom@demo.com", "English & Essay Writing", "English Lit student. I've helped students improve grades by a full letter in one month.", 15.0, 4.7, 33, 0),
            ]
            db.executemany("INSERT INTO tutors (name, email, subject, bio, hourly_rate, rating, total_sessions, verified) VALUES (?,?,?,?,?,?,?,?)", demo_tutors)
            db.commit()

init_db()

SUBJECT_KEYWORDS = {
    "Python & Machine Learning": ["python", "ml", "ai", "machine learning", "data", "scikit", "numpy", "pandas", "code", "programming"],
    "Mathematics & Statistics": ["math", "maths", "algebra", "calculus", "stats", "statistics", "numbers", "equations"],
    "Web Development (HTML/CSS/JS)": ["html", "css", "javascript", "web", "website", "frontend", "js", "design"],
    "Biology & Chemistry": ["biology", "bio", "chemistry", "chem", "science", "cells", "organic", "lab"],
    "English & Essay Writing": ["english", "essay", "writing", "grammar", "literature", "lit", "reading", "words","text"],
}

def ai_suggest_subject(question):
    question = question.lower()
    scores = {subject: 0 for subject in SUBJECT_KEYWORDS}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in question:
                scores[subject] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None

@app.route("/")
def index():
    db = get_db()
    tutors = db.execute("SELECT * FROM tutors ORDER BY rating DESC").fetchall()
    stats = {
        "tutors": db.execute("SELECT COUNT(*) FROM tutors").fetchone()[0],
        "bookings": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
        "subjects": len(SUBJECT_KEYWORDS),
    }
    return render_template("index.html", tutors=tutors, stats=stats)

@app.route("/tutors")
def tutors():
    db = get_db()
    subject_filter = request.args.get("subject", "")
    if subject_filter:
        all_tutors = db.execute("SELECT * FROM tutors WHERE subject LIKE ? ORDER BY rating DESC", (f"%{subject_filter}%",)).fetchall()
    else:
        all_tutors = db.execute("SELECT * FROM tutors ORDER BY rating DESC").fetchall()
    subjects = list(SUBJECT_KEYWORDS.keys())
    return render_template("tutors.html", tutors=all_tutors, subjects=subjects, selected=subject_filter)

@app.route("/tutor/<int:tutor_id>")
def tutor_profile(tutor_id):
    db = get_db()
    tutor = db.execute("SELECT * FROM tutors WHERE id=?", (tutor_id,)).fetchone()
    if not tutor:
        return redirect(url_for("tutors"))
    reviews = db.execute("SELECT * FROM bookings WHERE tutor_id=? ORDER BY created_at DESC LIMIT 5", (tutor_id,)).fetchall()
    return render_template("tutor_profile.html", tutor=tutor, reviews=reviews)

@app.route("/book/<int:tutor_id>", methods=["GET", "POST"])
def book(tutor_id):
    db = get_db()
    tutor = db.execute("SELECT * FROM tutors WHERE id=?", (tutor_id,)).fetchone()
    if not tutor:
        return redirect(url_for("tutors"))
    if request.method == "POST":
        fee = round(tutor["hourly_rate"] * 0.15, 2)
        db.execute("INSERT INTO bookings (tutor_id, student_name, student_email, subject, message, date, time, platform_fee) VALUES (?,?,?,?,?,?,?,?)",
            (tutor_id, request.form["name"], request.form["email"], request.form["subject"], request.form.get("message",""), request.form["date"], request.form["time"], fee))
        db.execute("UPDATE tutors SET total_sessions = total_sessions + 1 WHERE id=?", (tutor_id,))
        db.commit()
        return redirect(url_for("booking_success", tutor_name=tutor["name"]))
    return render_template("tutor_profile.html", tutor=tutor, reviews=[])

@app.route("/booking-success")
def booking_success():
    return render_template("success.html", tutor_name=request.args.get("tutor_name", "your tutor"))

@app.route("/register-tutor", methods=["GET", "POST"])
def register_tutor():
    db = get_db()
    error = None
    if request.method == "POST":
        try:
            db.execute("INSERT INTO tutors (name, email, subject, bio, hourly_rate) VALUES (?,?,?,?,?)",
                (request.form["name"], request.form["email"], request.form["subject"], request.form.get("bio",""), float(request.form.get("hourly_rate", 20))))
            db.commit()
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            error = "That email is already registered."
    return render_template("register_tutor.html", subjects=list(SUBJECT_KEYWORDS.keys()), error=error)

@app.route("/ai-match", methods=["POST"])
def ai_match():
    question = request.get_json().get("question", "")
    suggested = ai_suggest_subject(question)
    db = get_db()
    if suggested:
        tutors = db.execute("SELECT id, name, subject, rating, hourly_rate FROM tutors WHERE subject=? ORDER BY rating DESC LIMIT 3", (suggested,)).fetchall()
        return jsonify({"subject": suggested, "tutors": [dict(t) for t in tutors]})
    return jsonify({"subject": None, "tutors": []})

@app.route("/dashboard")
def dashboard():
    db = get_db()
    bookings = db.execute("SELECT b.*, t.name as tutor_name FROM bookings b JOIN tutors t ON b.tutor_id = t.id ORDER BY b.created_at DESC LIMIT 20").fetchall()
    revenue = db.execute("SELECT SUM(platform_fee) FROM bookings").fetchone()[0] or 0
    return render_template("dashboard.html", bookings=bookings, revenue=round(revenue,2),
        total_bookings=db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
        total_tutors=db.execute("SELECT COUNT(*) FROM tutors").fetchone()[0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
