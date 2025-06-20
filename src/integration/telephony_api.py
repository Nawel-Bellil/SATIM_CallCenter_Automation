import asyncio
import aiohttp
import json
from typing import Dict, Optional, Callable
from datetime import datetime
import logging

from ..orchestration.event_bus import event_bus, Event

logger = logging.getLogger(__name__)

class TelephonyConnector:
    """Connector for telephony system integration"""
    
    def __init__(self, telephony_base_url: str, api_key: str):
        self.base_url = telephony_base_url.rstrip('/')
        self.api_key = api_key
        self.session = None
        self.active_calls = {}
        self.setup_event_handlers()
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def setup_event_handlers(self):
        """Setup event handlers for telephony integration"""
        event_bus.subscribe("call_assigned", self.handle_call_assignment)
        event_bus.subscribe("call_ended", self.handle_call_end)
        event_bus.subscribe("agent_status_changed", self.update_agent_status)
    
    async def handle_incoming_call(self, call_data: Dict):
        """Handle incoming call from telephony system"""
        caller_phone = call_data.get("caller_id")
        call_session_id = call_data.get("session_id")
        
        logger.info(f"Incoming call from {caller_phone}")
        
        # Store call session
        self.active_calls[call_session_id] = {
            "caller_phone": caller_phone,
            "start_time": datetime.utcnow(),
            "status": "ringing"
        }
        
        # Publish incoming call event
        await event_bus.publish(Event(
            type="call_incoming",
            data={
                "caller_phone": caller_phone,
                "session_id": call_session_id,
                "priority": call_data.get("priority", 1)
            },
            timestamp=datetime.utcnow(),
            correlation_id=f"incoming_{call_session_id}"
        ))
    
    async def handle_call_assignment(self, event: Event):
        """Handle call assignment to agent"""
        call_id = event.data.get("call_id")
        agent_id = event.data.get("agent_id")
        caller_phone = event.data.get("caller_phone")
        
        try:
            # Route call to agent through telephony system
            await self.route_call_to_agent(caller_phone, agent_id)
            
            logger.info(f"Call {call_id} routed to agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error routing call {call_id}: {e}")
    
    async def route_call_to_agent(self, caller_phone: str, agent_id: int):
        """Route call to specific agent via telephony API"""
        if not self.session:
            raise RuntimeError("Telephony session not initialized")
        
        routing_data = {
            "caller_phone": caller_phone,
            "agent_id": agent_id,
            "action": "route"
        }
        
        async with self.session.post(
            f"{self.base_url}/calls/route",
            json=routing_data
        ) as response:
            if response.status not in [200, 201]:
                error_text = await response.text()
                raise Exception(f"Failed to route call: {error_text}")
    
    async def handle_call_end(self, event: Event):
        """Handle call end event"""
        call_id = event.data.get("call_id")
        
        try:
            # End call in telephony system
            await self.end_call(call_id)
            
            logger.info(f"Call {call_id} ended in telephony system")
            
        except Exception as e:
            logger.error(f"Error ending call {call_id}: {e}")
    
    async def end_call(self, call_id: int):
        """End call in telephony system"""
        if not self.session:
            raise RuntimeError("Telephony session not initialized")
        
        async with self.session.post(
            f"{self.base_url}/calls/{call_id}/end"
        ) as response:
            if response.status not in [200, 204]:
                error_text = await response.text()
                logger.warning(f"Failed to end call in telephony system: {error_text}")
    
    async def update_agent_status(self, event: Event):
        """Update agent status in telephony system"""
        agent_id = event.data.get("agent_id")
        status = event.data.get("status")
        
        try:
            await self.set_agent_telephony_status(agent_id, status)
        except Exception as e:
            logger.error(f"Error updating agent {agent_id} telephony status: {e}")
    
    async def set_agent_telephony_status(self, agent_id: int, status: str):
        """Set agent status in telephony system"""
        if not self.session:
            return
        
        status_data = {
            "agent_id": agent_id,
            "status": status
        }
        
        async with self.session.put(
            f"{self.base_url}/agents/{agent_id}/status",
            json=status_data
        ) as response:
            if response.status not in [200, 204]:
                error_text = await response.text()
                logger.warning(f"Failed to update agent telephony status: {error_text}")
    
    async def start_call_recording(self, call_id: int) -> str:
        """Start call recording"""
        if not self.session:
            raise RuntimeError("Telephony session not initialized")
        
        async with self.session.post(
            f"{self.base_url}/calls/{call_id}/record/start"
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("recording_id")
            else:
                error_text = await response.text()
                raise Exception(f"Failed to start recording: {error_text}")
    
    async def stop_call_recording(self, call_id: int, recording_id: str) -> str:
        """Stop call recording and get file path"""
        if not self.session:
            raise RuntimeError("Telephony session not initialized")
        
        async with self.session.post(
            f"{self.base_url}/calls/{call_id}/record/stop",
            json={"recording_id": recording_id}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("file_path")
            else:
                error_text = await response.text()
                raise Exception(f"Failed to stop recording: {error_text}")
