# File: src/agents/data_entry.py
import asyncio
import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from ..models import Call
from ..orchestration.event_bus import event_bus, Event

logger = logging.getLogger(__name__)

class DataEntryAgent:
    def __init__(self, db: Session):
        self.db = db
        self.extraction_patterns = self.load_extraction_patterns()
        self.form_templates = self.load_form_templates()
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Setup event handlers for data entry automation"""
        event_bus.subscribe("transcript_completed", self.extract_information)
        event_bus.subscribe("transcript_chunk", self.process_real_time_data)
        event_bus.subscribe("form_submission_requested", self.handle_form_submission)
    
    def load_extraction_patterns(self) -> Dict[str, Dict[str, str]]:
        """Load patterns for extracting different types of information"""
        return {
            "personal_info": {
                "name": r"(?:my name is|i am|je m'appelle|je suis)\s+([A-Za-z\s]+)",
                "phone": r"(?:phone|telephone|numero|tel)\s*(?:is|est)?\s*([0-9\s\-\+\(\)]{8,15})",
                "email": r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                "address": r"(?:address|adresse|habite|live at)\s*(?:is|est)?\s*([A-Za-z0-9\s,.-]+)",
                "cin": r"(?:CIN|carte d'identité|identity|numero)\s*(?:is|est)?\s*([0-9]{8})",
                "age": r"(?:age|âge)\s*(?:is|est)?\s*([0-9]{1,3})"
            },
            "banking": {
                "account_number": r"(?:account|compte)\s*(?:number|numero)?\s*([0-9]{10,20})",
                "rib": r"(?:RIB|RIP)\s*([0-9]{20,23})",
                "amount": r"(?:amount|montant|somme)\s*(?:of|de)?\s*([0-9,.\s]+)\s*(?:DA|DZD|dinars?)",
                "transaction_id": r"(?:transaction|operation)\s*(?:id|numero)?\s*([A-Z0-9]{6,20})"
            },
            "complaint": {
                "issue_type": r"(?:problem|problème|issue|souci)\s*(?:with|avec|is|est)\s*([A-Za-z\s]+)",
                "description": r"(?:describe|décrire|explain|expliquer)\s*(?:the)?\s*([A-Za-z0-9\s,.!?-]{20,200})",
                "urgency": r"(?:urgent|priority|priorité|emergency|urgence)",
                "previous_contact": r"(?:called|appelé|contacted|contacté)\s*(?:before|avant|already|déjà)"
            },
            "service_request": {
                "service_type": r"(?:need|besoin|want|veux|request|demande)\s*(?:to|de)?\s*([A-Za-z\s]+)",
                "appointment": r"(?:appointment|rendez-vous)\s*(?:on|le)?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
                "branch": r"(?:branch|agence|office|bureau)\s*(?:of|de|in|à)?\s*([A-Za-z\s]+)"
            }
        }
    
    def load_form_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load form templates for different types of requests"""
        return {
            "customer_information": {
                "fields": ["name", "phone", "email", "address", "cin", "age"],
                "required": ["name", "phone"],
                "validation": {
                    "phone": r"^[0-9\s\-\+\(\)]{8,15}$",
                    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                    "cin": r"^[0-9]{8}$"
                }
            },
            "banking_request": {
                "fields": ["account_number", "rib", "amount", "transaction_id", "service_type"],
                "required": ["account_number"],
                "validation": {
                    "account_number": r"^[0-9]{10,20}$",
                    "rib": r"^[0-9]{20,23}$"
                }
            },
            "complaint_form": {
                "fields": ["issue_type", "description", "urgency", "previous_contact"],
                "required": ["issue_type", "description"],
                "validation": {}
            },
            "service_request": {
                "fields": ["service_type", "appointment", "branch"],
                "required": ["service_type"],
                "validation": {
                    "appointment": r"^[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}$"
                }
            }
        }
    
    async def extract_information(self, event: Event):
        """Extract structured information from completed transcript"""
        call_id = event.data.get("call_id")
        transcript = event.data.get("transcript", "")
        caller_phone = event.data.get("caller_phone", "")
        
        logger.info(f"Extracting information from call {call_id}")
        
        # Extract information using patterns
        extracted_data = self.extract_from_text(transcript)
        
        # Determine form type based on extracted data
        form_type = self.determine_form_type(extracted_data)
        
        # Validate and structure the data
        structured_data = self.structure_data(extracted_data, form_type)
        
        # Store extracted data
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if call:
            call.summary = json.dumps(structured_data, ensure_ascii=False, indent=2)
            self.db.commit()
        
        # Publish data extraction event
        await event_bus.publish(Event(
            type="data_extracted",
            data={
                "call_id": call_id,
                "caller_phone": caller_phone,
                "extracted_data": structured_data,
                "form_type": form_type,
                "confidence": self.calculate_confidence(structured_data)
            },
            timestamp=datetime.utcnow(),
            correlation_id=f"data_extract_{call_id}"
        ))
        
        logger.info(f"Data extraction completed for call {call_id}: {form_type}")
    
    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """Extract information from text using regex patterns"""
        extracted = {}
        text_lower = text.lower()
        
        for category, patterns in self.extraction_patterns.items():
            extracted[category] = {}
            
            for field, pattern in patterns.items():
                matches = re.findall(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
                if matches:
                    # Take the first match and clean it up
                    value = matches[0].strip()
                    extracted[category][field] = value
        
        return extracted
    
    def determine_form_type(self, extracted_data: Dict[str, Any]) -> str:
        """Determine the most appropriate form type based on extracted data"""
        scores = {}
        
        for form_type, template in self.form_templates.items():
            score = 0
            for field in template["fields"]:
                # Check if field exists in any category
                for category_data in extracted_data.values():
                    if field in category_data:
                        score += 2 if field in template["required"] else 1
            
            scores[form_type] = score
        
        # Return the form type with highest score
        if scores:
            return max(scores, key=scores.get)
        
        return "customer_information"  # Default
    
    def structure_data(self, extracted_data: Dict[str, Any], form_type: str) -> Dict[str, Any]:
        """Structure extracted data according to form template"""
        template = self.form_templates.get(form_type, self.form_templates["customer_information"])
        structured = {
            "form_type": form_type,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": {},
            "validation_errors": [],
            "completion_status": "partial"
        }
        
        # Flatten extracted data
        flat_data = {}
        for category_data in extracted_data.values():
            flat_data.update(category_data)
        
        # Map fields according to template
        for field in template["fields"]:
            if field in flat_data:
                value = flat_data[field]
                
                # Validate field if validation pattern exists
                validation_pattern = template["validation"].get(field)
                if validation_pattern:
                    if not re.match(validation_pattern, value):
                        structured["validation_errors"].append({
                            "field": field,
                            "value": value,
                            "error": "Invalid format"
                        })
                        continue
                
                structured["fields"][field] = self.clean_field_value(field, value)
        
        # Check completion status
        required_fields = template["required"]
        completed_required = sum(1 for field in required_fields if field in structured["fields"])
        
        if completed_required == len(required_fields):
            structured["completion_status"] = "complete"
        elif completed_required > 0:
            structured["completion_status"] = "partial"
        else:
            structured["completion_status"] = "minimal"
        
        return structured
    
    def clean_field_value(self, field: str, value: str) -> str:
        """Clean and format field values"""
        value = value.strip()
        
        if field == "phone":
            # Normalize phone number
            value = re.sub(r'[^\d\+]', '', value)
            if value.startswith('0'):
                value = '+213' + value[1:]
        
        elif field == "email":
            value = value.lower()
        
        elif field == "name":
            value = value.title()
        
        elif field == "amount":
            # Extract numeric value
            value = re.sub(r'[^\d,.]', '', value)
        
        return value
    
    def calculate_confidence(self, structured_data: Dict[str, Any]) -> float:
        """Calculate confidence score for extracted data"""
        total_fields = len(structured_data.get("fields", {}))
        errors = len(structured_data.get("validation_errors", []))
        completion = structured_data.get("completion_status", "minimal")
        
        if total_fields == 0:
            return 0.0
        
        base_score = min(total_fields / 5.0, 1.0)  # Up to 5 fields = 100%
        error_penalty = errors * 0.1
        
        completion_bonus = {
            "complete": 0.2,
            "partial": 0.1,
            "minimal": 0.0
        }.get(completion, 0.0)
        
        confidence = max(0.0, min(1.0, base_score - error_penalty + completion_bonus))
        return round(confidence, 2)
    
    async def process_real_time_data(self, event: Event):
        """Process data in real-time as transcript chunks arrive"""
        call_id = event.data.get("call_id")
        chunk = event.data.get("chunk", {})
        text = chunk.get("text", "")
        
        # Extract information from this chunk
        extracted = self.extract_from_text(text)
        
        # If we found something important, publish an event
        if any(extracted.values()):
            await event_bus.publish(Event(
                type="real_time_data_found",
                data={
                    "call_id": call_id,
                    "chunk_data": extracted,
                    "timestamp": chunk.get("timestamp")
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"realtime_{call_id}"
            ))
    
    async def handle_form_submission(self, event: Event):
        """Handle form submission requests"""
        call_id = event.data.get("call_id")
        form_data = event.data.get("form_data", {})
        destination = event.data.get("destination", "crm")
        
        logger.info(f"Submitting form for call {call_id} to {destination}")
        
        # Validate form data
        validation_result = self.validate_form_data(form_data)
        
        if validation_result["valid"]:
            # Submit to appropriate system
            submission_result = await self.submit_to_system(form_data, destination)
            
            await event_bus.publish(Event(
                type="form_submitted",
                data={
                    "call_id": call_id,
                    "destination": destination,
                    "success": submission_result["success"],
                    "reference": submission_result.get("reference"),
                    "errors": submission_result.get("errors", [])
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"submit_{call_id}"
            ))
        else:
            await event_bus.publish(Event(
                type="form_validation_failed",
                data={
                    "call_id": call_id,
                    "validation_errors": validation_result["errors"]
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"validation_fail_{call_id}"
            ))
    
    def validate_form_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate form data before submission"""
        errors = []
        form_type = form_data.get("form_type", "customer_information")
        template = self.form_templates.get(form_type, {})
        
        # Check required fields
        required_fields = template.get("required", [])
        for field in required_fields:
            if field not in form_data.get("fields", {}):
                errors.append(f"Required field '{field}' is missing")
        
        # Validate field formats
        validation_rules = template.get("validation", {})
        fields = form_data.get("fields", {})
        
        for field, value in fields.items():
            if field in validation_rules:
                pattern = validation_rules[field]
                if not re.match(pattern, str(value)):
                    errors.append(f"Field '{field}' has invalid format")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def submit_to_system(self, form_data: Dict[str, Any], destination: str) -> Dict[str, Any]:
        """Submit form data to external system"""
        try:
            # This would integrate with actual CRM/ERP systems
            # For now, we'll simulate submission
            
            if destination == "crm":
                return await self.submit_to_crm(form_data)
            elif destination == "banking":
                return await self.submit_to_banking_system(form_data)
            elif destination == "complaint":
                return await self.submit_to_complaint_system(form_data)
            else:
                return {"success": False, "errors": ["Unknown destination system"]}
                
        except Exception as e:
            logger.error(f"Error submitting form to {destination}: {e}")
            return {"success": False, "errors": [str(e)]}
    
    async def submit_to_crm(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit to CRM system"""
        # Simulate CRM submission
        reference = f"CRM_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        return {
            "success": True,
            "reference": reference,
            "message": "Customer information updated successfully"
        }
    
    async def submit_to_banking_system(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit to banking system"""
        # Simulate banking system submission
        reference = f"BANK_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        return {
            "success": True,
            "reference": reference,
            "message": "Banking request processed successfully"
        }
    
    async def submit_to_complaint_system(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit to complaint management system"""
        # Simulate complaint system submission
        reference = f"COMP_{datetime.utcnow().strftime('%Y%m%d_%H