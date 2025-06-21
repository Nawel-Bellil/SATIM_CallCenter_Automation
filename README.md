# SATIM Call Center Automation

**SATIM Call Center Automation** is a backend system designed to streamline call center operations by automating call routing, FAQ handling, data entry, and speech-to-text processing. Built with Python and FastAPI, it uses an event-driven architecture to ensure scalability, modularity, and efficiency. The system addresses key challenges in call centers, such as long wait times, manual processes, and inconsistent responses, without requiring a frontend interface.

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Technologies](#technologies)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [Future Enhancements](#future-enhancements)
- [License](#license)

## Features
- **Smart Call Routing**: Assigns calls to available agents using load balancing or queues them based on priority.
- **AI-Powered FAQ Bot**: Matches customer questions to FAQs using NLP (TF-IDF and cosine similarity).
- **Automated Data Entry**: Extracts structured data (e.g., phone numbers, account IDs) from call transcripts using regex and NLP.
- **Real-Time Speech-to-Text**: Transcribes audio recordings and live streams using Google Speech Recognition.
- **System Monitoring**: Tracks metrics (queue length, active calls, agent status) and alerts for anomalies.
- **Event-Driven Architecture**: Uses an event bus for asynchronous communication between components.
- **API-Driven**: Provides FastAPI endpoints for health checks, call handling, and FAQ queries.

## Architecture
The system follows a modular, event-driven design:
- **Components**:
  - `CallRouter`: Manages call assignment and queuing.
  - `FAQBot`: Handles customer queries with NLP-based matching.
  - `DataEntryAutomator`: Extracts and validates data from transcripts.
  - `SpeechToTextProcessor`: Converts audio to text in real-time or batch.
  - `SystemCoordinator`: Initializes components, monitors health, and collects metrics.
- **EventBus**: Facilitates communication via publish-subscribe events (e.g., `call_incoming`, `question_asked`).
- **Database**: SQLite (development) stores agents, calls, queues, and FAQs.
- **API**: FastAPI provides endpoints like `/health`, `/call/incoming`, and `/faq/ask`.
![image](https://github.com/user-attachments/assets/91488757-ace8-49f1-bfd3-287446c8ed90)

## Technologies
- **Python 3.x**: Core programming language.
- **FastAPI**: High-performance API framework with async support.
- **SQLAlchemy**: ORM for SQLite database interactions.
- **SpeechRecognition**: For audio-to-text conversion (Google Speech API).
- **Scikit-learn & Transformers**: NLP for FAQ matching.
- **Asyncio**: Asynchronous event handling.
- **Logging**: Built-in Python logging for monitoring.

## Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-org/satim-callcenter-automation.git
   cd satim-callcenter-automation
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   Expected dependencies include:
   - `fastapi`
   - `uvicorn`
   - `sqlalchemy`
   - `speechrecognition`
   - `scikit-learn`
   - `transformers`
   - `numpy`

4. **Initialize the Database**:
   ```bash
   python -m src.database
   ```
   This creates the SQLite database (`satim_callcenter.db`) and tables.

5. **Run the API Server**:
   ```bash
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```

## Usage
1. **API Endpoints**:
   - **Health Check**: `GET /health`
     - Returns: `{"status": "healthy", "timestamp": "..."}`
   - **Root**: `GET /`
     - Returns: `{"message": "SATIM Call Center API", "status": "running"}`
   - **Incoming Call**: `POST /call/incoming?caller_phone=+213555123456&priority=1`
     - Returns: `{"status": "call_received", "caller_phone": "+213555123456"}`
   - **FAQ Question**: `POST /faq/ask?question=Ma+carte+est+bloquée&caller_phone=+213555123456`
     - Returns: `{"status": "question_received", "question": "Ma carte est bloquée"}`

2. **Run Tests**:
   ```bash
   python -m api_test
   ```
   This executes integration tests for imports, database, and API endpoints.

3. **Monitor Logs**:
   Check logs in the console or log files for system events, errors, and metrics.

## Project Structure
```
SATIM_CallCenter_Automation/
├── data/
│   ├── processed/
│   │   ├── satim_faqs_cleaned.csv
│   │   └── scraping_summary.json
│   └── raw/
│       └── satim_faqs_scraped.json
├── notebooks/
│   ├── 1_scrape_satim_faqs.ipynb
│   └── 2_train_nlp_model.ipynb
├── src/
│   ├── agents/
│   │   ├── call_routing.py
│   │   ├── data_entry.py
│   │   ├── faq_bot.py
│   │   └── speech_to_text.py
│   ├── api/
│   │   ├── main.py
│   ├── integration/
│   │   ├── crm_connector.py
│   │   └── telephony_api.py
│   ├── orchestration/
│   │   ├── coordinator.py
│   │   └── event_bus.py
│   ├── utils/
│   │   ├── audio_utils.py
│   │   ├── nlp_utils.py
│   │   └── scraper.py
│   ├── database.py
│   └── models.py
├── tests/
│   └── test_faq_bot.py
├── agents_quick_test.py
├── api_test.py
├── requirements.txt
├── satim_callcenter.db
├── README.md
├── LICENSE
├── CHANGELOG.md
├── setup.py
└── .gitignore
```

## Testing
- **Unit Tests**: Located in `tests/test_faq_bot.py` for FAQBot functionality.
- **Integration Tests**: Run `python -m api_test` to test imports, database, and API endpoints.
- **Test Results**: All tests passed (9/9, 100%) as per the provided output, covering imports, database, and API functionality.

## Contributing
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

Please follow the code style (PEP 8) and include tests for new features.

## Future Enhancements
- Develop a web dashboard (React/Flask) for real-time monitoring.
- Upgrade NLP with transformer models (e.g., BERT) for better FAQ matching.
- Migrate to PostgreSQL for production scalability.
- Implement full CRM and telephony integrations.
- Add multi-language support (e.g., Arabic).
- Introduce AI-driven analytics for customer sentiment and trends.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
