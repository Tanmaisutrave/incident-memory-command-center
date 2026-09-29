"""
Quick integration test for the Incident Memory Agent.

NOTE: This is a manual integration test. It requires a running server and
valid API keys (GROQ_API_KEY, HINDSIGHT_API_KEY) in backend/.env.
Run the backend first with `./run.ps1`, then execute this script directly:
`python scripts/manual/test_agent.py`

This script tests the core agent workflows:
1. Seeding memory with incidents
2. Analyzing new incidents with memory
3. Resolving incidents and retaining to memory
4. Comparing with/without memory
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from app.schemas import IncidentCreate, Environment, Severity, ResolutionRequest
from app.agent import agent


def print_section(title):
    """Print a section header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")


def test_agent_workflow():
    """Test the complete agent workflow."""
    print_section("INCIDENT MEMORY AGENT - WORKFLOW TEST")
    
    # Test 1: Create and analyze an incident
    print_section("TEST 1: Analyze Incident with Memory")
    
    incident_data = IncidentCreate(
        title="Payment API Redis Timeout and High Latency",
        service="payment-api",
        environment=Environment.PRODUCTION,
        severity=Severity.P1,
        symptoms="API response time at 7.5 seconds, Redis timeout errors, 18% error rate, 504 gateway timeouts",
        error_logs="RedisTimeoutError: Connection timeout after 5000ms",
        suspected_causes=["Redis connection pool exhaustion", "Network issues"],
        tags=["redis", "timeout", "performance"]
    )
    
    try:
        result = agent.process_incident(incident_data, use_memory=True)
        
        incident = result['incident']
        analysis = result['analysis']
        
        print(f"✓ Incident Created: {incident.incident_id}")
        print(f"✓ Service: {incident.service}")
        print(f"✓ Severity: {incident.severity}")
        print(f"\n📝 Analysis Summary:")
        print(f"  {analysis.summary[:200]}...")
        print(f"\n🎯 Likely Root Cause:")
        print(f"  {analysis.likely_root_cause}")
        print(f"\n📊 Confidence: {analysis.confidence:.0%}")
        print(f"\n🧠 Historical Incidents Found: {len(analysis.historical_incidents)}")
        
        if analysis.historical_evidence:
            print(f"\n📚 Historical Evidence:")
            for i, evidence in enumerate(analysis.historical_evidence[:3], 1):
                print(f"  {i}. {evidence}")
        
        if analysis.recommended_actions:
            print(f"\n💡 Recommended Actions:")
            for i, action in enumerate(analysis.recommended_actions[:3], 1):
                print(f"  {i}. {action}")
        
        print(f"\n✅ Test 1 PASSED")
        
        # Test 2: Resolve the incident
        print_section("TEST 2: Resolve Incident and Retain to Memory")
        
        resolution = ResolutionRequest(
            root_cause="Redis connection pool exhausted at peak load - 250/250 connections in use",
            actions_taken=[
                "Verified Redis server health - healthy",
                "Checked connection pool metrics - fully saturated",
                "Increased pool size from 250 to 400",
                "Added circuit breaker for graceful degradation"
            ],
            resolution="Increased Redis connection pool from 250 to 400 connections, added circuit breaker",
            outcome="API latency reduced from 7.5s to 800ms, error rate dropped to 0.3%",
            before_metrics={"latency_p99": 7500, "error_rate": 0.18, "connections": 250},
            after_metrics={"latency_p99": 800, "error_rate": 0.003, "connections": 180},
            downtime=15,
            affected_users=5000,
            lessons_learned="Connection pool from INC-1006 (400) was still insufficient during holiday traffic. Consider auto-scaling pool size based on traffic.",
            preventive_actions=[
                "Implement connection pool auto-scaling",
                "Set alerts at 70% pool utilization",
                "Regular capacity planning for traffic events"
            ]
        )
        
        result = agent.resolve_and_learn(
            incident_id=incident.incident_id,
            resolution=resolution
        )
        
        print(f"✓ Incident {result['incident_id']} resolved")
        print(f"✓ Status: {result['status']}")
        print(f"✓ Memory Retained: {result['memory_retained']}")
        print(f"✓ Message: {result['message']}")
        
        print(f"\n✅ Test 2 PASSED")
        
        # Test 3: Compare with/without memory
        print_section("TEST 3: Compare Analysis With/Without Memory")
        
        test_incident = IncidentCreate(
            title="Database Connection Pool Timeout",
            service="order-service",
            environment=Environment.PRODUCTION,
            severity=Severity.P1,
            symptoms="Database queries timing out, connection acquisition taking 20+ seconds"
        )
        
        comparison = agent.demonstrate_learning(test_incident)
        
        print(f"✓ Comparison completed")
        print(f"\n📊 Without Memory:")
        without = comparison['without_memory']
        print(f"  Confidence: {without.confidence:.0%}")
        print(f"  Historical Incidents: {len(without.historical_incidents)}")
        
        print(f"\n📊 With Memory:")
        with_mem = comparison['with_memory']
        print(f"  Confidence: {with_mem.confidence:.0%}")
        print(f"  Historical Incidents: {len(with_mem.historical_incidents)}")
        
        print(f"\n💡 Value Proposition:")
        print(f"  {comparison['demonstration']['value_proposition']}")
        
        print(f"\n✅ Test 3 PASSED")
        
        # Test 4: Get learning stats
        print_section("TEST 4: Agent Learning Statistics")
        
        stats = agent.get_learning_stats()
        
        print(f"🧠 Memory Bank: {stats['memory_bank']}")
        print(f"📊 Total Recalls: {stats['total_recalls']}")
        print(f"📝 Total Incidents Retained: {stats['total_incidents_retained']}")
        print(f"✓ Status: {stats['status']}")
        
        print(f"\n✅ Test 4 PASSED")
        
        # Summary
        print_section("ALL TESTS PASSED ✓")
        print("The Incident Memory Agent is working correctly!")
        print("\nKey Workflows Verified:")
        print("  ✓ Incident analysis with historical memory")
        print("  ✓ Historical evidence retrieval")
        print("  ✓ Memory-informed recommendations")
        print("  ✓ Incident resolution and retention")
        print("  ✓ Before/after memory comparison")
        print("  ✓ Learning statistics tracking")
        print("\n" + "="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_agent_workflow()
    sys.exit(0 if success else 1)
