# src/orchestration/event_bus.py - Add this if missing
import asyncio
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
    correlation_id: str = None

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Handler subscribed to {event_type}")
    
    async def publish(self, event: Event):
        """Publish an event to all subscribers"""
        if event.type in self.subscribers:
            tasks = []
            for handler in self.subscribers[event.type]:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(event))
                else:
                    # Handle sync functions
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Error in sync handler: {e}")
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.debug(f"Event published: {event.type}")

# Global event bus instance
event_bus = EventBus()