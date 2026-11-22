"""
MediRoute AI - Intelligent Healthcare Report Routing and Physician Assignment
M.Tech Research Prototype (Synthetic data only)
"""

import os
import sqlite3
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, g
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mediroute-ai-demo-secret-key-2026")

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediroute.db")

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
DEPARTMENTS = [
    "Cardiology", "Neurology", "Dermatology", "Orthopedics",
    "General Medicine", "Pediatrics", "Gynecology", "Other"
]

STATUSES = [
    "Assigned", "Pending Assignment", "Human Review Required",
    "Under Process", "Completed"
]

# Weighted keywords for department classification (keyword -> weight)
DEPT_KEYWORDS = {
    "Cardiology": {
        "heart": 5, "cardiac": 5, "chest pain": 5, "angina": 4,
        "palpitation": 4, "arrhythmia": 4, "ecg": 3, "myocardial": 5,
        "hypertension": 3, "blood pressure": 3, "coronary": 4,
        "tachycardia": 3, "bradycardia": 3, "murmur": 3
    },
    "Neurology": {
        "brain": 5, "headache": 4, "migraine": 4, "seizure": 5,
        "stroke": 5, "paralysis": 4, "numbness": 3, "dizziness": 3,
        "vertigo": 3, "epilepsy": 5, "neurological": 4, "memory loss": 3,
        "tremor": 3, "parkinson": 4, "alzheimer": 4, "nerve": 3
    },
    "Dermatology": {
        "skin": 5, "rash": 5, "itching": 4, "eczema": 4, "psoriasis": 4,
        "acne": 3, "dermatitis": 4, "lesion": 3, "mole": 3, "urticaria": 4,
        "hives": 3, "pigmentation": 3, "fungal": 3, "allergy skin": 3
    },
    "Orthopedics": {
        "bone": 5, "joint": 5, "fracture": 5, "sprain": 4, "arthritis": 4,
        "back pain": 4, "knee": 3, "shoulder": 3, "hip": 3, "spine": 4,
        "ligament": 3, "dislocation": 4, "orthopedic": 4, "musculoskeletal": 3
    },
    "General Medicine": {
        "fever": 4, "cough": 4, "cold": 3, "infection": 3, "fatigue": 3,
        "weakness": 3, "body pain": 3, "diabetes": 3, "thyroid": 3,
        "general checkup": 3, "viral": 3, "flu": 3, "sore throat": 3
    },
    "Pediatrics": {
        "child": 5, "infant": 5, "baby": 5, "pediatric": 5, "newborn": 5,
        "toddler": 4, "vaccination": 3, "growth": 3, "kids": 4, "children": 4
    },
    "Gynecology": {
        "pregnancy": 5, "pregnant": 5, "menstrual": 4, "gynecology": 5,
        "ovarian": 4, "uterus": 4, "prenatal": 4, "obstetric": 4,
        "vaginal": 3, "pcos": 4, "fertility": 3, "maternity": 4
    }
}

# Emergency indicator phrases (case-insensitive substring match)
EMERGENCY_TERMS = [
    "severe chest pain", "difficulty breathing", "shortness of breath",
    "unconscious", "unresponsive", "severe bleeding", "heavy bleeding",
    "stroke symptoms", "sudden paralysis", "facial droop", "slurred speech",
    "severe abdominal pain", "suicidal", "anaphylaxis", "cardiac arrest",
    "not breathing", "choking", "seizure ongoing", "status epilepticus"
]

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they do not exist."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,
            pending_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT UNIQUE NOT NULL,
            patient_name TEXT NOT NULL,
            description TEXT NOT NULL,
            department TEXT NOT NULL,
            matched_keywords TEXT,
            priority TEXT NOT NULL DEFAULT 'Normal',
            status TEXT NOT NULL,
            doctor_id TEXT,
            doctor_name TEXT,
            is_emergency INTEGER NOT NULL DEFAULT 0,
            emergency_keywords TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            activity TEXT NOT NULL,
            details TEXT,
            report_id TEXT
        );
    """)
    db.commit()


def log_activity(activity, details="", report_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO audit_logs (timestamp, activity, details, report_id) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), activity, details, report_id)
    )
    db.commit()


# ---------------------------------------------------------------------------
# Classification & Assignment Logic
# ---------------------------------------------------------------------------
def classify_department(text):
    """Weighted keyword scoring. Returns (department, list_of_matched_keywords)."""
    text_lower = text.lower()
    scores = {dept: 0 for dept in DEPARTMENTS}
    matched = {dept: [] for dept in DEPARTMENTS}

    for dept, keywords in DEPT_KEYWORDS.items():
        for kw, weight in keywords.items():
            if kw in text_lower:
                scores[dept] += weight
                matched[dept].append(kw)

    # Pick highest score; ties broken by first in DEPARTMENTS order
    best_dept = "Other"
    best_score = 0
    for dept in DEPARTMENTS:
        if scores[dept] > best_score:
            best_score = scores[dept]
            best_dept = dept

    return best_dept, matched.get(best_dept, [])


def screen_emergency(text):
    """Return (is_emergency: bool, matched_terms: list)."""
    text_lower = text.lower()
    found = [term for term in EMERGENCY_TERMS if term in text_lower]
    return len(found) > 0, found


def assign_doctor(department):
    """
    Least-pending-load assignment.
    Returns (doctor_id, doctor_name) or (None, None) if none available.
    """
    db = get_db()
    row = db.execute(
        """SELECT doctor_id, name, pending_count FROM doctors
           WHERE department = ? AND available = 1
           ORDER BY pending_count ASC, id ASC LIMIT 1""",
        (department,)
    ).fetchone()

    if row:
        db.execute(
            "UPDATE doctors SET pending_count = pending_count + 1 WHERE doctor_id = ?",
            (row["doctor_id"],)
        )
        db.commit()
        return row["doctor_id"], row["name"]
    return None, None


def generate_report_id():
    return "MR-" + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------
SAMPLE_DOCTORS = [
    ("DR-C01", "Dr. Ananya Reddy", "Cardiology", 1, 1),
    ("DR-C02", "Dr. Vikram Malhotra", "Cardiology", 1, 0),
    ("DR-N01", "Dr. Priya Nair", "Neurology", 1, 2),
    ("DR-N02", "Dr. Arjun Desai", "Neurology", 1, 0),
    ("DR-D01", "Dr. Sneha Kapoor", "Dermatology", 1, 1),
    ("DR-D02", "Dr. Rohan Mehta", "Dermatology", 0, 0),
    ("DR-O01", "Dr. Kavita Joshi", "Orthopedics", 1, 3),
    ("DR-O02", "Dr. Sameer Khan", "Orthopedics", 1, 1),
    ("DR-G01", "Dr. Meera Iyer", "General Medicine", 1, 2),
    ("DR-G02", "Dr. Farhan Ali", "General Medicine", 1, 0),
    ("DR-P01", "Dr. Lakshmi Rao", "Pediatrics", 1, 1),
    ("DR-P02", "Dr. Nikhil Sharma", "Pediatrics", 1, 0),
    ("DR-Y01", "Dr. Sunita Verma", "Gynecology", 1, 2),
    ("DR-Y02", "Dr. Aisha Begum", "Gynecology", 1, 0),
]

SAMPLE_REPORTS = [
    {
        "patient_name": "Ravi Kumar (Demo)",
        "description": "Patient complains of intermittent chest pain and mild palpitations for the past two days. ECG recommended.",
        "department": "Cardiology",
        "matched_keywords": "chest pain, palpitation",
        "priority": "Normal",
        "status": "Assigned",
        "doctor_id": "DR-C02",
        "doctor_name": "Dr. Vikram Malhotra",
        "is_emergency": 0,
        "emergency_keywords": ""
    },
    {
        "patient_name": "Sita Devi (Demo)",
        "description": "Severe headache with dizziness and occasional numbness in left arm. History of migraine.",
        "department": "Neurology",
        "matched_keywords": "headache, dizziness, numbness",
        "priority": "Normal",
        "status": "Under Process",
        "doctor_id": "DR-N02",
        "doctor_name": "Dr. Arjun Desai",
        "is_emergency": 0,
        "emergency_keywords": ""
    },
    {
        "patient_name": "Amit Patel (Demo)",
        "description": "Skin rash with intense itching on both arms for one week. Possible contact dermatitis.",
        "department": "Dermatology",
        "matched_keywords": "skin, rash, itching",
        "priority": "Normal",
        "status": "Completed",
        "doctor_id": "DR-D01",
        "doctor_name": "Dr. Sneha Kapoor",
        "is_emergency": 0,
        "emergency_keywords": ""
    },
    {
        "patient_name": "Emergency Demo Case",
        "description": "Patient brought with severe chest pain and difficulty breathing. Unresponsive initially.",
        "department": "Cardiology",
        "matched_keywords": "chest pain",
        "priority": "Emergency",
        "status": "Human Review Required",
        "doctor_id": None,
        "doctor_name": None,
        "is_emergency": 1,
        "emergency_keywords": "severe chest pain, difficulty breathing, unresponsive"
    },
]


def seed_sample_data(force=False):
    """Insert sample doctors and reports if tables are empty (or force=True)."""
    db = get_db()
    doc_count = db.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    rep_count = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

    if force or doc_count == 0:
        if force:
            db.execute("DELETE FROM doctors")
        for d in SAMPLE_DOCTORS:
            db.execute(
                "INSERT OR IGNORE INTO doctors (doctor_id, name, department, available, pending_count) VALUES (?,?,?,?,?)",
                d
            )
        log_activity("System", "Sample doctors loaded")

    if force or rep_count == 0:
        if force:
            db.execute("DELETE FROM reports")
            db.execute("DELETE FROM audit_logs")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in SAMPLE_REPORTS:
            rid = generate_report_id()
            db.execute(
                """INSERT INTO reports
                   (report_id, patient_name, description, department, matched_keywords,
                    priority, status, doctor_id, doctor_name, is_emergency, emergency_keywords, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, r["patient_name"], r["description"], r["department"], r["matched_keywords"],
                 r["priority"], r["status"], r["doctor_id"], r["doctor_name"],
                 r["is_emergency"], r["emergency_keywords"], now)
            )
            log_activity("Sample Data", f"Loaded demo report for {r['patient_name']}", rid)
        # Recalculate pending counts roughly
        db.execute("UPDATE doctors SET pending_count = 0")
        for d in SAMPLE_DOCTORS:
            db.execute(
                "UPDATE doctors SET pending_count = ? WHERE doctor_id = ?",
                (d[4], d[0])
            )
    db.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.before_request
def before_request():
    init_db()
    # Auto-seed on very first request if empty
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        seed_sample_data()


@app.route("/")
def dashboard():
    db = get_db()
    stats = {
        "total": db.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
        "processed": db.execute(
            "SELECT COUNT(*) FROM reports WHERE status IN ('Assigned','Under Process','Completed')"
        ).fetchone()[0],
        "emergency": db.execute(
            "SELECT COUNT(*) FROM reports WHERE is_emergency = 1"
        ).fetchone()[0],
        "pending": db.execute(
            "SELECT COUNT(*) FROM reports WHERE status IN ('Pending Assignment','Human Review Required')"
        ).fetchone()[0],
        "doctors": db.execute(
            "SELECT COUNT(*) FROM doctors WHERE available = 1"
        ).fetchone()[0],
    }
    recent = db.execute(
        "SELECT * FROM reports ORDER BY id DESC LIMIT 8"
    ).fetchall()
    return render_template("dashboard.html", stats=stats, recent_reports=recent)


@app.route("/submit", methods=["GET", "POST"])
def submit_report():
    result = None
    if request.method == "POST":
        patient_name = request.form.get("patient_name", "").strip()
        description = request.form.get("description", "").strip()

        # Validation
        if not patient_name:
            flash("Patient name is required.", "danger")
            return render_template("submit_report.html", departments=DEPARTMENTS)
        if len(description) < 20:
            flash("Description must be at least 20 characters.", "danger")
            return render_template("submit_report.html", departments=DEPARTMENTS)
        if len(description) > 4000:
            flash("Description must not exceed 4000 characters.", "danger")
            return render_template("submit_report.html", departments=DEPARTMENTS)

        # Simple duplicate prevention: same patient + same description hash in last 5 min
        db = get_db()
        recent_dup = db.execute(
            """SELECT report_id FROM reports
               WHERE patient_name = ? AND description = ?
               AND created_at > datetime('now', '-5 minutes')""",
            (patient_name, description)
        ).fetchone()
        if recent_dup:
            flash(f"Possible duplicate submission detected (recent report {recent_dup['report_id']}). Please wait a few minutes.", "warning")
            return render_template("submit_report.html", departments=DEPARTMENTS)

        report_id = generate_report_id()
        department, matched_kws = classify_department(description)
        is_emergency, emerg_kws = screen_emergency(description)

        priority = "Emergency" if is_emergency else "Normal"
        doctor_id = None
        doctor_name = None
        status = "Assigned"

        if is_emergency:
            status = "Human Review Required"
            log_activity("Emergency Flag", f"Matched: {', '.join(emerg_kws)}", report_id)
        else:
            doctor_id, doctor_name = assign_doctor(department)
            if doctor_id:
                status = "Assigned"
                log_activity("Doctor Assigned", f"{doctor_name} ({doctor_id}) – least pending load", report_id)
            else:
                status = "Pending Assignment"
                log_activity("Pending Assignment", f"No available doctor in {department}", report_id)

        log_activity("Report Submitted", f"Patient: {patient_name}", report_id)
        log_activity("Department Classification", f"{department} | keywords: {', '.join(matched_kws) or 'none'}", report_id)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """INSERT INTO reports
               (report_id, patient_name, description, department, matched_keywords,
                priority, status, doctor_id, doctor_name, is_emergency, emergency_keywords, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (report_id, patient_name, description, department, ", ".join(matched_kws),
             priority, status, doctor_id, doctor_name, 1 if is_emergency else 0,
             ", ".join(emerg_kws), now)
        )
        db.commit()

        result = {
            "report_id": report_id,
            "patient_name": patient_name,
            "department": department,
            "matched_keywords": matched_kws,
            "priority": priority,
            "status": status,
            "doctor_name": doctor_name,
            "is_emergency": is_emergency,
            "emergency_keywords": emerg_kws,
            "created_at": now
        }
        flash("Report submitted and routed successfully.", "success")

    return render_template("submit_report.html", departments=DEPARTMENTS, result=result)


@app.route("/reports")
def reports():
    db = get_db()
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    status = request.args.get("status", "").strip()

    sql = "SELECT * FROM reports WHERE 1=1"
    params = []
    if q:
        sql += " AND (patient_name LIKE ? OR report_id LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if department:
        sql += " AND department = ?"
        params.append(department)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"

    rows = db.execute(sql, params).fetchall()
    return render_template(
        "reports.html",
        reports=rows,
        departments=DEPARTMENTS,
        statuses=STATUSES,
        q=q,
        department=department,
        status=status
    )


@app.route("/update_status/<report_id>/<status>")
def update_status(report_id, status):
    if status not in ("Under Process", "Completed"):
        flash("Invalid status.", "danger")
        return redirect(url_for("reports"))

    db = get_db()
    row = db.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    if not row:
        flash("Report not found.", "danger")
        return redirect(url_for("reports"))

    if row["status"] == "Human Review Required":
        flash("Emergency-flagged reports require human review and cannot be auto-updated this way.", "warning")
        return redirect(url_for("reports"))

    db.execute(
        "UPDATE reports SET status = ?, updated_at = ? WHERE report_id = ?",
        (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), report_id)
    )
    # If completed, decrement doctor's pending count (if assigned)
    if status == "Completed" and row["doctor_id"]:
        db.execute(
            "UPDATE doctors SET pending_count = MAX(0, pending_count - 1) WHERE doctor_id = ?",
            (row["doctor_id"],)
        )
    db.commit()
    log_activity("Status Update", f"Changed to {status}", report_id)
    flash(f"Report {report_id} marked as {status}.", "success")
    return redirect(url_for("reports"))


@app.route("/reassign/<report_id>")
def reassign(report_id):
    db = get_db()
    row = db.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    if not row:
        flash("Report not found.", "danger")
        return redirect(url_for("reports"))

    if row["status"] != "Pending Assignment":
        flash("Only reports with Pending Assignment status can be reassigned.", "warning")
        return redirect(url_for("reports"))

    doctor_id, doctor_name = assign_doctor(row["department"])
    if doctor_id:
        db.execute(
            "UPDATE reports SET doctor_id=?, doctor_name=?, status=?, updated_at=? WHERE report_id=?",
            (doctor_id, doctor_name, "Assigned",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), report_id)
        )
        db.commit()
        log_activity("Doctor Assigned", f"Reassigned to {doctor_name} ({doctor_id})", report_id)
        flash(f"Report reassigned to {doctor_name}.", "success")
    else:
        flash("Still no available doctor in that department.", "warning")
    return redirect(url_for("reports"))


@app.route("/doctors")
def doctors():
    db = get_db()
    rows = db.execute("SELECT * FROM doctors ORDER BY department, name").fetchall()
    return render_template("doctors.html", doctors=rows, departments=DEPARTMENTS)


@app.route("/add_doctor", methods=["POST"])
def add_doctor():
    name = request.form.get("name", "").strip()
    department = request.form.get("department", "").strip()
    available = 1 if request.form.get("available") else 0

    if not name or department not in DEPARTMENTS:
        flash("Invalid doctor data.", "danger")
        return redirect(url_for("doctors"))

    doctor_id = "DR-" + uuid.uuid4().hex[:6].upper()
    db = get_db()
    db.execute(
        "INSERT INTO doctors (doctor_id, name, department, available, pending_count) VALUES (?,?,?,?,0)",
        (doctor_id, name, department, available)
    )
    db.commit()
    log_activity("Doctor Added", f"{name} ({doctor_id}) – {department}")
    flash(f"Doctor {name} added successfully.", "success")
    return redirect(url_for("doctors"))


@app.route("/toggle_availability/<doctor_id>")
def toggle_availability(doctor_id):
    db = get_db()
    row = db.execute("SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,)).fetchone()
    if not row:
        flash("Doctor not found.", "danger")
        return redirect(url_for("doctors"))

    new_val = 0 if row["available"] else 1
    db.execute("UPDATE doctors SET available = ? WHERE doctor_id = ?", (new_val, doctor_id))
    db.commit()
    status = "Available" if new_val else "Unavailable"
    log_activity("Availability Change", f"{row['name']} set to {status}")
    flash(f"{row['name']} is now {status}.", "success")
    return redirect(url_for("doctors"))


@app.route("/audit")
def audit_logs():
    db = get_db()
    logs = db.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100"
    ).fetchall()
    return render_template("audit_logs.html", logs=logs)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/load_demo")
def load_demo():
    seed_sample_data(force=False)
    flash("Demo data loaded (only if tables were empty).", "success")
    return redirect(url_for("dashboard"))


@app.route("/reset_demo")
def reset_demo():
    db = get_db()
    db.execute("DELETE FROM reports")
    db.execute("DELETE FROM doctors")
    db.execute("DELETE FROM audit_logs")
    db.commit()
    seed_sample_data(force=True)
    flash("All data reset and sample records reloaded.", "warning")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
