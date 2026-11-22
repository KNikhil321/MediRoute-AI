# MediRoute AI

**Framework for Intelligent Report Routing and Physician Assignment in Healthcare Using MediRoute AI**

A simple full-stack research prototype for intelligent healthcare report routing and physician assignment. Built with Flask + SQLite for M.Tech demonstration purposes.

> **Disclaimer**: This system does not diagnose diseases, replace doctors, or provide emergency medical care. All demonstration records are synthetic. Do not enter real patient information.

## Features

- Department classification using weighted keyword matching
- Emergency indicator screening (basic keyword-based)
- Least-pending-load physician assignment
- Dashboard with live statistics
- Report management, doctor management, audit logs
- Fully offline, no external APIs or paid services

## Tech Stack

- Frontend: HTML, CSS, JavaScript, Bootstrap 5
- Backend: Python Flask
- Database: SQLite
- NLP: Local weighted keyword matching (no external LLMs)

## Quick Start (Local)

```bash
# 1. Clone / extract the project
cd mediroute_ai

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

Open http://127.0.0.1:5000 in your browser.

On first run the database is created automatically with sample doctors and reports.

## Project Structure

```
mediroute_ai/
├── app.py                 # Main Flask application
├── requirements.txt
├── README.md
├── mediroute.db           # SQLite database (auto-created)
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── submit_report.html
│   ├── reports.html
│   ├── doctors.html
│   ├── audit_logs.html
│   └── about.html
└── static/
    ├── style.css
    └── script.js
```

## Deployment (Free Public HTTPS URL)

### Option 1: Render.com (Recommended – Free Tier)

1. Create a free account at https://render.com
2. Click **New + → Web Service**
3. Connect your GitHub repository (push this project to a public GitHub repo first)
4. Settings:
   - **Name**: mediroute-ai
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Instance Type**: Free
5. Add Environment Variable (optional):
   - `PORT` = `10000` (Render sets this automatically; the app already reads `os.environ.get("PORT", 5000)`)
6. Click **Create Web Service**
7. Wait 1–2 minutes. You will get a public URL like:
   `https://mediroute-ai.onrender.com`

### Option 2: Railway.app

1. Go to https://railway.app
2. New Project → Deploy from GitHub
3. Select the repository
4. Railway auto-detects Python. Set start command to `python app.py`
5. Generate a public domain from the Settings tab.

### Option 3: PythonAnywhere (Free)

1. Sign up at https://www.pythonanywhere.com
2. Upload the project files
3. Create a new Web App (Manual configuration, Python 3.10+)
4. Set the WSGI file to point to `app.py`
5. Reload the web app.

## Sample Workflow for Demo

1. Open **Dashboard** – see statistics and recent reports.
2. Go to **Submit Report** – enter a synthetic patient name and description (e.g., “Patient has severe chest pain and difficulty breathing”).
3. Submit → system classifies department, screens for emergency keywords, assigns doctor (or flags for human review).
4. Check **All Reports**, **Doctors**, and **Audit Logs**.
5. Use **Load Demo Data** / **Reset Demo Data** buttons on Dashboard if needed.

## Notes for Evaluation

- All data is synthetic.
- Emergency screening is keyword-based only – not clinical triage.
- No external AI APIs are used.
- Suitable for offline / free-tier demonstration.

---

Developed as an M.Tech project demonstration prototype.