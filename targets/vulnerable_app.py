"""
VANGUARD Target: Deliberately Vulnerable Web Application
=========================================================
A Flask-based web application with REAL, exploitable vulnerabilities
designed to be discovered and exploited by the Cognitive Purple Agent.

Vulnerabilities included:
  - SQL Injection (authentication bypass)
  - Path Traversal (arbitrary file read)
  - Command Injection (OS command execution)
  - Information Disclosure (server headers, debug info)
  - Insecure Direct Object Reference (IDOR)

SAFETY: This app binds ONLY to 127.0.0.1 and is intended
for local security research only.
"""

import os
import sqlite3
import subprocess
from flask import Flask, request, jsonify, g

app = Flask(__name__)
DB_PATH = "/tmp/vanguard_target/vulnerable.db"

# ──────────────────────────────────────────────────────────────────
# Database Setup
# ──────────────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    os.makedirs("/tmp/vanguard_target", exist_ok=True)
    # Seed sensitive files for the agent to discover
    with open("/tmp/vanguard_target/secret_credentials.txt", "w") as f:
        f.write("admin:SuperS3cretP@ssw0rd!\nceo:BoardRoom2025\nroot:toor\n")
    with open("/tmp/vanguard_target/confidential_report.pdf", "w") as f:
        f.write("[CLASSIFIED] Project AURORA - Satellite Vulnerability Assessment\n")
    with open("/tmp/vanguard_target/.env", "w") as f:
        f.write("DB_PASSWORD=pr0duction_p@ss\nAWS_SECRET_KEY=AKIAIOSFODNN7EXAMPLE\nAPI_KEY=sk-live-51234567890\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS classified_docs")
    c.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT,
        role TEXT,
        clearance_level TEXT
    )""")
    c.execute("""CREATE TABLE classified_docs (
        id INTEGER PRIMARY KEY,
        title TEXT,
        classification TEXT,
        content TEXT
    )""")
    # Seed users with plaintext passwords (deliberate vulnerability)
    users = [
        ("admin", "admin123", "administrator", "TOP_SECRET"),
        ("operator", "password", "operator", "SECRET"),
        ("analyst", "analyst2024", "analyst", "CONFIDENTIAL"),
        ("guest", "guest", "guest", "UNCLASSIFIED"),
    ]
    c.executemany("INSERT INTO users (username, password, role, clearance_level) VALUES (?,?,?,?)", users)
    # Seed classified documents
    docs = [
        ("Project AURORA Briefing", "TOP_SECRET", "Satellite vulnerability exploitation framework details"),
        ("Network Topology Map", "SECRET", "Internal network: 10.0.0.0/8, DMZ: 172.16.0.0/12"),
        ("Employee Records", "CONFIDENTIAL", "Full PII dataset for 2,400 employees"),
        ("Public Press Release", "UNCLASSIFIED", "Company announces new cybersecurity partnership"),
    ]
    c.executemany("INSERT INTO classified_docs (title, classification, content) VALUES (?,?,?)", docs)
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 1: SQL Injection (Authentication Bypass)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    """Login endpoint vulnerable to SQL Injection."""
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")
    db = get_db()
    # DELIBERATELY VULNERABLE: String concatenation in SQL query
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    try:
        result = db.execute(query).fetchone()
        if result:
            return jsonify({
                "status": "authenticated",
                "user": result["username"],
                "role": result["role"],
                "clearance": result["clearance_level"]
            })
        return jsonify({"status": "denied", "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 2: SQL Injection (Data Exfiltration)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/docs/search")
def search_docs():
    """Search classified docs — vulnerable to UNION-based SQLi."""
    keyword = request.args.get("q", "")
    db = get_db()
    query = f"SELECT id, title, classification FROM classified_docs WHERE title LIKE '%{keyword}%'"
    try:
        results = db.execute(query).fetchall()
        return jsonify({"results": [dict(r) for r in results]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 3: Path Traversal (Arbitrary File Read)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/files/download")
def download_file():
    """File download endpoint vulnerable to path traversal."""
    filename = request.args.get("name", "")
    # DELIBERATELY VULNERABLE: No sanitization of path
    base = "/tmp/vanguard_target/"
    filepath = base + filename
    try:
        with open(filepath, "r") as f:
            return jsonify({"filename": filename, "content": f.read()})
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 4: Command Injection (OS Command Execution)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/network/ping")
def ping_host():
    """Network diagnostic tool vulnerable to command injection."""
    host = request.args.get("host", "127.0.0.1")
    # DELIBERATELY VULNERABLE: Unsanitized shell command
    cmd = f"ping -c 1 {host}"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return jsonify({"command": cmd, "output": result.stdout, "error": result.stderr})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timed out"}), 408

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 5: Information Disclosure
# ──────────────────────────────────────────────────────────────────
@app.route("/api/debug/info")
def debug_info():
    """Debug endpoint leaking sensitive server information."""
    return jsonify({
        "server": "VanguardTarget/1.0",
        "python_version": os.popen("python3 --version").read().strip(),
        "os": os.popen("uname -a").read().strip(),
        "cwd": os.getcwd(),
        "env_vars": {k: v for k, v in os.environ.items() if "PATH" in k or "HOME" in k},
        "database_path": DB_PATH,
        "endpoints": [
            "GET  /                       - Server banner",
            "POST /api/login              - Authentication (username, password)",
            "GET  /api/docs/search?q=     - Search classified documents",
            "GET  /api/files/download?name=  - Download files",
            "GET  /api/network/ping?host= - Network ping utility",
            "GET  /api/debug/info         - This debug page",
            "GET  /api/users              - List all users (requires auth)",
        ]
    })

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 6: IDOR (Insecure Direct Object Reference)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/users/<int:user_id>")
def get_user(user_id):
    """User profile endpoint vulnerable to IDOR — no auth check."""
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if user:
        return jsonify({
            "id": user["id"],
            "username": user["username"],
            "password": user["password"],  # DELIBERATELY LEAKING PASSWORD
            "role": user["role"],
            "clearance": user["clearance_level"]
        })
    return jsonify({"error": "User not found"}), 404

@app.route("/")
def index():
    return jsonify({
        "service": "VANGUARD Target Application",
        "version": "1.0.0",
        "status": "operational",
        "hint": "Try /api/debug/info for more details"
    })


def start_target_server(port=9999):
    """Initialize and start the vulnerable target server."""
    init_db()
    print(f"[TARGET] Vulnerable application starting on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_target_server()
