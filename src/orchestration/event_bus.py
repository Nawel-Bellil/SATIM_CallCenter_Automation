"""Event bus for inter-agent communication"""
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
