import re
import string
from typing import List, Dict, Any
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import SnowballStemmer
import logging

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except:
    logger.warning("Could not download NLTK data")

class NLPProcessor:
    """Utility class for NLP operations"""
    
    def __init__(self, language: str = 'french'):
        self.language = language
        try:
            self.stop_words = set(stopwords.words(language))
        except:
            self.stop_words = set()
            logger.warning(f"Could not load stopwords for {language}")
        
        try:
            self.stemmer = SnowballStemmer(language)
        except:
            self.stemmer = None
            logger.warning(f"Could not load stemmer for {language}")
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove phone numbers (keep for data extraction elsewhere)
        # text = re.sub(r'\b\d{10}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into words"""
        try:
            tokens = word_tokenize(text, language=self.language)
            return tokens
        except:
            # Fallback to simple split
            return text.split()
    
    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        """Remove stopwords from token list"""
        return [token for token in tokens if token.lower() not in self.stop_words]
    
    def remove_punctuation(self, tokens: List[str]) -> List[str]:
        """Remove punctuation from tokens"""
        return [token for token in tokens if token not in string.punctuation]
    
    def stem_tokens(self, tokens: List[str]) -> List[str]:
        """Apply stemming to tokens"""
        if self.stemmer:
            return [self.stemmer.stem(token) for token in tokens]
        return tokens
    
    def preprocess_text(self, text: str, remove_stopwords: bool = True,
                       remove_punct: bool = True, apply_stemming: bool = False) -> List[str]:
        """Complete text preprocessing pipeline"""
        # Clean text
        text = self.clean_text(text)
        
        # Tokenize
        tokens = self.tokenize(text)
        
        # Remove punctuation
        if remove_punct:
            tokens = self.remove_punctuation(tokens)
        
        # Remove stopwords
        if remove_stopwords:
            tokens = self.remove_stopwords(tokens)
        
        # Apply stemming
        if apply_stemming:
            tokens = self.stem_tokens(tokens)
        
        return tokens
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """Extract keywords from text"""
        # Preprocess text
        tokens = self.preprocess_text(text, remove_stopwords=True, 
                                    remove_punct=True, apply_stemming=True)
        
        # Count token frequency
        token_freq = {}
        for token in tokens:
            if len(token) > 2:  # Ignore very short tokens
                token_freq[token] = token_freq.get(token, 0) + 1
        
        # Sort by frequency and return top k
        sorted_tokens = sorted(token_freq.items(), key=lambda x: x[1], reverse=True)
        return [token for token, freq in sorted_tokens[:top_k]]
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using Jaccard similarity"""
        tokens1 = set(self.preprocess_text(text1))
        tokens2 = set(self.preprocess_text(text2))
        
        if not tokens1 and not tokens2:
            return 1.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0
