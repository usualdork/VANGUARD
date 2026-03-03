from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    apt_profile = Column(String, index=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="running") # running, completed, failed

    actions = relationship("RedNodeAction", back_populates="run")

class RedNodeAction(Base):
    __tablename__ = "red_node_actions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    correlation_id = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    action_type = Column(String) # e.g., file_read, process_create
    language = Column(String) # rust, golang, nim
    obfuscation_type = Column(String) # ast
    payload = Column(Text) # the simulated script/payload
    is_evasive = Column(Boolean, default=True)

    run = relationship("Run", back_populates="actions")
    detections = relationship("BlueSensorEvent", back_populates="action")

class BlueSensorEvent(Base):
    __tablename__ = "blue_sensor_events"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(Integer, ForeignKey("red_node_actions.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    alert_type = Column(String) # e.g., high_severity, block
    heuristic_flagged = Column(String) # e.g., suspicious_api_call
    ttd_seconds = Column(Integer, nullable=True)

    action = relationship("RedNodeAction", back_populates="detections")
