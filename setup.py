#!/usr/bin/env python3
"""
Quick setup script to create missing essential files
"""

import os

def create_file(filepath, content):
    """Create file with content"""
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Created: {filepath}")


# Event Bus
event_bus_content = '''"""Event bus for inter-agent communication"""
import asyncio
from typing import Dict, List, Callable, Any
from datetime import datetime
from dataclasses import dataclass

@dataclass
class Event:
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    correlation_id: str = None

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event: Event):
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    await handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")

# Global event bus instance
event_bus = EventBus()
'''

# Models
models_content = '''"""Database models"""
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
'''

# Database
database_content = '''"""Database configuration"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# SQLite database for development
DATABASE_URL = "sqlite:///./satim_callcenter.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

# API Main
api_main_content = '''"""FastAPI main application"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db, create_tables
from ..agents.call_routing import CallRouter
from ..agents.faq_bot import FAQBot
from ..orchestration.event_bus import event_bus, Event
from datetime import datetime
import asyncio

app = FastAPI(title="SATIM Call Center API", version="1.0.0")

# Initialize on startup
@app.on_event("startup")
async def startup_event():
    create_tables()
    print("🚀 SATIM Call Center API Started")

@app.get("/")
async def root():
    return {"message": "SATIM Call Center API", "status": "running"}

@app.post("/call/incoming")
async def incoming_call(caller_phone: str, priority: int = 1):
    """Handle incoming call"""
    await event_bus.publish(Event(
        type="call_incoming",
        data={"caller_phone": caller_phone, "priority": priority},
        timestamp=datetime.utcnow()
    ))
    return {"status": "call_received", "caller_phone": caller_phone}

@app.post("/faq/ask")
async def ask_question(question: str, caller_phone: str = None):
    """Ask FAQ question"""
    await event_bus.publish(Event(
        type="question_asked",
        data={"question": question, "caller_phone": caller_phone},
        timestamp=datetime.utcnow()
    ))
    return {"status": "question_received", "question": question}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

# Quick requirements
requirements_content = '''fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==1.4.46
python-multipart==0.0.6
asyncio==3.4.3
numpy==1.24.3
scikit-learn==1.3.0
transformers==4.35.0
SpeechRecognition==3.10.0
'''

def main():
    """Create all missing files"""
    print("🔧 Creating missing essential files...")
    
    # Create directories
    os.makedirs("src/orchestration", exist_ok=True)
    os.makedirs("src/api", exist_ok=True)
    
    # Create files
    create_file("src/orchestration/event_bus.py", event_bus_content)
    create_file("src/models.py", models_content)
    create_file("src/database.py", database_content)
    create_file("src/api/main.py", api_main_content)
    create_file("requirements.txt", requirements_content)
    
    # Create __init__.py files
    create_file("src/__init__.py", "")
    create_file("src/agents/__init__.py", "")
    create_file("src/api/__init__.py", "")
    create_file("src/orchestration/__init__.py", "")
    
    print("\n🎉 Setup complete! Now run:")
    print("1. pip install -r requirements.txt")
    print("2. python quick_setup.py")
    print("3. python test_agents_quick.py")

if __name__ == "__main__":
    main()