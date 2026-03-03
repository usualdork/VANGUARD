from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, database, orchestrator
from simulators import red_node, blue_sensor
import datetime
import asyncio
import threading
import json
from agents.react_agent import run_react_pentest
import threading as _threading

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="VANGUARD API", description="Autonomous Adversarial Simulation & Telemetry Fusion Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "VANGUARD Core Online"}

@app.post("/runs/")
def create_run(apt_profile: str, language: str = "rust", action_type: str = "benign_file_read", db: Session = Depends(database.get_db)):
    db_run = models.Run(apt_profile=apt_profile)
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    
    # 1. Orchestrator: Generate Payload
    payload = orchestrator.generate_payload(apt_profile, language, action_type)
    
    # 2. Red Node: Execute Payload
    action = red_node.simulate_execution(db_run.id, payload, db)
    
    # 3. Blue Sensor: Telemetry Analysis
    detection = blue_sensor.ingest_telemetry_and_detect(action, db)
    
    # 4. Orchestrator: Autonomous Evasion Loop (If Detected)
    if detection:
        suggestion = orchestrator.evaluate_evasion_strategy(detection.heuristic_flagged, apt_profile)
        print(f"[{apt_profile} Evasion Loop] {suggestion}")
    
    db_run.status = "completed"
    db_run.end_time = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_run)
    
    return db_run

@app.get("/runs/")
def get_runs(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    runs = db.query(models.Run).offset(skip).limit(limit).all()
    return runs

@app.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(database.get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Return run with actions and detections
    actions = db.query(models.RedNodeAction).filter(models.RedNodeAction.run_id == run_id).all()
    action_ids = [a.id for a in actions]
    detections = db.query(models.BlueSensorEvent).filter(models.BlueSensorEvent.action_id.in_(action_ids)).all()
    
    return {
        "run": run,
        "actions": actions,
        "detections": detections
    }

# ---------------------------------------------------------
# Cognitive Purple Agent - HITL Streaming Endpoint
# ---------------------------------------------------------
# Track the active scan so we can cancel it
_active_scan = {"cancel_event": None, "thread": None}


@app.post("/api/v1/pentest/cancel")
async def cancel_pentest():
    """Cancel the currently running pentest scan."""
    if _active_scan["cancel_event"]:
        _active_scan["cancel_event"].set()
        _active_scan["cancel_event"] = None
        _active_scan["thread"] = None
        return {"status": "cancelled"}
    return {"status": "no_active_scan"}


@app.get("/api/v1/pentest/stream")
async def stream_pentest(request: Request, target_url: str, scope: str = "app", mission: str = None, max_steps: int = 20):
    """
    Server-Sent Events (SSE) endpoint to stream live LLM reasoning.
    Starts the ReAct loop in a background thread and yields its Steps.
    Automatically cancels any previously running scan.
    """
    # Cancel any previous scan first
    if _active_scan["cancel_event"]:
        _active_scan["cancel_event"].set()

    cancel_event = _threading.Event()
    _active_scan["cancel_event"] = cancel_event

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_step(event: dict):
        # Must be thread-safe as it is called from the synchronous ReAct thread
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def pentest_thread():
        try:
            run_react_pentest(
                target_url=target_url,
                mission=mission,
                max_steps=max_steps,
                scope=scope,
                on_step_callback=on_step,
                cancel_event=cancel_event
            )
        except Exception as e:
            on_step({"type": "error", "data": str(e)})
        finally:
            on_step({"type": "close", "data": "Stream closed"})

    # Launch agent in background thread
    thread = _threading.Thread(target=pentest_thread, daemon=True)
    _active_scan["thread"] = thread
    thread.start()

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Send keepalive comment to detect disconnection
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ["finish", "close", "error"]:
                    break
        finally:
            # Client disconnected or stream ended — kill the backend scan
            cancel_event.set()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
