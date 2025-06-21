"""FastAPI main application"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db, create_tables
from src.agents.call_routing import CallRouter
from src.agents.faq_bot import FAQBot
from src.orchestration.event_bus import event_bus, Event

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
