#!/usr/bin/env python3
"""
INSTANT TEST SCRIPT - Run this to test everything quickly!
"""

import requests
import time
import subprocess
import sys
import os
from threading import Thread
import json

def start_api_server():
    """Start the API server in background"""
    try:
        print("🚀 Starting API server...")
        # Change to the correct directory
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Start the server
        subprocess.run([
            sys.executable, "src/api/main.py"
        ], check=True)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

def wait_for_server(url="http://localhost:8000", timeout=30):
    """Wait for server to be ready"""
    print("⏳ Waiting for server to start...")
    
    for i in range(timeout):
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except:
            pass
        time.sleep(1)
        print(f"   Waiting... ({i+1}/{timeout})")
    
    print("❌ Server failed to start in time")
    return False

def test_api_endpoints():
    """Test all API endpoints"""
    base_url = "http://localhost:8000"
    
    tests = [
        {
            "name": "Root Endpoint",
            "method": "GET",
            "url": f"{base_url}/",
            "expected_status": 200
        },
        {
            "name": "Health Check",
            "method": "GET", 
            "url": f"{base_url}/health",
            "expected_status": 200
        },
        {
            "name": "Incoming Call",
            "method": "POST",
            "url": f"{base_url}/call/incoming",
            "params": {"caller_phone": "+213555123456", "priority": 1},
            "expected_status": 200
        },
        {
            "name": "FAQ Question",
            "method": "POST",
            "url": f"{base_url}/faq/ask",
            "params": {"question": "Ma carte est bloquée", "caller_phone": "+213555123456"},
            "expected_status": 200
        }
    ]
    
    results = []
    
    for test in tests:
        try:
            print(f"\n🧪 Testing: {test['name']}")
            
            if test['method'] == 'GET':
                response = requests.get(test['url'], timeout=5)
            else:
                response = requests.post(test['url'], params=test.get('params', {}), timeout=5)
            
            success = response.status_code == test['expected_status']
            
            if success:
                print(f"✅ {test['name']}: PASSED")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.json()}")
            else:
                print(f"❌ {test['name']}: FAILED")
                print(f"   Expected: {test['expected_status']}, Got: {response.status_code}")
                print(f"   Response: {response.text}")
            
            results.append({
                "test": test['name'],
                "success": success,
                "status_code": response.status_code,
                "response": response.json() if success else response.text
            })
            
        except Exception as e:
            print(f"❌ {test['name']}: ERROR - {e}")
            results.append({
                "test": test['name'],
                "success": False,
                "error": str(e)
            })
    
    return results

def test_database():
    """Test database creation"""
    print("\n🗄️ Testing Database...")
    
    try:
        # Check if database file exists
        db_file = "satim_callcenter.db"
        if os.path.exists(db_file):
            print(f"✅ Database file exists: {db_file}")
            file_size = os.path.getsize(db_file)
            print(f"   Size: {file_size} bytes")
            return True
        else:
            print(f"❌ Database file not found: {db_file}")
            return False
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_imports():
    """Test if all imports work"""
    print("\n📦 Testing Imports...")
    
    import_tests = [
        ("Event Bus", "from src.orchestration.event_bus import event_bus, Event"),
        ("Database", "from src.database import get_db, create_tables"),
        ("Models", "from src.models import Agent, Call, CallQueue, FAQ"),
        ("Call Router", "from src.agents.call_routing import CallRouter"),
    ]
    
    results = []
    
    for name, import_stmt in import_tests:
        try:
            exec(import_stmt)
            print(f"✅ {name}: Import successful")
            results.append({"test": name, "success": True})
        except Exception as e:
            print(f"❌ {name}: Import failed - {e}")
            results.append({"test": name, "success": False, "error": str(e)})
    
    return results

def run_quick_test():
    """Run the complete quick test"""
    print("🚀 SATIM Call Center - INSTANT TEST")
    print("=" * 50)
    
    # Test 1: Imports
    import_results = test_imports()
    
    # Test 2: Database
    db_result = test_database()
    
    # Test 3: Start server and test API
    print("\n🌐 Starting API Server Test...")
    
    # Start server in background thread
    server_thread = Thread(target=start_api_server, daemon=True)
    server_thread.start()
    
    # Wait for server to be ready
    if wait_for_server():
        # Test API endpoints
        api_results = test_api_endpoints()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)
        
        print("\n📦 Import Tests:")
        for result in import_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"   {result['test']}: {status}")
        
        print(f"\n🗄️ Database Test: {'✅ PASS' if db_result else '❌ FAIL'}")
        
        print("\n🌐 API Tests:")
        for result in api_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"   {result['test']}: {status}")
        
        # Calculate success rate
        total_tests = len(import_results) + 1 + len(api_results)
        passed_tests = sum(1 for r in import_results if r['success']) + (1 if db_result else 0) + sum(1 for r in api_results if r['success'])
        
        print(f"\n🎯 Overall Success Rate: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("\n🎉 ALL TESTS PASSED! Your system is working! 🎉")
        else:
            print(f"\n⚠️ {total_tests - passed_tests} tests failed. Check the details above.")
    
    else:
        print("\n❌ Server failed to start. Check for errors above.")
    
    print(f"\n⏰ Test completed at {time.strftime('%H:%M:%S')}")

if __name__ == "__main__":
    run_quick_test()