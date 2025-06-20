import wave
import numpy as np
import librosa
import soundfile as sf
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Utility class for audio processing operations"""
    
    @staticmethod
    def load_audio(file_path: str, sr: int = 16000) -> Tuple[np.ndarray, int]:
        """Load audio file and return audio data and sample rate"""
        try:
            audio, sample_rate = librosa.load(file_path, sr=sr)
            return audio, sample_rate
        except Exception as e:
            logger.error(f"Error loading audio file {file_path}: {e}")
            raise
    
    @staticmethod
    def save_audio(audio_data: np.ndarray, file_path: str, sr: int = 16000):
        """Save audio data to file"""
        try:
            sf.write(file_path, audio_data, sr)
            logger.info(f"Audio saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving audio to {file_path}: {e}")
            raise
    
    @staticmethod
    def normalize_audio(audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1] range"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            return audio / max_val
        return audio
    
    @staticmethod
    def remove_silence(audio: np.ndarray, sr: int = 16000, 
                      top_db: int = 20) -> np.ndarray:
        """Remove silence from audio"""
        try:
            # Use librosa to trim silence
            trimmed_audio, _ = librosa.effects.trim(audio, top_db=top_db)
            return trimmed_audio
        except Exception as e:
            logger.error(f"Error removing silence: {e}")
            return audio
    
    @staticmethod
    def enhance_audio_quality(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        """Enhance audio quality for better speech recognition"""
        try:
            # Normalize
            audio = AudioProcessor.normalize_audio(audio)
            
            # Remove silence
            audio = AudioProcessor.remove_silence(audio, sr)
            
            # Apply high-pass filter to remove low-frequency noise
            audio = librosa.effects.preemphasis(audio)
            
            return audio
        except Exception as e:
            logger.error(f"Error enhancing audio quality: {e}")
            return audio