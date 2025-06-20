from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), default="available")
    skills = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    calls = relationship("Call", back_populates="agent")

class Call(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    caller_phone = Column(String(20), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    call_start = Column(DateTime, default=datetime.utcnow)
    call_end = Column(DateTime)
    duration = Column(Integer)
    status = Column(String(20), default="active")
    transcript = Column(Text)
    summary = Column(Text)
    resolved = Column(Boolean, default=False)
    
    agent = relationship("Agent", back_populates="calls")

class FAQ(Base):
    __tablename__ = "faqs"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(50))
    confidence_threshold = Column(Float, default=0.8)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class CallQueue(Base):
    __tablename__ = "call_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    caller_phone = Column(String(20), nullable=False)
    priority = Column(Integer, default=1)
    wait_time = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_agent_id = Column(Integer, ForeignKey("agents.id"))

# Pydantic models for API
class AgentCreate(BaseModel):
    name: str
    email: str
    skills: List[str] = []

class AgentResponse(BaseModel):
    id: int
    name: str
    email: str
    status: str
    skills: List[str]
    
    class Config:
        from_attributes = True

class CallCreate(BaseModel):
    caller_phone: str
    agent_id: Optional[int] = None

class CallResponse(BaseModel):
    id: int
    caller_phone: str
    agent_id: Optional[int]
    status: str
    call_start: datetime
    duration: Optional[int]
    resolved: bool
    
    class Config:
        from_attributes = True

class FAQCreate(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None

class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    category: Optional[str]
    usage_count: int
    
    class Config:
        from_attributes = True