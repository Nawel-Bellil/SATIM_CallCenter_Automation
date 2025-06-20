import asyncio
import speech_recognition as sr
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import threading
import queue
import json
from ..orchestration.event_bus import event_bus, Event
from ..models import Call
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SpeechToTextAgent:
    def __init__(self, db: Session):
        self.db = db
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.active_transcriptions = {}
        self.setup_event_handlers()
        self.setup_microphone()
    
    def setup_event_handlers(self):
        """Setup event handlers for speech processing"""
        event_bus.subscribe("call_assigned", self.start_transcription)
        event_bus.subscribe("call_ended", self.stop_transcription)
        event_bus.subscribe("audio_chunk_received", self.process_audio_chunk)
    
    def setup_microphone(self):
        """Setup microphone for speech recognition"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
            logger.info("Microphone setup completed")
        except Exception as e:
            logger.error(f"Microphone setup failed: {e}")
    
    async def start_transcription(self, event: Event):
        """Start transcription for a call"""
        call_id = event.data.get("call_id")
        caller_phone = event.data.get("caller_phone")
        
        if call_id:
            logger.info(f"Starting transcription for call {call_id}")
            
            # Initialize transcription session
            self.active_transcriptions[call_id] = {
                "caller_phone": caller_phone,
                "transcript_chunks": [],
                "start_time": datetime.utcnow(),
                "status": "active"
            }
            
            # Start background transcription
            asyncio.create_task(self.transcribe_call(call_id))
    
    async def stop_transcription(self, event: Event):
        """Stop transcription for a call"""
        call_id = event.data.get("call_id")
        
        if call_id in self.active_transcriptions:
            logger.info(f"Stopping transcription for call {call_id}")
            
            transcription_data = self.active_transcriptions[call_id]
            transcription_data["status"] = "completed"
            transcription_data["end_time"] = datetime.utcnow()
            
            # Compile full transcript
            full_transcript = self.compile_transcript(transcription_data["transcript_chunks"])
            
            # Update call record with transcript
            call = self.db.query(Call).filter(Call.id == call_id).first()
            if call:
                call.transcript = full_transcript
                self.db.commit()
            
            # Publish transcript completion event
            await event_bus.publish(Event(
                type="transcript_completed",
                data={
                    "call_id": call_id,
                    "transcript": full_transcript,
                    "duration": len(transcription_data["transcript_chunks"]),
                    "caller_phone": transcription_data["caller_phone"]
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"transcript_{call_id}"
            ))
            
            # Clean up
            del self.active_transcriptions[call_id]
    
    async def transcribe_call(self, call_id: int):
        """Continuous transcription for a call"""
        try:
            while call_id in self.active_transcriptions and \
                  self.active_transcriptions[call_id]["status"] == "active":
                
                # Simulate audio capture and transcription
                # In a real implementation, this would connect to telephony system
                transcript_chunk = await self.capture_and_transcribe()
                
                if transcript_chunk:
                    # Add timestamp to chunk
                    timestamped_chunk = {
                        "timestamp": datetime.utcnow(),
                        "text": transcript_chunk,
                        "confidence": 0.85  # Mock confidence score
                    }
                    
                    self.active_transcriptions[call_id]["transcript_chunks"].append(timestamped_chunk)
                    
                    # Publish real-time transcript event
                    await event_bus.publish(Event(
                        type="transcript_chunk",
                        data={
                            "call_id": call_id,
                            "chunk": timestamped_chunk,
                            "caller_phone": self.active_transcriptions[call_id]["caller_phone"]
                        },
                        timestamp=datetime.utcnow(),
                        correlation_id=f"chunk_{call_id}"
                    ))
                    
                    # Check if this chunk contains a question
                    if self.is_question(transcript_chunk):
                        await self.handle_question_detected(call_id, transcript_chunk)
                
                # Wait before next capture
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Error in transcription for call {call_id}: {e}")
    
    async def capture_and_transcribe(self) -> Optional[str]:
        """Capture audio and convert to text"""
        try:
            # In a real implementation, this would capture from telephony system
            # For now, we'll simulate with microphone input
            with self.microphone as source:
                # Listen for audio with timeout
                audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
            
            # Recognize speech
            text = self.recognizer.recognize_google(audio)
            return text
            
        except sr.WaitTimeoutError:
            # No audio detected
            return None
        except sr.UnknownValueError:
            # Audio not clear enough
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in speech recognition: {e}")
            return None
    
    def compile_transcript(self, chunks: list) -> str:
        """Compile transcript chunks into full transcript"""
        if not chunks:
            return ""
        
        # Sort by timestamp
        sorted_chunks = sorted(chunks, key=lambda x: x["timestamp"])
        
        # Combine text with timestamps
        transcript_lines = []
        for chunk in sorted_chunks:
            timestamp_str = chunk["timestamp"].strftime("%H:%M:%S")
            transcript_lines.append(f"[{timestamp_str}] {chunk['text']}")
        
        return "\n".join(transcript_lines)
    
    def is_question(self, text: str) -> bool:
        """Detect if text contains a question"""
        question_indicators = [
            "?", "what", "how", "when", "where", "why", "who", "which",
            "can you", "could you", "do you", "are you", "is it", "will you"
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in question_indicators)
    
    async def handle_question_detected(self, call_id: int, question_text: str):
        """Handle when a question is detected in speech"""
        transcription_data = self.active_transcriptions.get(call_id)
        if not transcription_data:
            return
        
        # Publish question event for FAQ bot
        await event_bus.publish(Event(
            type="question_asked",
            data={
                "call_id": call_id,
                "question": question_text,
                "caller_phone": transcription_data["caller_phone"],
                "source": "speech"
            },
            timestamp=datetime.utcnow(),
            correlation_id=f"speech_question_{call_id}"
        ))
    
    async def process_audio_chunk(self, event: Event):
        """Process audio chunk from external source"""
        call_id = event.data.get("call_id")
        audio_data = event.data.get("audio_data")
        
        if call_id in self.active_transcriptions:
            # Process the audio chunk
            transcript = await self.transcribe_audio_data(audio_data)
            if transcript:
                timestamped_chunk = {
                    "timestamp": datetime.utcnow(),
                    "text": transcript,
                    "confidence": 0.80
                }
                
                self.active_transcriptions[call_id]["transcript_chunks"].append(timestamped_chunk)
    
    async def transcribe_audio_data(self, audio_data: bytes) -> Optional[str]:
        """Transcribe raw audio data"""
        try:
            # Convert audio data to AudioData object
            # This is a simplified implementation
            # In practice, you'd need proper audio format handling
            
            # Mock transcription for now
            return "Transcribed text from audio data"
            
        except Exception as e:
            logger.error(f"Error transcribing audio data: {e}")
            return None
    
    def get_active_transcriptions(self) -> Dict[int, Dict[str, Any]]:
        """Get currently active transcriptions"""
        return {
            call_id: {
                "caller_phone": data["caller_phone"],
                "start_time": data["start_time"],
                "chunk_count": len(data["transcript_chunks"]),
                "status": data["status"]
            }
            for call_id, data in self.active_transcriptions.items()
        }
    
    def get_call_transcript(self, call_id: int) -> Optional[str]:
        """Get current transcript for a call"""
        if call_id in self.active_transcriptions:
            chunks = self.active_transcriptions[call_id]["transcript_chunks"]
            return self.compile_transcript(chunks)
        
        # Check database for completed transcript
        call = self.db.query(Call).filter(Call.id == call_id).first()
        return call.transcript if call else None