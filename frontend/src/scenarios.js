/**
 * scenarios.js — Synthetic demo incidents.
 *
 * Each scenario sets only the fields present in the incident form
 * (title, service, environment, severity, symptoms, error_logs).
 * `measurements` is stored separately as a read-only display string
 * so it can be shown in the form without being submitted as `metrics`.
 */

export const scenarios = [
  {
    name: "Recurring Redis timeout",
    title: "Checkout latency rises during peak traffic",
    service: "payment-api",
    environment: "production",
    severity: "P1",
    symptoms:
      "Checkout p99 latency rose to 7.5 seconds. Redis calls time out and 18% of requests return 502. Pool utilization is 100%, active connections 100/100. No recent deployment.",
    error_logs: "RedisTimeoutError: timeout after 5000ms; pool_wait_ms=4800",
    // display-only; not submitted to the backend
    measurements: '{ "latency_p99_ms": 7500, "error_rate": 0.18, "pool_utilization": 1 }',
  },
  {
    name: "Same symptom, new cause",
    title: "Redis timeouts despite spare pool capacity",
    service: "payment-api",
    environment: "production",
    severity: "P1",
    symptoms:
      "Redis timeouts returned after a network change. Pool utilization is 28% (70/250), Redis CPU is 22%, packet loss to Redis is 12%. The old pool-size increase has already been applied. Do not assume the historical cause is current.",
    error_logs:
      "RedisTimeoutError: timeout after 5000ms; packet_loss=12%; pool_wait_ms=2",
    measurements: '{ "pool_utilization": 0.28, "packet_loss": 0.12 }',
  },
  {
    name: "Unfamiliar TLS failure",
    title: "Partner API connections fail certificate verification",
    service: "partner-gateway",
    environment: "production",
    severity: "P2",
    symptoms:
      "All calls to the partner endpoint started failing with certificate expiration errors at midnight. Internal APIs are healthy. No database timeouts are observed.",
    error_logs: "SSLCertVerificationError: certificate has expired",
    measurements: null,
  },
];

/** Fields that live on the incident form (not measurements). */
export const FORM_FIELDS = ["title", "service", "environment", "severity", "symptoms", "error_logs"];

export const sampleAnalysis = {
  incident_id: "SAMPLE-ONLY",
  severity_assessment: "P1",
  severity_reasoning: "P1 — production checkout completely impaired.",
  summary:
    "Redis timeouts coincide with exhausted client connections. Verify pool wait time before changing capacity.",
  likely_root_cause:
    "Client-side Redis connection pool exhaustion is the leading hypothesis.",
  evidence_assessment:
    "Supported by reported pool utilization, but not yet confirmed through a diagnostic check.",
  investigation_steps: [
    "Measure pool wait time and active connections during a timeout. A full pool with rising wait time supports this hypothesis.",
    "Check Redis server capacity and connection leaks before increasing the client limit.",
  ],
  recommended_actions: [
    "If the pool is exhausted and Redis has capacity, raise the limit gradually with a rollback plan.",
  ],
  disconfirming_checks: [
    "Low pool wait time or packet loss would weaken the pool-exhaustion hypothesis.",
  ],
  verification_steps: [
    "Confirm pool wait time, checkout p99 latency and error rate return to baseline after the change.",
  ],
  historical_evidence: [
    "The synthetic incident INC-1001 reports a successful increase from 100 to 250 connections.",
  ],
  memory_insights: [
    "Previous success suggests a diagnostic starting point; it does not prove the same cause today.",
  ],
  cited_sources: ["SAMPLE-M1"],
  used_memory: true,
  memory_status: "retrieved",
  timings_ms: {},
  warnings: [],
  flagged_actions: [],
  risk_notes:
    "A larger pool can overload Redis. Confirm headroom and watch server connections.",
  historical_incidents: [
    {
      source_id: "SAMPLE-M1",
      memory_type: "experience",
      memory_text:
        "Synthetic history · INC-1001\nService: payment-api\nSymptoms: Redis timeouts and high pool wait.\nRoot cause: client pool exhaustion.\nResolution: increased connection limit from 100 to 250 after checking server headroom.\nOutcome: checkout latency recovered. This is illustrative sample data, not a live Hindsight response.",
    },
  ],
};
