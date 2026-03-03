import random
import datetime
from sqlalchemy.orm import Session
from backend.models import RedNodeAction, BlueSensorEvent
import logging
import time
from elasticsearch import Elasticsearch

logger = logging.getLogger("VANGUARD_BlueSensor")

def get_es_client():
    try:
        es = Elasticsearch(["http://127.0.0.1:9200"])
        if not es.ping():
            return None
        return es
    except Exception:
        return None

def ingest_telemetry_and_detect(action: RedNodeAction, db: Session) -> BlueSensorEvent | None:
    """
    Simulates a SIEM/EDR ingesting the action's execution telemetry.
    Randomly flags the event to simulate a detection with a TTD.
    """
    logger.info(f"[{action.correlation_id}] Blue Sensor Analyzing Telemetry...")
    
    es = get_es_client()
    if es:
        # Simulate SIEM polling delay
        time.sleep(2)
        try:
            res = es.search(index="vanguard-telemetry", query={"match": {"correlation_id": action.correlation_id}})
            if res['hits']['total']['value'] > 0:
                logger.info(f"[{action.correlation_id}] Telemetry verified in Elasticsearch SIEM.")
            else:
                logger.warning(f"[{action.correlation_id}] Telemetry missing from Elasticsearch.")
        except Exception as e:
            logger.error(f"[{action.correlation_id}] Elasticsearch query failed: {e}")
    
    # Simulate heuristic detection processing
    if random.random() < 0.6: # Simulate 60% detection rate
        # Calculate random TTD (Time to Detect) in seconds simulating pipeline latency
        ttd = random.randint(5, 300) 
        
        event = BlueSensorEvent(
            action_id=action.id,
            timestamp=datetime.datetime.utcnow(),
            alert_type="high_severity",
            heuristic_flagged=f"Ransomware Detected (TTD: {ttd}s)",
            ttd_seconds=ttd
        )
        db.add(event)
        
        if es:
            alert_doc = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "event_type": "alert",
                "severity": "high",
                "correlation_id": action.correlation_id,
                "ttd_seconds": ttd,
                "description": f"Heuristic Detection of actor {action.run.apt_profile if action.run else 'Unknown'}."
            }
            try:
                es.index(index="vanguard-alerts", document=alert_doc)
                logger.info(f"[{action.correlation_id}] Alert published to Kibana (vanguard-alerts).")
            except Exception as alert_e:
                logger.error(f"[{action.correlation_id}] Failed to publish logic to Alerts index: {alert_e}")
        
        db.commit()
        db.refresh(event)
        
        return event
    
    logger.info(f"[{action.correlation_id}] No detection triggered. Payload successfully evaded sensors.")
    return None
