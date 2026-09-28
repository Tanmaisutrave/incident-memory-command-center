"""
Seed script to populate Hindsight with synthetic incident data.

This script creates realistic production incidents across different services
and failure types, then stores them in Hindsight memory.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from app.hindsight_client import hindsight_client


# Synthetic incident data
INCIDENTS = [
    {
        "incident_id": "INC-1001",
        "title": "Payment API Redis Timeout - High Latency",
        "service": "payment-api",
        "environment": "production",
        "severity": "P1",
        "symptoms": "API response time increased to 8.2 seconds, Redis timeout errors in logs, 502 bad gateway responses, error rate 23%",
        "error_logs": "RedisTimeoutError: Timeout connecting to Redis after 5000ms. Connection pool saturated.",
        "root_cause": "Redis connection pool exhaustion. Pool configured for 100 max connections, but peak traffic required 180+ connections.",
        "actions_taken": [
            "Verified Redis server health - OK",
            "Checked connection pool metrics - 100/100 in use",
            "Increased pool size from 100 to 250",
            "Restarted application pods"
        ],
        "resolution": "Increased Redis connection pool size from 100 to 250 connections in application configuration",
        "outcome": "API latency reduced from 8.2s to 1.1s, error rate dropped to 0%, Redis connections stabilized at 140-160 during peak",
        "downtime": 18,
        "lessons_learned": "Monitor connection pool utilization proactively. Set alerts at 80% capacity. Connection pool was undersized for peak traffic.",
        "tags": ["redis", "connection-pool", "performance", "timeout"]
    },
    {
        "incident_id": "INC-1002",
        "title": "Order Service Database Connection Exhaustion",
        "service": "order-service",
        "environment": "production",
        "severity": "P1",
        "symptoms": "Service timing out on database queries, connection acquisition taking 15+ seconds, 500 errors",
        "error_logs": "PSQLException: Connection is not available, request timed out after 30000ms",
        "root_cause": "PostgreSQL connection pool exhausted due to long-running queries holding connections",
        "actions_taken": [
            "Identified slow queries holding connections",
            "Killed long-running queries",
            "Optimized problematic query with index",
            "Increased connection pool from 50 to 100"
        ],
        "resolution": "Added missing index on orders.created_at column, increased connection pool size, set stricter query timeouts",
        "outcome": "Query time reduced from 45s to 0.3s, connection pool usage normalized to 30-40",
        "downtime": 25,
        "lessons_learned": "Missing database indexes can cascade into connection pool exhaustion. Regular query performance audits needed.",
        "tags": ["database", "postgres", "connection-pool", "performance"]
    },
    {
        "incident_id": "INC-1003",
        "title": "API Gateway Timeout to User Service",
        "service": "api-gateway",
        "environment": "production",
        "severity": "P2",
        "symptoms": "Gateway timing out after 30 seconds when calling user-service, intermittent 504 Gateway Timeout",
        "error_logs": "GatewayTimeout: Upstream request timeout after 30000ms to user-service.internal:8080",
        "root_cause": "Network latency spike between gateway and user-service due to AWS AZ connectivity issue",
        "actions_taken": [
            "Verified user-service health - responding normally",
            "Checked network latency - 500-800ms vs normal 2-5ms",
            "Checked AWS health dashboard - AZ connectivity issue reported",
            "Waited for AWS resolution"
        ],
        "resolution": "AWS resolved AZ connectivity issue. No application changes required.",
        "outcome": "Network latency returned to normal 2-5ms. Timeouts ceased.",
        "downtime": 45,
        "lessons_learned": "Sometimes root cause is infrastructure, not application. Have runbook for AZ connectivity checks.",
        "tags": ["network", "timeout", "aws", "infrastructure"]
    },
    {
        "incident_id": "INC-1004",
        "title": "Notification Service Memory Leak OOMKilled",
        "service": "notification-service",
        "environment": "production",
        "severity": "P2",
        "symptoms": "Service pod restarting every 2-3 hours with OOMKilled status, memory usage climbing steadily to 2GB limit",
        "error_logs": "OOMKilled: Container exceeded memory limit of 2Gi",
        "root_cause": "Memory leak in email template caching - templates never expired from cache",
        "actions_taken": [
            "Analyzed memory dumps",
            "Identified growing cache with no eviction",
            "Fixed cache implementation to use LRU with max size",
            "Deployed fix and monitored"
        ],
        "resolution": "Implemented LRU cache with max 1000 entries and 1-hour TTL for email templates",
        "outcome": "Memory usage stabilized at 400-500MB. No more OOMKilled events.",
        "downtime": 0,
        "lessons_learned": "Always implement cache eviction policies. Memory leaks manifest gradually.",
        "tags": ["memory", "oom", "kubernetes", "cache"]
    },
    {
        "incident_id": "INC-1005",
        "title": "Inventory Service CPU Saturation",
        "service": "inventory-service",
        "environment": "production",
        "severity": "P1",
        "symptoms": "Service responding slowly (5-10s), CPU at 100%, high system load",
        "error_logs": "Service degraded: CPU throttling detected, response time P99: 9800ms",
        "root_cause": "Inefficient inventory calculation loop processing 50k items synchronously on each request",
        "actions_taken": [
            "Profiled application CPU usage",
            "Identified hot path in inventory calculation",
            "Implemented caching for inventory totals",
            "Added background job for pre-calculation"
        ],
        "resolution": "Moved inventory calculation to background job running every 5 minutes, cached results in Redis",
        "outcome": "CPU dropped to 15-20%, response time improved to 50-100ms",
        "downtime": 35,
        "lessons_learned": "Don't perform expensive calculations synchronously in request path. Use caching and background jobs.",
        "tags": ["cpu", "performance", "optimization"]
    },
    {
        "incident_id": "INC-1006",
        "title": "Payment API Redis Timeout During Flash Sale",
        "service": "payment-api",
        "environment": "production",
        "severity": "P1",
        "symptoms": "API latency spiked to 6.5 seconds during flash sale, Redis timeout errors, 15% error rate",
        "error_logs": "RedisTimeoutError: Command timeout after 5000ms",
        "root_cause": "Redis connection pool saturated during traffic spike - pool at 250/250, waiting requests queued",
        "actions_taken": [
            "Checked Redis server metrics - healthy",
            "Verified connection pool - fully saturated",
            "Temporarily increased pool to 400",
            "Added Redis read replicas for read traffic"
        ],
        "resolution": "Increased connection pool to 400, configured read replicas for read operations, added circuit breaker",
        "outcome": "API handled 3x traffic spike gracefully, latency stayed under 500ms, no timeouts",
        "downtime": 12,
        "lessons_learned": "Flash sales require capacity planning. Previous pool increase (INC-1001) was insufficient for peak events.",
        "tags": ["redis", "connection-pool", "capacity", "timeout"]
    },
    {
        "incident_id": "INC-1007",
        "title": "User Service Kafka Consumer Lag Spike",
        "service": "user-service",
        "environment": "production",
        "severity": "P2",
        "symptoms": "Kafka consumer lag growing to 50k messages, user profile updates delayed by 30+ minutes",
        "error_logs": "KafkaConsumer: Partition lag increasing, current offset 45283, latest offset 95621",
        "root_cause": "Consumer processing too slowly due to synchronous database writes for each message",
        "actions_taken": [
            "Scaled up consumer instances from 3 to 10",
            "Implemented batch processing for database writes",
            "Increased consumer threads per instance"
        ],
        "resolution": "Refactored consumer to batch database writes (100 messages per batch), scaled to 10 instances",
        "outcome": "Consumer lag cleared in 15 minutes, processing rate increased from 50 msg/sec to 500 msg/sec",
        "downtime": 0,
        "lessons_learned": "Batch database operations for high-throughput consumers. Horizontal scaling alone isn't enough.",
        "tags": ["kafka", "consumer-lag", "performance", "database"]
    },
    {
        "incident_id": "INC-1008",
        "title": "Order Service Disk Space Full",
        "service": "order-service",
        "environment": "production",
        "severity": "P1",
        "symptoms": "Service crashing with disk write errors, pod evicted by Kubernetes",
        "error_logs": "IOError: No space left on device. Unable to write log file.",
        "root_cause": "Application logs not rotated, filled 20GB persistent volume",
        "actions_taken": [
            "Cleared old log files manually",
            "Configured log rotation (7 days retention, 1GB max)",
            "Increased PV size to 50GB",
            "Set up disk usage alerts at 80%"
        ],
        "resolution": "Implemented log rotation, increased volume size, added monitoring",
        "outcome": "Disk usage stabilized at 15-20%, logs automatically rotated",
        "downtime": 8,
        "lessons_learned": "Always configure log rotation. Monitor disk usage proactively.",
        "tags": ["disk", "storage", "kubernetes", "logging"]
    },
    {
        "incident_id": "INC-1009",
        "title": "Payment Gateway Third-Party Timeout",
        "service": "payment-api",
        "environment": "production",
        "severity": "P1",
        "symptoms": "Payment processing failing, timeout errors calling Stripe API, 60% failure rate",
        "error_logs": "StripeAPIError: Request timeout after 30000ms, connection refused",
        "root_cause": "Stripe API experiencing outage in us-east-1 region",
        "actions_taken": [
            "Checked Stripe status page - outage confirmed",
            "Enabled fallback to backup payment processor",
            "Communicated with customers",
            "Waited for Stripe resolution"
        ],
        "resolution": "Stripe resolved their outage after 45 minutes. Switched back to Stripe as primary.",
        "outcome": "Payment processing restored. Backup processor handled 40% of traffic during outage.",
        "downtime": 45,
        "lessons_learned": "Third-party dependencies fail. Always have fallback processors and status page monitoring.",
        "tags": ["third-party", "payment", "timeout", "external"]
    },
    {
        "incident_id": "INC-1010",
        "title": "Notification Service Database Connection Leak",
        "service": "notification-service",
        "environment": "production",
        "severity": "P2",
        "symptoms": "Connections to PostgreSQL growing unbounded, reaching max_connections limit of 200",
        "error_logs": "PSQLException: FATAL: sorry, too many clients already",
        "root_cause": "Database connections not properly closed in error handling path",
        "actions_taken": [
            "Identified connection leak in exception handler",
            "Fixed code to ensure connections closed in finally block",
            "Restarted service to clear leaked connections",
            "Added connection pool monitoring"
        ],
        "resolution": "Fixed connection leak bug, implemented proper resource cleanup with context managers",
        "outcome": "Connection count stabilized at 10-15, well under limit",
        "downtime": 5,
        "lessons_learned": "Always use try-finally or context managers for resource cleanup. Monitor connection counts.",
        "tags": ["database", "connection-leak", "postgres", "bug"]
    },
    {
        "incident_id": "INC-1011",
        "title": "Order Service Cache Invalidation Storm",
        "service": "order-service",
        "environment": "production",
        "severity": "P2",
        "symptoms": "Sudden spike in database load, cache hit rate dropped from 95% to 5%, slow responses",
        "error_logs": "Database connection pool saturated, query latency P99: 5000ms",
        "root_cause": "Cache invalidation bug cleared entire cache instead of single entry, causing cache stampede",
        "actions_taken": [
            "Identified bug in cache invalidation logic",
            "Temporarily disabled automatic invalidation",
            "Manually warmed cache",
            "Deployed fix for targeted invalidation"
        ],
        "resolution": "Fixed cache invalidation to only clear specific keys, not entire cache",
        "outcome": "Cache hit rate recovered to 94%, database load returned to normal",
        "downtime": 15,
        "lessons_learned": "Test cache invalidation logic carefully. Implement gradual cache warming after failures.",
        "tags": ["cache", "database", "performance", "bug"]
    },
    {
        "incident_id": "INC-1012",
        "title": "User Service Pod CrashLoopBackOff",
        "service": "user-service",
        "environment": "production",
        "severity": "P1",
        "symptoms": "Kubernetes pods in CrashLoopBackOff state, service unavailable",
        "error_logs": "Readiness probe failed: HTTP probe failed with statuscode: 503. Liveness probe failed.",
        "root_cause": "Application startup taking 35 seconds, readiness probe timeout set to 10 seconds",
        "actions_taken": [
            "Analyzed slow startup - database migrations running on every pod start",
            "Increased readiness probe timeout to 60 seconds",
            "Moved migrations to init container",
            "Optimized application startup time"
        ],
        "resolution": "Moved database migrations to Kubernetes init job, increased probe timeouts, optimized startup",
        "outcome": "Pods start successfully in 5 seconds, no more CrashLoopBackOff",
        "downtime": 20,
        "lessons_learned": "Readiness probes must match actual startup time. Don't run migrations in application startup.",
        "tags": ["kubernetes", "crashloop", "readiness", "startup"]
    }
]


def seed_incidents():
    """Seed Hindsight with synthetic incident data."""
    print("\n" + "="*60)
    print("  INCIDENT MEMORY SEEDING")
    print("="*60)
    print(f"Bank ID: {hindsight_client.bank_id}")
    print(f"Incidents to seed: {len(INCIDENTS)}")
    print("="*60 + "\n")
    
    success_count = 0
    failed_count = 0
    
    for idx, incident in enumerate(INCIDENTS, 1):
        try:
            print(f"[{idx}/{len(INCIDENTS)}] Seeding {incident['incident_id']}...")
            
            # Build memory content
            content = f"""INCIDENT: {incident['incident_id']} - {incident['title']}

Service: {incident['service']}
Environment: {incident['environment']}
Severity: {incident['severity']}

SYMPTOMS:
{incident['symptoms']}

ERROR LOGS:
{incident.get('error_logs', 'N/A')}

ROOT CAUSE:
{incident['root_cause']}

ACTIONS TAKEN:
{chr(10).join(f'- {action}' for action in incident.get('actions_taken', []))}

RESOLUTION:
{incident['resolution']}

OUTCOME:
{incident['outcome']}

DOWNTIME: {incident.get('downtime', 0)} minutes

LESSONS LEARNED:
{incident.get('lessons_learned', 'N/A')}
"""
            
            # Build metadata
            metadata = {
                "incident_id": incident['incident_id'],
                "service": incident['service'],
                "environment": incident['environment'],
                "severity": incident['severity'],
                "tags": ",".join(incident.get('tags', []))
            }
            
            # Retain to Hindsight
            result = hindsight_client.retain(
                content=content,
                metadata=metadata,
                context=f"Historical incident for {incident['service']}"
            )
            
            if result.get('success'):
                print(f"  ✓ {incident['incident_id']} retained successfully")
                success_count += 1
            else:
                print(f"  ✗ {incident['incident_id']} failed to retain")
                failed_count += 1
                
        except Exception as e:
            print(f"  ✗ {incident['incident_id']} error: {e}")
            failed_count += 1
    
    print("\n" + "="*60)
    print("  SEEDING COMPLETE")
    print("="*60)
    print(f"Successfully seeded: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Total: {len(INCIDENTS)}")
    print("="*60 + "\n")
    
    return success_count == len(INCIDENTS)


if __name__ == "__main__":
    success = seed_incidents()
    sys.exit(0 if success else 1)
