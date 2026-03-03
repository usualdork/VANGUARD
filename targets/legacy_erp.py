"""
VANGUARD Target: Legacy ERP System
==================================
A Flask-based ERP application with REAL, exploitable vulnerabilities
representing older enterprise software patterns.

Vulnerabilities included:
  - XML External Entity (XXE) Injection
  - Server-Side Request Forgery (SSRF)
  - Hardcoded API tokens
  - Open Redirect
  - Unrestricted File Upload (simulated)

SAFETY: This app binds ONLY to 127.0.0.1.
"""

import os
import sqlite3
import urllib.request
from flask import Flask, request, jsonify, g, redirect
import xml.etree.ElementTree as ET

app = Flask(__name__)
DB_PATH = "/tmp/vanguard_target/erp.db"

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
    # Seed sensitive internal files
    with open("/tmp/vanguard_target/erp_config.ini", "w") as f:
        f.write("[erp_db]\nhost=internal-erp.local\nuser=sysadmin\npassword=VendorPass2020!\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS vendors")
    c.execute("""CREATE TABLE vendors (
        id INTEGER PRIMARY KEY,
        name TEXT,
        contact TEXT,
        internal_notes TEXT
    )""")
    vendors = [
        ("Acme Corp", "contact@acme.com", "Owes $50,000"),
        ("GlobalTech", "sales@globaltech.com", "Contract expires 2026. IP: 10.0.9.15"),
        ("DefSys", "gov@defsys.com", "TOP SECRET: Supply chain backdoor installed"),
    ]
    c.executemany("INSERT INTO vendors (name, contact, internal_notes) VALUES (?,?,?)", vendors)
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 1: Server-Side Request Forgery (SSRF)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/v1/proxy/image")
def fetch_vendor_image():
    """ERP Proxy endpoint vulnerable to SSRF."""
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    # DELIBERATELY VULNERABLE: Fetches arbitrary URL, including file:// or localhost
    try:
        # User could send file:///etc/passwd or http://169.254.169.254/latest/meta-data/
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as response:
            content = response.read().decode('utf-8', errors='ignore')
            return jsonify({
                "source": url,
                "status": "success",
                "preview": content[:1000] # Return preview to the attacker
            })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch {url}", "details": str(e)}), 500

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 2: XML External Entity (XXE)
# ──────────────────────────────────────────────────────────────────
@app.route("/api/v1/invoice/process", methods=["POST"])
def process_invoice():
    """Invoice processor vulnerable to XXE."""
    if request.content_type != "application/xml":
        return jsonify({"error": "Content-Type must be application/xml"}), 415

    xml_data = request.data
    # DELIBERATELY VULNERABLE: DefusedXML is NOT used. Standard ET is vulnerable to XXE
    # Actually wait, modern Python mitigates XXE in ET. We will simulate it for the agent 
    # to find by parsing manually if standard ET blocks it, or we use standard ET with entities.
    
    try:
        # In python standard library, xml.etree does not automatically resolve external entities 
        # for security reasons by default in newer versions, but we will write a vulnerable 
        # mock parser for demonstration if the agent sends an entity payload.
        xml_str = xml_data.decode('utf-8')
        
        # Simulated XXE Vulnerability
        if "<!ENTITY" in xml_str and "SYSTEM" in xml_str:
            # Extract the path the attacker is trying to read
            try:
                system_path = xml_str.split("SYSTEM")[1].split(">")[0].strip(" '\"")
                if system_path.startswith("file://"):
                    system_path = system_path[7:]
                with open(system_path, "r") as f:
                    leaked_data = f.read()
                    return jsonify({"status": "parsed", "vendor_id": leaked_data})
            except Exception as e:
                pass

        # Normal parsing fallback
        root = ET.fromstring(xml_data)
        vendor = root.findtext("vendor")
        amount = root.findtext("amount")
        return jsonify({"status": "success", "message": f"Invoice for {vendor} processed: ${amount}"})
    except Exception as e:
        return jsonify({"error": "XML Parsing Failed", "details": str(e)}), 400

# ──────────────────────────────────────────────────────────────────
# VULNERABILITY 3: Hardcoded API Key & Insecure Direct Object Reference
# ──────────────────────────────────────────────────────────────────
@app.route("/api/v1/vendors/<int:vendor_id>")
def get_vendor(vendor_id):
    """Vendor detail endpoint vulnerable to IDOR."""
    api_key = request.headers.get("X-API-Key")
    
    # DELIBERATELY VULNERABLE: Hardcoded credential
    if api_key != "ERP-LEGACY-T0K3N-99":
        return jsonify({"error": "Unauthorized. Hint: Check /api/v1/docs"}), 401
    
    # IDOR: No check if the user is allowed to see THIS SPECIFIC vendor
    db = get_db()
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    if vendor:
        return jsonify(dict(vendor))
    return jsonify({"error": "Vendor not found"}), 404

# ──────────────────────────────────────────────────────────────────
# Informational Endpoints
# ──────────────────────────────────────────────────────────────────
@app.route("/api/v1/docs")
def docs():
    return jsonify({
        "info": "Legacy ERP API (v1.2.4)",
        "endpoints": [
            "GET /api/v1/proxy/image?url=...",
            "POST /api/v1/invoice/process (XML format)",
            "GET /api/v1/vendors/<id> (Requires X-API-Key: ERP-LEGACY-T0K3N-99)"
        ]
    })

@app.route("/")
def index():
    return jsonify({
        "service": "Legacy ERP Extranet",
        "docs": "/api/v1/docs"
    })

def start_target_server(port=9998):
    init_db()
    print(f"[TARGET] Legacy ERP application starting on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_target_server()
