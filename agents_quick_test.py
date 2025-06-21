
import asyncio
import sys
import os
sys.path.append('src')

from src.database import get_db
from src.models import FAQ, Agent, Call
from src.agents.faq_bot import FAQBot
from src.agents.data_entry import DataEntryAutomator
from src.agents.call_routing import CallRouter
from src.orchestration.event_bus import event_bus, Event
from datetime import datetime, timezone
import json

class QuickTester:
    def __init__(self):
        self.db = next(get_db())
        self.setup_test_data()
    
    def setup_test_data(self):
        """Setup minimal test data"""
        # Add test FAQ if not exists
        existing_faq = self.db.query(FAQ).first()
        if not existing_faq:
            test_faq = FAQ(
                question="Comment débloquer ma carte?",
                answer="Pour débloquer votre carte, composez le 3033 ou connectez-vous à votre espace client en ligne.",
                category="carte"
            )
            self.db.add(test_faq)
        
        # Add test agent if not exists
        existing_agent = self.db.query(Agent).filter_by(email="agent.test@satim.dz").first()

        if not existing_agent:
            test_agent = Agent(
                name="Agent Test",
                email="agent.test@satim.dz",
                phone="+213555000000",
                status="available"
            )
            self.db.add(test_agent)
        
        self.db.commit()
        print("✅ Test data setup complete")

    async def test_faq_bot(self):
        """Test FAQ Bot"""
        print("\n🤖 Testing FAQ Bot...")
        
        faq_bot = FAQBot(self.db)
        
        # Test question
        test_event = Event(
            type="question_asked",
            data={
                "question": "Ma carte est bloquée, que faire?",
                "caller_phone": "+213555123456",
                "call_id": 1
            },
            timestamp=datetime.now(timezone.utc)

        )
        
        await faq_bot.handle_question(test_event)
        print("✅ FAQ Bot test completed")

    async def test_data_entry(self):
        """Test Data Entry Automator"""
        print("\n📝 Testing Data Entry...")
        
        data_entry = DataEntryAutomator(self.db)
        
        # Test transcript with extractable data
        test_transcript = """
        Bonjour, mon nom est Ahmed Bennaceur. 
        Mon numéro de carte est 1234 5678 9012 3456.
        J'ai un problème avec une transaction de 150.50 DA.
        Mon email est ahmed@email.com
        """
        
        test_event = Event(
            type="call_transcript_ready",
            data={
                "call_id": 1,
                "transcript": test_transcript
            },
            timestamp=datetime.utcnow()
        )
        
        await data_entry.handle_transcript(test_event)
        print("✅ Data Entry test completed")

    async def test_call_router(self):
        """Test Call Router"""
        print("\n📞 Testing Call Router...")
        
        router = CallRouter(self.db)
        
        # Test incoming call
        test_event = Event(
            type="call_incoming",
            data={
                "caller_phone": "+213555987654",
                "priority": 1
            },
            timestamp=datetime.utcnow()
        )
        
        await router.handle_incoming_call(test_event)
        print("✅ Call Router test completed")

    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Quick Agent Tests...")
        
        try:
            await self.test_faq_bot()
            await self.test_data_entry()
            await self.test_call_router()
            
            print("\n✅ All tests completed successfully!")
            
            # Show some results
            self.show_results()
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

    def show_results(self):
        """Show test results"""
        print("\n📊 Test Results:")
        
        # Check FAQs
        faq_count = self.db.query(FAQ).count()
        print(f"   FAQs in database: {faq_count}")
        
        # Check Agents
        agent_count = self.db.query(Agent).count()
        print(f"   Agents in database: {agent_count}")
        
        # Check Calls
        call_count = self.db.query(Call).count()
        print(f"   Calls in database: {call_count}")
        
        # Show latest call data
        latest_call = self.db.query(Call).order_by(Call.id.desc()).first()
        if latest_call and latest_call.summary:
            try:
                extracted_data = json.loads(latest_call.summary)
                print(f"   Latest call extracted data: {len(extracted_data)} fields")
            except:
                pass

if __name__ == "__main__":
    from src.models import Base
    from src.database import engine

    # 💥 Drop old tables (including agents without 'phone')
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


    tester = QuickTester()
    asyncio.run(tester.run_all_tests())
