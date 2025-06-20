import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
import random
from sqlalchemy.orm import Session
from ..models import Agent, CallQueue, Call
from ..orchestration.event_bus import event_bus, Event
import logging

logger = logging.getLogger(__name__)

class CallRouter:
    def __init__(self, db: Session):
        self.db = db
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Setup event handlers for call routing"""
        event_bus.subscribe("call_incoming", self.handle_incoming_call)
        event_bus.subscribe("agent_status_changed", self.handle_agent_status_change)
        event_bus.subscribe("call_ended", self.handle_call_ended)
    
    async def handle_incoming_call(self, event: Event):
        """Handle incoming call event"""
        caller_phone = event.data.get("caller_phone")
        priority = event.data.get("priority", 1)
        
        logger.info(f"Routing incoming call from {caller_phone}")
        
        # Find available agent
        available_agent = self.find_best_agent()
        
        if available_agent:
            # Assign call directly
            await self.assign_call_to_agent(caller_phone, available_agent.id)
        else:
            # Add to queue
            await self.add_to_queue(caller_phone, priority)
    
    def find_best_agent(self) -> Optional[Agent]:
        """Find the best available agent using load balancing"""
        available_agents = self.db.query(Agent).filter(
            Agent.status == "available"
        ).all()
        
        if not available_agents:
            return None
        
        # Simple round-robin for now - can be enhanced with more sophisticated algorithms
        # Count current active calls per agent
        agent_loads = {}
        for agent in available_agents:
            active_calls = self.db.query(Call).filter(
                Call.agent_id == agent.id,
                Call.status == "active"
            ).count()
            agent_loads[agent.id] = active_calls
        
        # Return agent with lowest load
        best_agent_id = min(agent_loads, key=agent_loads.get)
        return next(agent for agent in available_agents if agent.id == best_agent_id)
    
    async def assign_call_to_agent(self, caller_phone: str, agent_id: int):
        """Assign call to specific agent"""
        # Update agent status
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.status = "busy"
            
            # Create call record
            call = Call(
                caller_phone=caller_phone,
                agent_id=agent_id,
                status="active"
            )
            self.db.add(call)
            self.db.commit()
            
            # Publish assignment event
            await event_bus.publish(Event(
                type="call_assigned",
                data={
                    "call_id": call.id,
                    "caller_phone": caller_phone,
                    "agent_id": agent_id,
                    "agent_name": agent.name
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"call_{call.id}"
            ))
            
            logger.info(f"Call assigned: {caller_phone} -> Agent {agent.name}")
    
    async def add_to_queue(self, caller_phone: str, priority: int):
        """Add call to waiting queue"""
        queue_item = CallQueue(
            caller_phone=caller_phone,
            priority=priority
        )
        self.db.add(queue_item)
        self.db.commit()
        
        await event_bus.publish(Event(
            type="call_queued",
            data={
                "queue_id": queue_item.id,
                "caller_phone": caller_phone,
                "priority": priority,
                "position": self.get_queue_position(queue_item.id)
            },
            timestamp=datetime.utcnow(),
            correlation_id=f"queue_{queue_item.id}"
        ))
        
        logger.info(f"Call queued: {caller_phone} (Priority: {priority})")
    
    def get_queue_position(self, queue_id: int) -> int:
        """Get position in queue"""
        queue_item = self.db.query(CallQueue).filter(CallQueue.id == queue_id).first()
        if not queue_item:
            return 0
        
        position = self.db.query(CallQueue).filter(
            CallQueue.created_at <= queue_item.created_at,
            CallQueue.assigned_agent_id.is_(None)
        ).count()
        
        return position
    
    async def handle_agent_status_change(self, event: Event):
        """Handle agent status change - assign queued calls if agent becomes available"""
        agent_id = event.data.get("agent_id")
        new_status = event.data.get("status")
        
        if new_status == "available":
            await self.process_queue()
    
    async def handle_call_ended(self, event: Event):
        """Handle call ended event"""
        call_id = event.data.get("call_id")
        agent_id = event.data.get("agent_id")
        
        # Update call record
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if call:
            call.call_end = datetime.utcnow()
            call.status = "completed"
            if call.call_start:
                call.duration = int((call.call_end - call.call_start).total_seconds())
        
        # Update agent status
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.status = "available"
        
        self.db.commit()
        
        # Process queue for next call
        await self.process_queue()
    
    async def process_queue(self):
        """Process waiting queue and assign calls to available agents"""
        # Get highest priority queued call
        queued_call = self.db.query(CallQueue).filter(
            CallQueue.assigned_agent_id.is_(None)
        ).order_by(
            CallQueue.priority.desc(),
            CallQueue.created_at.asc()
        ).first()
        
        if queued_call:
            available_agent = self.find_best_agent()
            if available_agent:
                # Assign the call
                await self.assign_call_to_agent(queued_call.caller_phone, available_agent.id)
                
                # Remove from queue
                queued_call.assigned_agent_id = available_agent.id
                self.db.commit()
