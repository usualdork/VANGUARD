"""
VANGUARD Target: Cloud Storage API
==================================
A Flask-based file storage application with REAL, exploitable vulnerabilities.

Vulnerabilities included:
  - Broken Authentication (JWT Signature Stripping / 'none' algorithm)
  - Insecure Direct Object Reference (IDOR) on file access
  - Command Injection via "file conversion" utility
  - Directory Listing / Information Disclosure

SAFETY: This app binds ONLY to 127.0.0.1.
"""

import os
import sqlite3
import base64
import json
import subprocess
from flask import Flask, request, jsonify, g

app = Flask(__name__)
DB_PATH = "/tmp/vanguard_target/cloud_storage.db"

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
    os.makedirs("/tmp/vanguard_target/storage", exist_ok=True)
    
    # Seed files
    with open("/tmp/vanguard_target/storage/file_1.txt", "w") as f:
        f.write("User1: Grocery List\n")
    with open("/tmp/vanguard_target/storage/file_2.txt", "w") as f:
        f.write("Admin: AWS VPC Architecture diagram link: https://internal.corp/vpc\n")
    with open("/tmp/vanguard_target/storage/file_3.txt", "w") as f:
        f.write("Financials Q4: Revenue $4.2M, Missed targets.\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS files")
    
    c.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT,
        is_admin BOOLEAN
    )""")
    
    c.execute("""CREATE TABLE files (
        id INTEGER PRIMARY KEY,
        owner_id INTEGER,
        filename TEXT,
        disk_path TEXT
    )""")
    
    c.executemany("INSERT INTO users (username, password, is_admin) VALUES (?,?,?)", [
        ("admin", "admin_secure", True),
        ("testuser", "test1234", False)
    ])
    
    c.executemany("INSERT INTO files (owner_id, filename, disk_path) VALUES (?,?,?)", [
        (2, "groceries.txt", "/tmp/vanguard_target/storage/file_1.txt"),
        (1, "architecture.txt", "/tmp/vanguard_target/storage/file_2.txt"),
        (1, "financials_q4.txt", "/tmp/vanguard_target/storage/file_3.txt")
    ])
    
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 1: Broken Authentication (JWT "none" algorithm)
# ──────────────────────────────────────────────────────────────────
def parse_vulnerable_jwt(token):
    """
    Deliberately vulnerable JWT parser that accepts the 'none' algorithm
    or ignores signature validation if the alg header is tampered.
    """
    try:
        parts = token.split('.')
        if len(parts) < 2: return None
        
        header_b64 = parts[0] + "=" * ((4 - len(parts[0]) % 4) % 4)
        payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        
        header = json.loads(base64.b64decode(header_b64).decode('utf-8'))
        payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
        
        # DELIBERATELY VULNERABLE: If alg is 'none', we just trust the payload!
        if header.get("alg", "").lower() == "none":
            return payload
            
        # Hardcoded static secret verification (also vulnerable)
        if len(parts) == 3 and parts[2] == "static_secret_signature":
            return payload
            
        return None
    except Exception:
        return None

@app.route("/api/v1/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    un = data.get("username")
    pw = data.get("password")
    db = get_db()
    
    # Safe param binding here, but we'll leak JWT
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (un, pw)).fetchone()
    if user:
        header = base64.b64encode(b'{"alg":"HS256","typ":"JWT"}').decode('utf-8').rstrip('=')
        payload = base64.b64encode(json.dumps({"sub": user["id"], "role": "admin" if user["is_admin"] else "user"}).encode('utf-8')).decode('utf-8').rstrip('=')
        token = f"{header}.{payload}.static_secret_signature"
        return jsonify({"token": token})
    return jsonify({"error": "Invalid credentials"}), 401

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 2: IDOR (Insecure Direct Object Reference)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/v1/files/<int:file_id>")
def get_file(file_id):
    """Vulnerable IDOR: Doesn't check if the authenticated user owns the file."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
    
    token = auth_header.split(" ")[1]
    claims = parse_vulnerable_jwt(token)
    if not claims:
        return jsonify({"error": "Invalid token. Try alg: none"}), 401
        
    db = get_db()
    # DELIBERATELY VULNERABLE: Does NOT enforce `WHERE owner_id = claims['sub']`
    file_record = db.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    
    if not file_record:
        return jsonify({"error": "File not found"}), 404
        
    try:
        with open(file_record["disk_path"], "r") as f:
            content = f.read()
            return jsonify({
                "id": file_record["id"],
                "filename": file_record["filename"],
                "owner": file_record["owner_id"],
                "content": content
            })
    except Exception as e:
        return jsonify({"error": "Could not read file from disk"}), 500

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 3: Command Injection via "Conversion" logic
# ──────────────────────────────────────────────────────────────────
@app.route("/api/v1/tools/convert", methods=["POST"])
def convert_file():
    """Vulnerable to OS Command Injection via the format parameter."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing token"}), 401
        
    data = request.get_json() or {}
    source_file = data.get("source", "file_1.txt")
    out_format = data.get("format", "pdf")
    
    # DELIBERATELY VULNERABLE: Unsanitized out_format goes straight to shell
    # e.g., format -> "pdf; cat /etc/passwd"
    cmd = f"echo 'Converting {source_file} to {out_format}'"
    
    try:
        # We use shell=True to allow the injection to actually work
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return jsonify({"status": "conversion_mocked", "output": result.stdout, "error": result.stderr})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({
        "service": "Cloud Storage API",
        "endpoints": [
            "POST /api/v1/login - body: username, password",
            "GET  /api/v1/files/<id> - Requires Auth header",
            "POST /api/v1/tools/convert - body: source, format (Requires Auth header)"
        ]
    })

def start_target_server(port=9997):
    init_db()
    print(f"[TARGET] Cloud Storage application starting on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_target_server()
