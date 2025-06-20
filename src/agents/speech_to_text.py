import asyncio
import speech_recognition as sr
import io
import wave
import logging
from typing import Optional, Callable
from datetime import datetime

from ..orchestration.event_bus import event_bus, Event

logger = logging.getLogger(__name__)

class SpeechToTextProcessor:
    """Handles speech-to-text conversion for call recordings"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.setup_event_handlers()
        
        # Adjust for ambient noise
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
    
    def setup_event_handlers(self):
        """Setup event handlers for speech processing"""
        event_bus.subscribe("audio_recorded", self.handle_audio_recording)
        event_bus.subscribe("real_time_audio", self.handle_real_time_audio)
    
    async def handle_audio_recording(self, event: Event):
        """Handle recorded audio file for transcription"""
        call_id = event.data.get("call_id")
        audio_file_path = event.data.get("audio_file_path")
        
        logger.info(f"Processing audio file for call {call_id}")
        
        try:
            # Process audio file
            transcript = await self.transcribe_audio_file(audio_file_path)
            
            if transcript:
                # Publish transcript ready event
                await event_bus.publish(Event(
                    type="call_transcript_ready",
                    data={
                        "call_id": call_id,
                        "transcript": transcript,
                        "source": "file"
                    },
                    timestamp=datetime.utcnow(),
                    correlation_id=f"transcript_{call_id}"
                ))
                
                logger.info(f"Transcript generated for call {call_id}")
            else:
                logger.warning(f"No transcript generated for call {call_id}")
                
        except Exception as e:
            logger.error(f"Error processing audio for call {call_id}: {e}")
            
            # Publish error event
            await event_bus.publish(Event(
                type="speech_processing_error",
                data={
                    "call_id": call_id,
                    "error": str(e)
                },
                timestamp=datetime.utcnow(),
                correlation_id=f"error_{call_id}"
            ))
    
    async def handle_real_time_audio(self, event: Event):
        """Handle real-time audio stream for live transcription"""
        call_id = event.data.get("call_id")
        audio_chunk = event.data.get("audio_chunk")
        
        try:
            # Process audio chunk
            partial_transcript = await self.transcribe_audio_chunk(audio_chunk)
            
            if partial_transcript:
                # Publish partial transcript event
                await event_bus.publish(Event(
                    type="partial_transcript",
                    data={
                        "call_id": call_id,
                        "partial_transcript": partial_transcript,
                        "timestamp": datetime.utcnow()
                    },
                    timestamp=datetime.utcnow(),
                    correlation_id=f"partial_{call_id}"
                ))
                
        except Exception as e:
            logger.error(f"Error processing real-time audio for call {call_id}: {e}")
    
    async def transcribe_audio_file(self, audio_file_path: str) -> Optional[str]:
        """Transcribe complete audio file"""
        try:
            with sr.AudioFile(audio_file_path) as source:
                # Record the audio file
                audio_data = self.recognizer.record(source)
                
                # Use Google Speech Recognition (can be replaced with other services)
                transcript = self.recognizer.recognize_google(
                    audio_data, 
                    language="fr-FR"  # French for Algeria, can be configured
                )
                
                return transcript
                
        except sr.UnknownValueError:
            logger.warning("Speech recognition could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in transcription: {e}")
            return None
    
    async def transcribe_audio_chunk(self, audio_chunk: bytes) -> Optional[str]:
        """Transcribe audio chunk for real-time processing"""
        try:
            # Convert bytes to AudioData
            audio_data = sr.AudioData(audio_chunk, 16000, 2)  # 16kHz, 16-bit
            
            # Use Google Speech Recognition
            transcript = self.recognizer.recognize_google(
                audio_data,
                language="fr-FR"
            )
            
            return transcript
            
        except sr.UnknownValueError:
            # Normal - not all chunks contain speech
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in chunk transcription: {e}")
            return None
    
    def start_real_time_listening(self, call_id: int, callback: Optional[Callable] = None):
        """Start real-time audio listening for a call"""
        logger.info(f"Starting real-time listening for call {call_id}")
        
        def audio_callback(recognizer, audio):
            """Callback for real-time audio processing"""
            asyncio.create_task(
                event_bus.publish(Event(
                    type="real_time_audio",
                    data={
                        "call_id": call_id,
                        "audio_chunk": audio.get_raw_data()
                    },
                    timestamp=datetime.utcnow(),
                    correlation_id=f"realtime_{call_id}"
                ))
            )
            
            if callback:
                callback(audio)
        
        # Start background listening
        stop_listening = self.recognizer.listen_in_background(
            self.microphone, 
            audio_callback,
            phrase_time_limit=5  # Process every 5 seconds
        )
        
        return stop_listening
