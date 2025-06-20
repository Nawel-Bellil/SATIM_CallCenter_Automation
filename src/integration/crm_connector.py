import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from ..orchestration.event_bus import event_bus, Event

logger = logging.getLogger(__name__)

class CRMConnector:
    """Connector for integrating with CRM systems"""
    
    def __init__(self, crm_base_url: str, api_key: str):
        self.base_url = crm_base_url.rstrip('/')
        self.api_key = api_key
        self.session = None
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
        """Setup event handlers for CRM integration"""
        event_bus.subscribe("data_extracted", self.handle_data_extracted)
        event_bus.subscribe("call_ended", self.handle_call_ended)
        event_bus.subscribe("customer_info_updated", self.handle_customer_update)
    
    async def handle_data_extracted(self, event: Event):
        """Handle extracted data and sync with CRM"""
        call_id = event.data.get("call_id")
        extracted_data = event.data.get("extracted_data", {})
        
        logger.info(f"Syncing extracted data to CRM for call {call_id}")
        
        try:
            # Extract customer information
            customer_data = self.prepare_customer_data(extracted_data)
            
            if customer_data:
                # Create or update customer in CRM
                customer_id = await self.create_or_update_customer(customer_data)
                
                # Create interaction record
                if customer_id:
                    await self.create_interaction_record(customer_id, call_id, extracted_data)
                
                # Publish success event
                await event_bus.publish(Event(
                    type="crm_sync_completed",
                    data={
                        "call_id": call_id,
                        "customer_id": customer_id,
                        "success": True
                    },
                    timestamp=datetime.utcnow(),
                    correlation_id=f"crm_{call_id}"
                ))
                
        except Exception as e:
            logger.error(f"Error syncing to CRM for call {call_id}: {e}")
            
            # Publish error event
            await event_bus.publish(Event(
                type="crm_sync_error",
                data={
                    "call_id": call_id,
                    "error": str(e),
                    "success": False
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"crm_error_{call_id}"
            ))
    
    def prepare_customer_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare customer data for CRM from extracted data"""
        customer_data = {}
        
        # Map extracted data to CRM fields
        field_mappings = {
            "customer_name": "name",
            "phone": "phone_number",
            "email": "email_address",
            "address": "address",
            "account_number": "account_id"
        }
        
        for extracted_field, crm_field in field_mappings.items():
            if extracted_field in extracted_data:
                value = extracted_data[extracted_field]
                if isinstance(value, list) and value:
                    customer_data[crm_field] = value[0]  # Take first value
                elif isinstance(value, str):
                    customer_data[crm_field] = value
        
        return customer_data
    
    async def create_or_update_customer(self, customer_data: Dict[str, Any]) -> Optional[str]:
        """Create or update customer in CRM"""
        if not self.session:
            raise RuntimeError("CRM session not initialized")
        
        try:
            # First, try to find existing customer
            customer_id = await self.find_customer(customer_data)
            
            if customer_id:
                # Update existing customer
                await self.update_customer(customer_id, customer_data)
                return customer_id
            else:
                # Create new customer
                return await self.create_customer(customer_data)
                
        except Exception as e:
            logger.error(f"Error creating/updating customer: {e}")
            raise
    
    async def find_customer(self, customer_data: Dict[str, Any]) -> Optional[str]:
        """Find existing customer by phone or email"""
        search_fields = ["phone_number", "email_address", "account_id"]
        
        for field in search_fields:
            if field in customer_data:
                try:
                    async with self.session.get(
                        f"{self.base_url}/customers/search",
                        params={field: customer_data[field]}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("customers"):
                                return data["customers"][0]["id"]
                except Exception as e:
                    logger.warning(f"Error searching customer by {field}: {e}")
        
        return None
    
    async def create_customer(self, customer_data: Dict[str, Any]) -> str:
        """Create new customer in CRM"""
        async with self.session.post(
            f"{self.base_url}/customers",
            json=customer_data
        ) as response:
            if response.status in [200, 201]:
                data = await response.json()
                return data["customer"]["id"]
            else:
                error_text = await response.text()
                raise Exception(f"Failed to create customer: {error_text}")
    
    async def update_customer(self, customer_id: str, customer_data: Dict[str, Any]):
        """Update existing customer in CRM"""
        async with self.session.put(
            f"{self.base_url}/customers/{customer_id}",
            json=customer_data
        ) as response:
            if response.status not in [200, 204]:
                error_text = await response.text()
                raise Exception(f"Failed to update customer: {error_text}")
    
    async def create_interaction_record(self, customer_id: str, call_id: int, extracted_data: Dict[str, Any]):
        """Create interaction record in CRM"""
        interaction_data = {
            "customer_id": customer_id,
            "type": "phone_call",
            "channel": "call_center",
            "call_id": call_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": extracted_data,
            "issue_type": extracted_data.get("issue_type"),
            "resolution": extracted_data.get("resolution")
        }
        
        async with self.session.post(
            f"{self.base_url}/interactions",
            json=interaction_data
        ) as response:
            if response.status not in [200, 201]:
                error_text = await response.text()
                logger.warning(f"Failed to create interaction record: {error_text}")
    
    async def handle_call_ended(self, event: Event):
        """Handle call ended event for final CRM sync"""
        call_id = event.data.get("call_id")
        
        # Final sync of call outcome
        try:
            await self.update_call_outcome(call_id)
        except Exception as e:
            logger.error(f"Error updating call outcome in CRM: {e}")
    
    async def update_call_outcome(self, call_id: int):
        """Update call outcome in CRM"""
        # This would typically fetch the final call data and update CRM
        pass
    
    async def handle_customer_update(self, event: Event):
        """Handle customer information updates"""
        customer_data = event.data.get("customer_data", {})
        
        try:
            await self.create_or_update_customer(customer_data)
        except Exception as e:
            logger.error(f"Error handling customer update: {e}")