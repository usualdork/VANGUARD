from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import get_db, Base
import pytest

# Setup an in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_vanguard.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

from unittest.mock import patch
from backend import orchestrator

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "VANGUARD Core Online"}

def test_create_run_e2e():
    response = client.post("/runs/?apt_profile=TestingAPT&language=python&action_type=malicious_recon")
    assert response.status_code == 200
    data = response.json()
    print("DATA RETURNED:", data)
    assert data["apt_profile"] == "TestingAPT"
    assert "status" in data
    assert data["status"] == "completed"
    
    run_id = data["id"]
    
    # Retrieve the run to check graph components
    res_get = client.get(f"/runs/{run_id}")
    assert res_get.status_code == 200
    graph_data = res_get.json()
    
    assert "run" in graph_data
    assert "actions" in graph_data
    assert "detections" in graph_data
    
    actions = graph_data["actions"]
    assert len(actions) == 1
    action = actions[0]
    assert action["action_type"] == "simulated_benign_action"
    
    # Log payload format
    print("Simulated Payload Generated:", action["payload"])
    assert action["correlation_id"].startswith("evt_")
    
    # Assert detection logic
    detections = graph_data["detections"]
    if len(detections) > 0:
        det = detections[0]
        assert det["action_id"] == action["id"]
        assert det["ttd_seconds"] is not None
        print(f"Detected Heuristic: {det['heuristic_flagged']} with TTD: {det['ttd_seconds']}s")

def test_get_all_runs():
    client.post("/runs/?apt_profile=Run1")
    client.post("/runs/?apt_profile=Run2")
    
    response = client.get("/runs/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
def test_missing_run():
    response = client.get("/runs/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"
