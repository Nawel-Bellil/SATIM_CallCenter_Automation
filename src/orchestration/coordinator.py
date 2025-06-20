import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..agents.call_routing import CallRouter
from ..agents.faq_bot import FAQBot
from ..agents.data_entry import DataEntryAutomator
from ..agents.speech_to_text import SpeechToTextProcessor
from ..integration.crm_connector import CRMConnector
from ..integration.telephony_api import TelephonyConnector
from .event_bus import event_bus, Event

logger = logging.getLogger(__name__)

class SystemCoordinator:
    """Main coordinator for the call center automation system"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.db = SessionLocal()
        self.components = {}
        self.running = False
        
        # Initialize components
        self.initialize_components()
        self.setup_event_handlers()
    
    def initialize_components(self):
        """Initialize all system components"""
        logger.info("Initializing system components...")
        
        # Core agents
        self.components['call_router'] = CallRouter(self.db)
        self.components['faq_bot'] = FAQBot(self.db)
        self.components['data_entry'] = DataEntryAutomator(self.db)
        self.components['speech_processor'] = SpeechToTextProcessor()
        
        # External integrations
        if self.config.get('crm_enabled'):
            self.components['crm_connector'] = CRMConnector(
                self.config['crm_base_url'],
                self.config['crm_api_key']
            )
        
        if self.config.get('telephony_enabled'):
            self.components['telephony_connector'] = TelephonyConnector(
                self.config['telephony_base_url'],
                self.config['telephony_api_key']
            )
        
        logger.info(f"Initialized {len(self.components)} components")
    
    def setup_event_handlers(self):
        """Setup system-level event handlers"""
        event_bus.subscribe("system_start", self.handle_system_start)
        event_bus.subscribe("system_stop", self.handle_system_stop)
        event_bus.subscribe("health_check", self.handle_health_check)
        event_bus.subscribe("component_error", self.handle_component_error)
    
    async def start(self):
        """Start the system coordinator"""
        logger.info("Starting SATIM Call Center Automation System")
        self.running = True
        
        # Initialize async components
        for name, component in self.components.items():
            if hasattr(component, '__aenter__'):
                try:
                    await component.__aenter__()
                    logger.info(f"Started async component: {name}")
                except Exception as e:
                    logger.error(f"Failed to start {name}: {e}")
        
        # Publish system start event
        await event_bus.publish(Event(
            type="system_start",
            data={"timestamp": datetime.utcnow()},
            timestamp=datetime.utcnow(),
            correlation_id="system_start"
        ))
        
        # Start monitoring loop
        asyncio.create_task(self.monitoring_loop())
        
        logger.info("System coordinator started successfully")
    
    async def stop(self):
        """Stop the system coordinator"""
        logger.info("Stopping SATIM Call Center Automation System")
        self.running = False
        
        # Publish system stop event
        await event_bus.publish(Event(
            type="system_stop",
            data={"timestamp": datetime.utcnow()},
            timestamp=datetime.utcnow(),
            correlation_id="system_stop"
        ))
        
        # Stop async components
        for name, component in self.components.items():
            if hasattr(component, '__aexit__'):
                try:
                    await component.__aexit__(None, None, None)
                    logger.info(f"Stopped async component: {name}")
                except Exception as e:
                    logger.error(f"Error stopping {name}: {e}")
        
        # Close database connection
        self.db.close()
        
        logger.info("System coordinator stopped")
    
    async def monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Perform health checks
                await self.perform_health_checks()
                
                # Check system metrics
                await self.check_system_metrics()
                
                # Sleep for monitoring interval
                await asyncio.sleep(self.config.get('monitoring_interval', 30))
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)  # Short sleep on error
    
    async def perform_health_checks(self):
        """Perform health checks on system components"""
        health_status = {}
        
        for name, component in self.components.items():
            try:
                if hasattr(component, 'health_check'):
                    status = await component.health_check()
                else:
                    status = "healthy"  # Default for components without health check
                
                health_status[name] = status
                
            except Exception as e:
                health_status[name] = f"error: {str(e)}"
                logger.warning(f"Health check failed for {name}: {e}")
        
        # Publish health check event
        await event_bus.publish(Event(
            type="health_check",
            data={"component_status": health_status},
            timestamp=datetime.utcnow(),
            correlation_id="health_check"
        ))
    
    async def check_system_metrics(self):
        """Check and report system metrics"""
        try:
            from ..models import Agent, Call, CallQueue
            
            # Get current metrics
            metrics = {
                "active_calls": self.db.query(Call).filter(Call.status == "active").count(),
                "queue_length": self.db.query(CallQueue).filter(CallQueue.assigned_agent_id.is_(None)).count(),
                "available_agents": self.db.query(Agent).filter(Agent.status == "available").count(),
                "busy_agents": self.db.query(Agent).filter(Agent.status == "busy").count(),
                "event_history_size": len(event_bus.event_history)
            }
            
            # Check for alerts
            alerts = []
            if metrics["queue_length"] > self.config.get('queue_alert_threshold', 10):
                alerts.append(f"High queue length: {metrics['queue_length']}")
            
            if metrics["available_agents"] == 0 and metrics["queue_length"] > 0:
                alerts.append("No available agents with queued calls")
            
            # Publish metrics event
            await event_bus.publish(Event(
                type="system_metrics",
                data={
                    "metrics": metrics,
                    "alerts": alerts
                },
                timestamp=datetime.utcnow(),
                correlation_id="system_metrics"
            ))
            
            if alerts:
                logger.warning(f"System alerts: {alerts}")
                
        except Exception as e:
            logger.error(f"Error checking system metrics: {e}")
    
    async def handle_system_start(self, event: Event):
        """Handle system start event"""
        logger.info("System start event received")
    
    async def handle_system_stop(self, event: Event):
        """Handle system stop event"""
        logger.info("System stop event received")
    
    async def handle_health_check(self, event: Event):
        """Handle health check event"""
        component_status = event.data.get("component_status", {})
        
        # Check for unhealthy components
        unhealthy = [name for name, status in component_status.items() if status != "healthy"]
        
        if unhealthy:
            logger.warning(f"Unhealthy components detected: {unhealthy}")
            
            # Attempt to restart unhealthy components
            for component_name in unhealthy:
                await self.restart_component(component_name)
    
    async def handle_component_error(self, event: Event):
        """Handle component error event"""
        component_name = event.data.get("component_name")
        error = event.data.get("error")
        
        logger.error(f"Component error in {component_name}: {error}")
        
        # Attempt to restart the component
        await self.restart_component(component_name)
    
    async def restart_component(self, component_name: str):
        """Restart a specific component"""
        try:
            if component_name in self.components:
                component = self.components[component_name]
                
                # Stop component if it has async context
                if hasattr(component, '__aexit__'):
                    await component.__aexit__(None, None, None)
                
                # Reinitialize component
                self.initialize_single_component(component_name)
                
                # Start component if it has async context
                if hasattr(component, '__aenter__'):
                    await component.__aenter__()
                
                logger.info(f"Successfully restarted component: {component_name}")
                
        except Exception as e:
            logger.error(f"Failed to restart component {component_name}: {e}")
    
    def initialize_single_component(self, component_name: str):
        """Initialize a single component"""
        if component_name == 'call_router':
            self.components[component_name] = CallRouter(self.db)
        elif component_name == 'faq_bot':
            self.components[component_name] = FAQBot(self.db)
        elif component_name == 'data_entry':
            self.components[component_name] = DataEntryAutomator(self.db)
        elif component_name == 'speech_processor':
            self.components[component_name] = SpeechToTextProcessor()
        elif component_name == 'crm_connector' and self.config.get('crm_enabled'):
            self.components[component_name] = CRMConnector(
                self.config['crm_base_url'],
                self.config['crm_api_key']
            )
        elif component_name == 'telephony_connector' and self.config.get('telephony_enabled'):
            self.components[component_name] = TelephonyConnector(
                self.config['telephony_base_url'],
                self.config['telephony_api_key']
            )
    
    def get_system_status(self) -> Dict:
        """Get current system status"""
        return {
            "running": self.running,
            "components": list(self.components.keys()),
            "event_history_size": len(event_bus.event_history),
            "database_connected": bool(self.db)
        }