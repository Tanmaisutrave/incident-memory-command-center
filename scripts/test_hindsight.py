"""
Test script to verify Hindsight integration.

This script tests the complete memory cycle:
1. RETAIN - Store a test incident memory
2. RECALL - Retrieve the stored memory
3. REFLECT - Analyze patterns across memories
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from app.hindsight_client import hindsight_client


def test_retain():
    """Test storing a memory in Hindsight."""
    print("\n" + "="*60)
    print("TEST 1: RETAIN - Store incident memory")
    print("="*60)
    
    test_incident = {
        "incident_id": "TEST-001",
        "title": "Redis Connection Pool Exhaustion",
        "service": "payment-api",
        "environment": "production",
        "severity": "P1",
        "symptoms": "8.2 second API latency, Redis timeout errors, 502 responses",
        "root_cause": "Redis connection pool exhausted (100 max connections)",
        "resolution": "Increased Redis connection pool from 100 to 250",
        "outcome": "Latency reduced to 1.1s, error rate dropped to 0%",
        "lessons_learned": "Monitor connection pool utilization proactively"
    }
    
    content = f"""
Incident: {test_incident['incident_id']} - {test_incident['title']}

Service: {test_incident['service']}
Environment: {test_incident['environment']}
Severity: {test_incident['severity']}

Symptoms:
{test_incident['symptoms']}

Root Cause:
{test_incident['root_cause']}

Resolution:
{test_incident['resolution']}

Outcome:
{test_incident['outcome']}

Lessons Learned:
{test_incident['lessons_learned']}
"""
    
    metadata = {
        "incident_id": test_incident["incident_id"],
        "service": test_incident["service"],
        "environment": test_incident["environment"],
        "severity": test_incident["severity"],
        "category": "redis",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        result = hindsight_client.retain(
            content=content.strip(),
            metadata=metadata,
            context=f"Incident {test_incident['incident_id']}"
        )
        print(f"✓ Successfully retained memory")
        print(f"  Content preview: {content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Failed to retain memory: {e}")
        return False


def test_recall():
    """Test retrieving memories from Hindsight."""
    print("\n" + "="*60)
    print("TEST 2: RECALL - Retrieve similar incidents")
    print("="*60)
    
    query = "Redis timeout and high latency in payment API"
    
    try:
        memories = hindsight_client.recall(
            query=query,
            max_tokens=2048,
            budget="mid"
        )
        print(f"✓ Successfully recalled {len(memories)} memories")
        print(f"  Query: {query}")
        
        if memories:
            print("\n  Retrieved memories:")
            for i, memory in enumerate(memories, 1):
                memory_text = memory.get('text', '')
                content_preview = memory_text[:80].replace('\n', ' ') if memory_text else ''
                print(f"    {i}. {content_preview}...")
                memory_type = memory.get('type', 'unknown')
                print(f"       Type: {memory_type}")
        else:
            print("  Note: No memories found (bank may be empty)")
        
        return True
    except Exception as e:
        print(f"✗ Failed to recall memories: {e}")
        return False


def test_reflect():
    """Test reflection across incident memories."""
    print("\n" + "="*60)
    print("TEST 3: REFLECT - Discover patterns")
    print("="*60)
    
    query = """
    Analyze all Redis-related incidents and identify:
    1. Common symptoms
    2. Most frequent root causes
    3. Successful resolution patterns
    4. Preventive recommendations
    """
    
    try:
        reflection = hindsight_client.reflect(
            query=query.strip(),
            budget="mid",
            context="pattern analysis"
        )
        print(f"✓ Successfully completed reflection")
        print(f"\n  Reflection insights:")
        print(f"  {reflection[:500]}...")
        return True
    except Exception as e:
        print(f"✗ Failed to reflect: {e}")
        return False


def test_health():
    """Test Hindsight connectivity."""
    print("\n" + "="*60)
    print("TEST 0: HEALTH CHECK")
    print("="*60)
    
    try:
        healthy = hindsight_client.health_check()
        if healthy:
            print("✓ Hindsight connection is healthy")
            return True
        else:
            print("✗ Hindsight connection failed")
            return False
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def main():
    """Run all Hindsight tests."""
    print("\n" + "="*60)
    print("HINDSIGHT INTEGRATION TEST")
    print("="*60)
    print(f"Bank ID: {hindsight_client.bank_id}")
    print(f"Base URL: {os.getenv('HINDSIGHT_BASE_URL', 'not set')}")
    
    results = {
        "Health Check": test_health(),
        "RETAIN": test_retain(),
        "RECALL": test_recall(),
        "REFLECT": test_reflect()
    }
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
        print("Hindsight integration is working correctly!")
    else:
        print("SOME TESTS FAILED ✗")
        print("Please check your configuration and try again.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
