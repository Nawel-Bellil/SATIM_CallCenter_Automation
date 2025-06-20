import asyncio
import json
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class Event:
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    correlation_id: str

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: List[Event] = []
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed handler to {event_type}")
    
    async def publish(self, event: Event):
        """Publish an event to all subscribers"""
        self.event_history.append(event)
        logger.info(f"Publishing event: {event.type}")
        
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")
    
    def get_event_history(self, event_type: str = None) -> List[Event]:
        """Get event history, optionally filtered by type"""
        if event_type:
            return [e for e in self.event_history if e.type == event_type]
        return self.event_history

# Global event bus instance
event_bus = EventBus()