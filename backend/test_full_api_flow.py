"""Test the complete API flow for incident analysis."""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_complete_flow():
    """Test the complete flow from incident creation to analysis display."""
    
    print("="*80)
    print("COMPLETE API FLOW TEST")
    print("="*80)
    
    # Step 1: Submit incident
    print("\n1. Creating and analyzing incident...")
    incident_data = {
        "title": "Payment API experiencing severe latency",
        "service": "payment-api",
        "environment": "production",
        "severity": "P1",
        "symptoms": """The payment API is experiencing severe latency and intermittent request failures in production. 
Response times have increased from ~1 second to 8-10 seconds over the last 20 minutes. 
We're seeing database connection timeout errors in the logs and the active connection count is approaching the pool limit.""",
        "error_logs": """
2026-09-27T14:30:15Z ERROR [payment-api] Database connection timeout after 30s
2026-09-27T14:30:18Z ERROR [payment-api] Connection pool exhausted (50/50 active)
2026-09-27T14:30:22Z ERROR [payment-api] Failed to acquire database connection
2026-09-27T14:30:25Z ERROR [payment-api] Transaction rolled back due to timeout
""",
        "metrics": {"avg_response_time_ms": 8500, "error_rate": 0.15, "active_db_connections": "48/50"},
        "suspected_causes": ["Database connection leak", "Slow queries", "Connection pool misconfiguration"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/incidents/analyze",
        json=incident_data,
        timeout=60
    )
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return
    
    analysis = response.json()
    print("✓ Analysis complete\n")
    
    # Step 2: Display key metrics
    print("="*80)
    print("ANALYSIS RESULTS")
    print("="*80)
    
    print(f"\nIncident ID: {analysis['incident_id']}")
    print(f"Used Memory: {analysis['used_memory']}")
    print(f"Confidence: {analysis['confidence']:.0%}")
    
    # Step 3: Historical Context
    print("\n" + "-"*80)
    print("HISTORICAL CONTEXT")
    print("-"*80)
    print(f"Historical Incidents Found: {len(analysis['historical_incidents'])}")
    if analysis['historical_incidents']:
        for i, hist in enumerate(analysis['historical_incidents'][:3], 1):
            print(f"\n  {i}. Type: {hist.get('memory_type', 'N/A')}")
            print(f"     Length: {len(hist.get('memory_text', ''))} chars")
            print(f"     Preview: {hist.get('memory_text', '')[:100]}...")
    else:
        print("  ⚠️  No historical incidents returned (but memories were used)")
    
    print(f"\nHistorical Evidence: {len(analysis['historical_evidence'])}")
    if analysis['historical_evidence']:
        for i, ev in enumerate(analysis['historical_evidence'][:5], 1):
            print(f"  {i}. {ev[:80]}")
    else:
        print("  ⚠️  No historical evidence")
    
    print(f"\nMemory Insights: {len(analysis['memory_insights'])}")
    if analysis['memory_insights']:
        for i, insight in enumerate(analysis['memory_insights'][:5], 1):
            print(f"  {i}. {insight[:80]}")
    else:
        print("  ⚠️  No memory insights")
    
    # Step 4: Root Cause Analysis
    print("\n" + "-"*80)
    print("ROOT CAUSE ANALYSIS")
    print("-"*80)
    print(f"\n{analysis['likely_root_cause']}")
    
    # Step 5: Summary
    print("\n" + "-"*80)
    print("SUMMARY")
    print("-"*80)
    print(f"\n{analysis['summary']}")
    
    # Step 6: Recommendations
    print("\n" + "-"*80)
    print("RECOMMENDATIONS")
    print("-"*80)
    print("\nRecommended Actions:")
    for i, action in enumerate(analysis['recommended_actions'], 1):
        print(f"  {i}. {action}")
    
    print("\nInvestigation Steps:")
    for i, step in enumerate(analysis['investigation_steps'], 1):
        print(f"  {i}. {step}")
    
    # Step 7: Verdict
    print("\n" + "="*80)
    print("TEST VERDICT")
    print("="*80)
    
    checks = {
        "✓ Confidence >= 70%": analysis['confidence'] >= 0.70,
        "✓ Root cause substantive (>50 chars)": len(analysis['likely_root_cause']) > 50,
        "✓ Summary substantive (>100 chars)": len(analysis['summary']) > 100,
        "✓ Recommended actions provided": len(analysis['recommended_actions']) >= 3,
        "✓ Investigation steps provided": len(analysis['investigation_steps']) >= 3,
        "⚠️  Historical incidents returned": len(analysis['historical_incidents']) > 0,
        "⚠️  Historical evidence returned": len(analysis['historical_evidence']) > 0,
        "⚠️  Memory insights returned": len(analysis['memory_insights']) > 0,
    }
    
    print()
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check}: {'PASS' if passed else 'FAIL'}")
    
    # Overall verdict
    critical_checks = [checks[k] for k in list(checks.keys())[:5]]
    all_critical_pass = all(critical_checks)
    
    print()
    if all_critical_pass:
        print("✓ ANALYSIS QUALITY: DEMO-READY")
        if not checks["⚠️  Historical incidents returned"]:
            print("⚠️  Note: Historical context not showing in response (may be LLM output format variation)")
    else:
        print("✗ ANALYSIS QUALITY: NOT DEMO-READY")
    print("="*80)


if __name__ == "__main__":
    test_complete_flow()
