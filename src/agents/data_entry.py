import asyncio
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from ..models import Call, Agent
from ..orchestration.event_bus import event_bus, Event

logger = logging.getLogger(__name__)

class DataEntryAutomator:
    """Automates data entry from call transcripts"""
    
    def __init__(self, db: Session):
        self.db = db
        self.extraction_patterns = self.load_extraction_patterns()
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Setup event handlers for data entry automation"""
        event_bus.subscribe("call_transcript_ready", self.handle_transcript)
        event_bus.subscribe("call_ended", self.finalize_data_entry)
    
    def load_extraction_patterns(self) -> Dict[str, str]:
        """Load regex patterns for data extraction"""
        return {
            "phone": r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "account_number": r"\b(?:account|compte)\s*(?:number|numéro)?\s*:?\s*([A-Z0-9]{8,12})\b",
            "transaction_id": r"\b(?:transaction|trans)\s*(?:id|number)?\s*:?\s*([A-Z0-9]{10,20})\b",
            "amount": r"\b(?:€|EUR|DA|DZD)?\s*([0-9,]+\.?[0-9]*)\s*(?:€|EUR|DA|DZD)?\b",
            "date": r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
            "card_number": r"\b(?:carte|card)\s*(?:number|numéro)?\s*:?\s*([0-9]{4}[-\s]*[0-9]{4}[-\s]*[0-9]{4}[-\s]*[0-9]{4})\b"
        }
    
    async def handle_transcript(self, event: Event):
        """Handle call transcript for data extraction"""
        call_id = event.data.get("call_id")
        transcript = event.data.get("transcript", "")
        
        logger.info(f"Processing transcript for call {call_id}")
        
        # Extract structured data from transcript
        extracted_data = self.extract_data_from_transcript(transcript)
        
        # Update call record with extracted data
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if call:
            call.transcript = transcript
            
            # Store extracted data as JSON in summary field for now
            # In production, you'd have dedicated fields or related tables
            call.summary = json.dumps(extracted_data, ensure_ascii=False)
            self.db.commit()
            
            # Publish data extraction event
            await event_bus.publish(Event(
                type="data_extracted",
                data={
                    "call_id": call_id,
                    "extracted_data": extracted_data,
                    "fields_found": len(extracted_data)
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"extract_{call_id}"
            ))
            
            logger.info(f"Extracted {len(extracted_data)} data fields from call {call_id}")
    
    def extract_data_from_transcript(self, transcript: str) -> Dict[str, Any]:
        """Extract structured data from transcript using NLP and regex"""
        extracted = {}
        
        # Apply regex patterns
        for field_name, pattern in self.extraction_patterns.items():
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            if matches:
                if field_name == "phone":
                    # Join phone number parts
                    extracted[field_name] = [f"({match[0]}) {match[1]}-{match[2]}" for match in matches]
                else:
                    extracted[field_name] = matches
        
        # Extract customer information using keyword matching
        customer_info = self.extract_customer_info(transcript)
        if customer_info:
            extracted.update(customer_info)
        
        # Extract issue/request type
        issue_type = self.classify_issue_type(transcript)
        if issue_type:
            extracted["issue_type"] = issue_type
        
        # Extract resolution status
        resolution = self.extract_resolution_status(transcript)
        if resolution:
            extracted["resolution"] = resolution
        
        return extracted
    
    def extract_customer_info(self, transcript: str) -> Dict[str, str]:
        """Extract customer information from transcript"""
        info = {}
        
        # Name patterns
        name_patterns = [
            r"(?:my name is|je suis|I am)\s+([A-Za-z\s]+)",
            r"(?:customer|client)\s+name\s*:?\s*([A-Za-z\s]+)",
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                info["customer_name"] = match.group(1).strip()
                break
        
        # Address patterns
        address_patterns = [
            r"(?:address|adresse)\s*:?\s*([^.!?]+)",
            r"(?:I live at|j'habite à)\s+([^.!?]+)"
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                info["address"] = match.group(1).strip()
                break
        
        return info
    
    def classify_issue_type(self, transcript: str) -> Optional[str]:
        """Classify the type of issue/request from transcript"""
        issue_keywords = {
            "carte_bloquée": ["carte bloquée", "card blocked", "blocked card", "carte ne marche pas"],
            "transaction_échouée": ["transaction failed", "paiement échoué", "payment failed", "transaction échouée"],
            "solde_insuffisant": ["insufficient funds", "solde insuffisant", "pas assez d'argent"],
            "fraude": ["fraud", "fraude", "suspicious transaction", "transaction suspecte"],
            "activation_carte": ["activate card", "activer carte", "nouvelle carte"],
            "changement_pin": ["change pin", "changer code", "forgot pin", "code oublié"],
            "demande_relevé": ["statement", "relevé", "historique", "transactions history"]
        }
        
        transcript_lower = transcript.lower()
        
        for issue_type, keywords in issue_keywords.items():
            for keyword in keywords:
                if keyword.lower() in transcript_lower:
                    return issue_type
        
        return None
    
    def extract_resolution_status(self, transcript: str) -> Optional[str]:
        """Extract resolution status from transcript"""
        resolution_keywords = {
            "résolu": ["resolved", "fixed", "résolu", "corrigé", "problem solved"],
            "en_cours": ["in progress", "en cours", "working on it", "nous vérifions"],
            "escaladé": ["escalated", "escaladé", "transferred", "transféré"],
            "non_résolu": ["unresolved", "non résolu", "couldn't help", "pas pu aider"]
        }
        
        transcript_lower = transcript.lower()
        
        for status, keywords in resolution_keywords.items():
            for keyword in keywords:
                if keyword.lower() in transcript_lower:
                    return status
        
        return None
    
    async def finalize_data_entry(self, event: Event):
        """Finalize data entry when call ends"""
        call_id = event.data.get("call_id")
        
        call = self.db.query(Call).filter(Call.id == call_id).first()
        if call and call.summary:
            try:
                extracted_data = json.loads(call.summary)
                
                # Validate and clean extracted data
                validated_data = self.validate_extracted_data(extracted_data)
                
                # Update with validated data
                call.summary = json.dumps(validated_data, ensure_ascii=False)
                
                # Mark call as resolved if resolution was found
                if validated_data.get("resolution") == "résolu":
                    call.resolved = True
                
                self.db.commit()
                
                # Publish completion event
                await event_bus.publish(Event(
                    type="data_entry_completed",
                    data={
                        "call_id": call_id,
                        "validated_data": validated_data,
                        "resolved": call.resolved
                    },
                    timestamp=datetime.utcnow(),
                    correlation_id=f"complete_{call_id}"
                ))
                
                logger.info(f"Data entry finalized for call {call_id}")
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in call summary for call {call_id}")
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted data"""
        validated = {}
        
        for key, value in data.items():
            if key == "phone" and isinstance(value, list):
                # Validate phone numbers
                valid_phones = []
                for phone in value:
                    if len(re.sub(r'[^\d]', '', phone)) == 10:  # US format
                        valid_phones.append(phone)
                if valid_phones:
                    validated[key] = valid_phones
            
            elif key == "email" and isinstance(value, list):
                # Validate emails
                valid_emails = []
                for email in value:
                    if "@" in email and "." in email:
                        valid_emails.append(email.lower())
                if valid_emails:
                    validated[key] = valid_emails
            
            elif key == "amount" and isinstance(value, list):
                # Clean and validate amounts
                valid_amounts = []
                for amount in value:
                    cleaned_amount = re.sub(r'[^\d.,]', '', str(amount))
                    if cleaned_amount:
                        valid_amounts.append(cleaned_amount)
                if valid_amounts:
                    validated[key] = valid_amounts
            
            else:
                validated[key] = value
        
        return validated
