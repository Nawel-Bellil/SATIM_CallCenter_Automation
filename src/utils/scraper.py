import requests
from bs4 import BeautifulSoup
import json
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import re
from dataclasses import dataclass
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

@dataclass
class FAQItem:
    question: str
    answer: str
    category: str
    source_url: str

class SATIMScraper:
    """Scraper for SATIM website FAQ and help content"""
    
    def __init__(self, base_url: str = "https://www.satim.dz", delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.scraped_faqs = []
        
    def scrape_page(self, url: str) -> Optional[BeautifulSoup]:
        """Scrape a single page and return BeautifulSoup object"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def extract_faq_from_page(self, soup: BeautifulSoup, url: str, category: str = "General") -> List[FAQItem]:
        """Extract FAQ items from a page"""
        faqs = []
        
        # Method 1: Look for FAQ sections with common patterns
        faq_sections = soup.find_all(['div', 'section'], class_=re.compile(r'faq|question|help', re.I))
        
        for section in faq_sections:
            # Look for question-answer pairs
            questions = section.find_all(['h3', 'h4', 'h5', 'dt'], text=re.compile(r'\?|Comment|Que|Quoi|Pourquoi', re.I))
            
            for question_elem in questions:
                question_text = self.clean_text(question_elem.get_text())
                
                # Find corresponding answer
                answer_elem = question_elem.find_next_sibling(['p', 'div', 'dd'])
                if answer_elem:
                    answer_text = self.clean_text(answer_elem.get_text())
                    
                    if len(question_text) > 10 and len(answer_text) > 20:
                        faqs.append(FAQItem(
                            question=question_text,
                            answer=answer_text,
                            category=category,
                            source_url=url
                        ))
        
        # Method 2: Look for accordion-style FAQs
        accordions = soup.find_all(['div', 'section'], class_=re.compile(r'accordion|collapse|expand', re.I))
        
        for accordion in accordions:
            headers = accordion.find_all(['button', 'a', 'h3', 'h4'], attrs={'data-toggle': True})
            
            for header in headers:
                question_text = self.clean_text(header.get_text())
                
                # Find associated content
                target_id = header.get('data-target', '').replace('#', '')
                if target_id:
                    content = accordion.find(id=target_id)
                    if content:
                        answer_text = self.clean_text(content.get_text())
                        
                        if len(question_text) > 10 and len(answer_text) > 20:
                            faqs.append(FAQItem(
                                question=question_text,
                                answer=answer_text,
                                category=category,
                                source_url=url
                            ))
        
        return faqs
    
    def extract_service_info(self, soup: BeautifulSoup, url: str) -> List[FAQItem]:
        """Extract service information that can be converted to FAQs"""
        faqs = []
        
        # Look for service descriptions
        service_sections = soup.find_all(['div', 'section'], class_=re.compile(r'service|product|offer', re.I))
        
        for section in service_sections:
            title_elem = section.find(['h1', 'h2', 'h3'])
            if title_elem:
                title = self.clean_text(title_elem.get_text())
                
                # Get description
                description_elem = section.find(['p', 'div'], class_=re.compile(r'description|content|text', re.I))
                if description_elem:
                    description = self.clean_text(description_elem.get_text())
                    
                    if len(title) > 5 and len(description) > 30:
                        # Convert to FAQ format
                        question = f"Qu'est-ce que {title}?"
                        faqs.append(FAQItem(
                            question=question,
                            answer=description,
                            category="Services",
                            source_url=url
                        ))
        
        return faqs
    
    def scrape_contact_info(self, soup: BeautifulSoup, url: str) -> List[FAQItem]:
        """Extract contact information as FAQs"""
        faqs = []
        
        # Look for contact information
        contact_sections = soup.find_all(['div', 'section'], class_=re.compile(r'contact|address|phone', re.I))
        
        for section in contact_sections:
            # Extract phone numbers
            phones = re.findall(r'(\+?213[.\s\-]?(?:\d{2}[.\s\-]?){4}\d{2})', section.get_text())
            if phones:
                faqs.append(FAQItem(
                    question="Quels sont les numéros de téléphone de SATIM?",
                    answer=f"Vous pouvez contacter SATIM aux numéros suivants: {', '.join(phones)}",
                    category="Contact",
                    source_url=url
                ))
            
            # Extract email addresses
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', section.get_text())
            if emails:
                faqs.append(FAQItem(
                    question="Quelle est l'adresse email de SATIM?",
                    answer=f"Vous pouvez contacter SATIM par email: {', '.join(emails)}",
                    category="Contact",
                    source_url=url
                ))
            
            # Extract addresses
            address_patterns = [
                r'\d+[,\s]+[A-Za-z\s]+[,\s]*Alger',
                r'[A-Za-z\s]+[,\s]*Algérie'
            ]
            
            for pattern in address_patterns:
                addresses = re.findall(pattern, section.get_text(), re.I)
                if addresses:
                    faqs.append(FAQItem(
                        question="Où se trouve SATIM?",
                        answer=f"SATIM est située à: {', '.join(addresses)}",
                        category="Contact",
                        source_url=url
                    ))
                    break
        
        return faqs
    
    def scrape_all(self) -> List[FAQItem]:
        """Scrape all relevant pages from SATIM website"""
        self.scraped_faqs = []
        
        # Main pages to scrape
        pages_to_scrape = [
            (f"{self.base_url}/index.php/fr/", "Accueil"),
            (f"{self.base_url}/index.php/fr/contact", "Contact"),
            (f"{self.base_url}/index.php/fr/services", "Services"),
            (f"{self.base_url}/index.php/fr/produits", "Produits"),
            (f"{self.base_url}/index.php/fr/aide", "Aide"),
            (f"{self.base_url}/index.php/fr/faq", "FAQ"),
            (f"{self.base_url}/index.php/fr/support", "Support"),
        ]
        
        for url, category in pages_to_scrape:
            logger.info(f"Scraping {url} ({category})")
            
            soup = self.scrape_page(url)
            if soup:
                # Extract FAQs using different methods
                faqs = self.extract_faq_from_page(soup, url, category)
                self.scraped_faqs.extend(faqs)
                
                # Extract service information
                service_faqs = self.extract_service_info(soup, url)
                self.scraped_faqs.extend(service_faqs)
                
                # Extract contact information
                if category == "Contact":
                    contact_faqs = self.scrape_contact_info(soup, url)
                    self.scraped_faqs.extend(contact_faqs)
                
                # Find and scrape linked pages
                self.scrape_linked_pages(soup, url, category)
            
            time.sleep(self.delay)
        
        # Add default FAQs for common banking/payment questions
        self.add_default_faqs()
        
        logger.info(f"Total FAQs scraped: {len(self.scraped_faqs)}")
        return self.scraped_faqs
    
    def scrape_linked_pages(self, soup: BeautifulSoup, base_url: str, category: str):
        """Scrape linked pages from the current page"""
        # Find relevant links
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href')
            if href and self.is_relevant_link(href, link.get_text()):
                full_url = urljoin(base_url, href)
                
                if self.is_same_domain(full_url) and full_url not in [item.source_url for item in self.scraped_faqs]:
                    logger.info(f"Scraping linked page: {full_url}")
                    
                    soup_linked = self.scrape_page(full_url)
                    if soup_linked:
                        faqs = self.extract_faq_from_page(soup_linked, full_url, category)
                        self.scraped_faqs.extend(faqs)
                    
                    time.sleep(self.delay)
    
    def is_relevant_link(self, href: str, link_text: str) -> bool:
        """Check if a link is relevant for FAQ scraping"""
        relevant_keywords = ['faq', 'aide', 'help', 'support', 'question', 'contact', 'service']
        
        href_lower = href.lower()
        text_lower = link_text.lower()
        
        return any(keyword in href_lower or keyword in text_lower for keyword in relevant_keywords)
    
    def is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to the same domain"""
        return urlparse(url).netloc == urlparse(self.base_url).netloc
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep French accents
        text = re.sub(r'[^\w\s\-\.\,\?\!\àâäçéèêëïîôöùûüÿ]', '', text)
        
        return text.strip()
    
    def add_default_faqs(self):
        """Add default FAQs for common banking/payment questions"""
        default_faqs = [
            FAQItem(
                question="Comment puis-je contacter le service client SATIM?",
                answer="Vous pouvez contacter le service client SATIM par téléphone, email ou en visitant nos bureaux. Consultez notre page contact pour plus d'informations.",
                category="Contact",
                source_url=f"{self.base_url}/default"
            ),
            FAQItem(
                question="Quels sont les horaires d'ouverture de SATIM?",
                answer="SATIM est généralement ouvert du dimanche au jeudi de 8h00 à 17h00. Les horaires peuvent varier selon les services.",
                category="Informations",
                source_url=f"{self.base_url}/default"
            ),
            FAQItem(
                question="Comment puis-je effectuer un paiement via SATIM?",
                answer="SATIM propose plusieurs méthodes de paiement électronique. Contactez-nous pour connaître les options disponibles selon votre situation.",
                category="Paiements",
                source_url=f"{self.base_url}/default"
            ),
            FAQItem(
                question="Que faire en cas de problème technique?",
                answer="En cas de problème technique, contactez immédiatement notre support technique. Nous vous aiderons à résoudre le problème rapidement.",
                category="Support",
                source_url=f"{self.base_url}/default"
            )
        ]
        
        self.scraped_faqs.extend(default_faqs)
    
    def save_to_json(self, filename: str):
        """Save scraped FAQs to JSON file"""
        data = [
            {
                "question": faq.question,
                "answer": faq.answer,
                "category": faq.category,
                "source_url": faq.source_url
            }
            for faq in self.scraped_faqs
        ]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"FAQs saved to {filename}")
    
    def save_to_database(self, db: Session):
        """Save scraped FAQs to database"""
        from models import FAQ

        
        saved_count = 0
        
        for faq_item in self.scraped_faqs:
            # Check if FAQ already exists
            existing_faq = db.query(FAQ).filter(
                FAQ.question == faq_item.question
            ).first()
            
            if not existing_faq:
                db_faq = FAQ(
                    question=faq_item.question,
                    answer=faq_item.answer,
                    category=faq_item.category
                )
                db.add(db_faq)
                saved_count += 1
        
        db.commit()
        logger.info(f"Saved {saved_count} new FAQs to database")
        return saved_count

def main():
    """Main function for testing the scraper"""
    logging.basicConfig(level=logging.INFO)
    
    scraper = SATIMScraper()
    faqs = scraper.scrape_all()
    
    print(f"Scraped {len(faqs)} FAQs")
    
    # Save to JSON file
    scraper.save_to_json("data/raw/satim_faqs.json")
    
    # Print first few FAQs
    for i, faq in enumerate(faqs[:5]):
        print(f"\n--- FAQ {i+1} ---")
        print(f"Question: {faq.question}")
        print(f"Answer: {faq.answer[:100]}...")
        print(f"Category: {faq.category}")

if __name__ == "__main__":
    main()