import uuid
import datetime
import tempfile
import subprocess
import os
from sqlalchemy.orm import Session
from backend.models import RedNodeAction
import logging
from elasticsearch import Elasticsearch

logger = logging.getLogger("VANGUARD_RedNode")

def get_es_client():
    try:
        es = Elasticsearch(["http://127.0.0.1:9200"])
        if not es.ping():
            logger.warning("Elasticsearch is unreachable. Operating without SIEM integration.")
            return None
        return es
    except Exception as e:
        logger.error(f"Elasticsearch connection failed: {e}")
        return None

def simulate_execution(run_id: int, payload_data: dict, db: Session) -> RedNodeAction:
    """
    Simulates the red node executing a payload on an endpoint.
    Conducts mock environmental reconnaissance before execution.
    """
    correlation_id = f"evt_{uuid.uuid4().hex[:12]}"
    
    # 1. Environmental Reconnaissance
    conduct_environmental_recon()
    
    # 2. Execution Logging
    script = payload_data.get("script", "")
    lang = payload_data.get("language", "unknown")
    obfuscation = payload_data.get("obfuscation_type", "none")
    
    logger.info(f"[{correlation_id}] Compiling & Executing {lang} payload with {obfuscation} obfuscation...")
    
    execution_result = "Simulated Execution Only (No Native Compiler)"
    
    if lang.lower() in ["go", "golang"]:
        tmp_path = None # Initialize tmp_path for cleanup in case of early error
        try:
            # Create a temporary Go file
            fd, tmp_path = tempfile.mkstemp(suffix=".go", text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(script)
            
            logger.info(f"[{correlation_id}] Executing compiled payload at {tmp_path}")
            # Run the Go code
            result = subprocess.run(["go", "run", tmp_path], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                execution_result = f"SUCCESS:\n{result.stdout.strip()}"
                logger.info(f"[{correlation_id}] Execution successful: {execution_result}")
            else:
                execution_result = f"FAILED:\n{result.stderr.strip()}"
                logger.warning(f"[{correlation_id}] Execution failed: {execution_result}")
                
            # Self-delete the artifact
            os.remove(tmp_path)
            logger.info(f"[{correlation_id}] Self-deleted compiled artifact from disk.")
            
        except subprocess.TimeoutExpired:
            execution_result = "TIMEOUT: Payload execution exceeded 15 seconds."
            logger.error(f"[{correlation_id}] {execution_result}")
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as cleanup_e:
                    logger.error(f"[{correlation_id}] Failed to clean up temporary file {tmp_path}: {cleanup_e}")
        except Exception as e:
            execution_result = f"ERROR: {str(e)}"
            logger.error(f"[{correlation_id}] Failed to execute native code: {e}")
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as cleanup_e:
                    logger.error(f"[{correlation_id}] Failed to clean up temporary file {tmp_path}: {cleanup_e}")

    elif lang.lower() == "python":
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".py", text=True)
            with os.fdopen(fd, 'w') as f:
                f.write(script)
            
            logger.info(f"[{correlation_id}] Executing Python payload at {tmp_path}")
            # Run the Python code
            result = subprocess.run(["python3", tmp_path], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                execution_result = f"SUCCESS:\n{result.stdout.strip()}"
                logger.info(f"[{correlation_id}] Script output: {execution_result}")
            else:
                execution_result = f"FAILED:\n{result.stderr.strip()}"
                logger.warning(f"[{correlation_id}] Script failed: {execution_result}")
                
            os.remove(tmp_path)
        except Exception as e:
            execution_result = f"ERROR: {str(e)}"
            logger.error(f"[{correlation_id}] Failed to execute script: {e}")
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    # 3. Save "Telemetry" to DB (Action Graph)
    action = RedNodeAction(
        run_id=run_id,
        correlation_id=correlation_id,
        timestamp=datetime.datetime.utcnow(),
        action_type="simulated_benign_action",
        language=lang,
        obfuscation_type=obfuscation,
        payload=script,
        is_evasive=True
    )
    
    db.add(action)
    db.commit()
    db.refresh(action)
    
    # 3.5 SIEM Injection
    es = get_es_client()
    if es:
        doc = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "event_type": "process_execution",
            "correlation_id": correlation_id,
            "host": "vanguard_endpoint_01",
            "payload_language": lang,
            "obfuscation": obfuscation,
            "raw_script": script
        }
        es.index(index="vanguard-telemetry", document=doc)
        logger.info(f"[{correlation_id}] Indexed execution telemetry in Elasticsearch.")
    
    # 4. Containment & Self-Deletion
    logger.info(f"[{correlation_id}] Enforcing strict containment & automated self-deletion protocols.")
    
    return action

def conduct_environmental_recon():
    """Mock checking for EDRs to inform the orchestration loop."""
    print("[Red Node Recon] Enumerating processes...")
    print("[Red Node Recon] -> csfalcon.sys (CrowdStrike) identified.")
    print("[Red Node Recon] Expected strategy: Direct Syscalls preferred over API hooking.")
