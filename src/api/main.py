from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import uvicorn
from datetime import datetime
import asyncio

from ..database import get_db, engine
from ..models import Base, Agent, Call, FAQ, AgentCreate, AgentResponse, CallCreate, CallResponse, FAQCreate, FAQResponse
from ..agents.call_routing import CallRouter
from ..agents.faq_bot import FAQBot
from ..orchestration.event_bus import event_bus, Event

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SATIM Call Center Automation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
@app.on_event("startup")
async def startup_event():
    """Initialize system components on startup"""
    print("Starting SATIM Call Center Automation System...")

# Agent endpoints
@app.post("/agents/", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    db_agent = Agent(**agent.dict())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.get("/agents/", response_model=List[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    return db.query(Agent).all()

@app.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.put("/agents/{agent_id}/status")
async def update_agent_status(agent_id: int, status: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    old_status = agent.status
    agent.status = status
    db.commit()
    
    # Publish status change event
    await event_bus.publish(Event(
        type="agent_status_changed",
        data={"agent_id": agent_id, "old_status": old_status, "status": status},
        timestamp=datetime.utcnow(),
        correlation_id=f"agent_{agent_id}"
    ))
    
    return {"message": "Status updated successfully"}

# Call endpoints
@app.post("/calls/incoming")
async def incoming_call(caller_phone: str, priority: int = 1, db: Session = Depends(get_db)):
    """Handle incoming call"""
    await event_bus.publish(Event(
        type="call_incoming",
        data={"caller_phone": caller_phone, "priority": priority},
        timestamp=datetime.utcnow(),
        correlation_id=f"incoming_{caller_phone}"
    ))
    
    return {"message": "Call received and being processed"}

@app.get("/calls/", response_model=List[CallResponse])
def get_calls(db: Session = Depends(get_db)):
    return db.query(Call).all()

@app.post("/calls/{call_id}/end")
async def end_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    await event_bus.publish(Event(
        type="call_ended",
        data={"call_id": call_id, "agent_id": call.agent_id},
        timestamp=datetime.utcnow(),
        correlation_id=f"call_{call_id}"
    ))
    
    return {"message": "Call ended successfully"}

# FAQ endpoints
@app.post("/faqs/", response_model=FAQResponse)
def create_faq(faq: FAQCreate, db: Session = Depends(get_db)):
    db_faq = FAQ(**faq.dict())
    db.add(db_faq)
    db.commit()
    db.refresh(db_faq)
    return db_faq

@app.get("/faqs/", response_model=List[FAQResponse])
def get_faqs(db: Session = Depends(get_db)):
    return db.query(FAQ).all()

@app.post("/faqs/ask")
async def ask_question(question: str, caller_phone: str, call_id: int = None, db: Session = Depends(get_db)):
    """Ask a question to the FAQ bot"""
    await event_bus.publish(Event(
        type="question_asked",
        data={
            "question": question,
            "caller_phone": caller_phone,
            "call_id": call_id
        },
        timestamp=datetime.utcnow(),
        correlation_id=f"question_{call_id or caller_phone}"
    ))
    
    return {"message": "Question processed", "status": "processing"}

@app.get("/faqs/stats")
def get_faq_stats(db: Session = Depends(get_db)):
    """Get FAQ usage statistics"""
    faq_bot = FAQBot(db)
    return faq_bot.get_faq_stats()

@app.get("/queue/status")
def get_queue_status(db: Session = Depends(get_db)):
    """Get current queue status"""
    queue_items = db.query(CallQueue).filter(
        CallQueue.assigned_agent_id.is_(None)
    ).order_by(CallQueue.priority.desc(), CallQueue.created_at.asc()).all()
    
    return {
        "queue_length": len(queue_items),
        "items": [
            {
                "id": item.id,
                "caller_phone": item.caller_phone,
                "priority": item.priority,
                "wait_time": int((datetime.utcnow() - item.created_at).total_seconds()),
                "position": idx + 1
            }
            for idx, item in enumerate(queue_items)
        ]
    }

@app.get("/dashboard/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Get dashboard metrics"""
    # Active calls
    active_calls = db.query(Call).filter(Call.status == "active").count()
    
    # Available agents
    available_agents = db.query(Agent).filter(Agent.status == "available").count()
    
    # Queue length
    queue_length = db.query(CallQueue).filter(
        CallQueue.assigned_agent_id.is_(None)
    ).count()
    
    # Today's completed calls
    from datetime import date
    today = date.today()
    completed_today = db.query(Call).filter(
        Call.status == "completed",
        Call.call_start >= today
    ).count()
    
    return {
        "active_calls": active_calls,
        "available_agents": available_agents,
        "queue_length": queue_length,
        "completed_today": completed_today
    }

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)