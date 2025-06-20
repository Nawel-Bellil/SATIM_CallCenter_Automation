import asyncio
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from transformers import pipeline
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import logging
from ..models import FAQ
from ..orchestration.event_bus import event_bus, Event
from datetime import datetime

logger = logging.getLogger(__name__)

class FAQBot:
    def __init__(self, db: Session):
        self.db = db
        self.vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        self.faq_vectors = None
        self.faqs = []
        self.confidence_threshold = 0.7
        self.setup_event_handlers()
        self.load_faqs()
    
    def setup_event_handlers(self):
        """Setup event handlers for FAQ processing"""
        event_bus.subscribe("question_asked", self.handle_question)
        event_bus.subscribe("faq_updated", self.reload_faqs)
    
    def load_faqs(self):
        """Load FAQs from database and create vectors"""
        try:
            self.faqs = self.db.query(FAQ).all()
            if self.faqs:
                questions = [faq.question for faq in self.faqs]
                self.faq_vectors = self.vectorizer.fit_transform(questions)
                logger.info(f"Loaded {len(self.faqs)} FAQs")
            else:
                logger.warning("No FAQs found in database")
        except Exception as e:
            logger.error(f"Error loading FAQs: {e}")
    
    async def handle_question(self, event: Event):
        """Handle incoming question"""
        question = event.data.get("question", "")
        caller_phone = event.data.get("caller_phone", "")
        call_id = event.data.get("call_id")
        
        logger.info(f"Processing question from {caller_phone}: {question}")
        
        # Find best matching FAQ
        best_match = self.find_best_match(question)
        
        if best_match:
            faq, confidence = best_match
            
            # Update usage count
            faq.usage_count += 1
            self.db.commit()
            
            # Publish response event
            await event_bus.publish(Event(
                type="faq_response_generated",
                data={
                    "call_id": call_id,
                    "caller_phone": caller_phone,
                    "question": question,
                    "answer": faq.answer,
                    "confidence": confidence,
                    "faq_id": faq.id,
                    "category": faq.category
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"faq_{faq.id}"
            ))
            
            logger.info(f"FAQ response sent (confidence: {confidence:.2f})")
        else:
            # No suitable FAQ found
            await event_bus.publish(Event(
                type="faq_no_match",
                data={
                    "call_id": call_id,
                    "caller_phone": caller_phone,
                    "question": question
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"no_match_{call_id}"
            ))
            
            logger.info("No suitable FAQ match found")
    
    def find_best_match(self, question: str) -> Optional[Tuple[FAQ, float]]:
        """Find best matching FAQ for given question"""
        if not self.faqs or self.faq_vectors is None:
            return None
        
        try:
            # Preprocess question
            processed_question = self.preprocess_question(question)
            
            # Transform question to vector
            question_vector = self.vectorizer.transform([processed_question])
            
            # Calculate similarities
            similarities = cosine_similarity(question_vector, self.faq_vectors)[0]
            
            # Find best match
            best_idx = np.argmax(similarities)
            best_score = similarities[best_idx]
            
            if best_score >= self.confidence_threshold:
                return self.faqs[best_idx], best_score
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding FAQ match: {e}")
            return None
    
    def preprocess_question(self, question: str) -> str:
        """Preprocess question for better matching"""
        # Convert to lowercase
        question = question.lower()
        
        # Remove special characters and extra spaces
        question = re.sub(r'[^\w\s]', ' ', question)
        question = re.sub(r'\s+', ' ', question).strip()
        
        return question
    
    async def reload_faqs(self, event: Event):
        """Reload FAQs when updated"""
        logger.info("Reloading FAQs...")
        self.load_faqs()
    
    def add_faq(self, question: str, answer: str, category: str = None) -> FAQ:
        """Add new FAQ to database"""
        faq = FAQ(
            question=question,
            answer=answer,
            category=category
        )
        self.db.add(faq)
        self.db.commit()
        
        # Trigger reload
        asyncio.create_task(event_bus.publish(Event(
            type="faq_updated",
            data={"faq_id": faq.id},
            timestamp=datetime.utcnow(),
            correlation_id=f"faq_add_{faq.id}"
        )))
        
        return faq
    
    def get_faq_stats(self) -> dict:
        """Get FAQ usage statistics"""
        total_faqs = len(self.faqs)
        total_usage = sum(faq.usage_count for faq in self.faqs)
        
        category_stats = {}
        for faq in self.faqs:
            category = faq.category or "Uncategorized"
            if category not in category_stats:
                category_stats[category] = {"count": 0, "usage": 0}
            category_stats[category]["count"] += 1
            category_stats[category]["usage"] += faq.usage_count
        
        return {
            "total_faqs": total_faqs,
            "total_usage": total_usage,
            "categories": category_stats,
            "most_used": max(self.faqs, key=lambda x: x.usage_count) if self.faqs else None
        }
