"""Database models"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    status = Column(String(20), default="available")  # available, busy, offline
    created_at = Column(DateTime, default=datetime.utcnow)

class Call(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True)
    caller_phone = Column(String(20), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    status = Column(String(20), default="pending")  # pending, active, completed
    call_start = Column(DateTime, default=datetime.utcnow)
    call_end = Column(DateTime)
    duration = Column(Integer)  # seconds
    transcript = Column(Text)
    summary = Column(Text)
    resolved = Column(Boolean, default=False)
    
    agent = relationship("Agent", backref="calls")

class CallQueue(Base):
    __tablename__ = "call_queue"
    
    id = Column(Integer, primary_key=True)
    caller_phone = Column(String(20), nullable=False)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_agent_id = Column(Integer, ForeignKey("agents.id"))

class FAQ(Base):
    __tablename__ = "faqs"
    
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(50))
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
