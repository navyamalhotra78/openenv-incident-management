"""
Real-world incident templates used across all tasks.
Each template carries enough context (logs, metrics, fixes) for an agent to
reason about — not just random severity/service combinations.

Severity mapping to our model:
  SEV1 → critical | SEV2 → high | SEV3 → medium | SEV4 → low

Service mapping:
  database → "database" | infra → "api-gateway" | backend → "auth"/"payments"/"trading"
  frontend → "ui"       | security → "auth"
"""

INCIDENT_TEMPLATES: list[dict] = [
    {
        "id": "db_conn_pool",
        "title": "Database connection pool exhausted",
        "severity": "critical",
        "service": "database",
        "true_team": "database",
        "true_root_cause": "connection_leak",
        "metrics": {
            "db_connections_used": 500,
            "db_connections_max": 500,
            "query_latency_p99_ms": 8500,
            "error_rate_pct": 42.3,
            "cpu_pct": 34,
        },
        "logs": [
            "[ERROR] HikariPool-1 - Connection is not available, request timed out after 30000ms",
            "[WARN]  Active connections: 500/500 — pool saturated",
            "[ERROR] PSQLException: FATAL: remaining connection slots are reserved for non-replication superuser",
            "[INFO]  Long-running query detected: SELECT * FROM orders WHERE status='pending' (72s)",
        ],
        "valid_fixes": [
            "restart_connection_pool", "kill_long_running_queries",
            "increase_pool_size", "add_read_replica",
        ],
        "required_fix_order": ["kill_long_running_queries", "restart_connection_pool"],
        "prevention_steps": [
            "Add connection pool monitoring",
            "Set query timeout limits",
            "Use connection pooler (PgBouncer)",
        ],
    },
    {
        "id": "memory_leak",
        "title": "API service OOMKilled — memory leak",
        "severity": "high",
        "service": "auth",
        "true_team": "backend",
        "true_root_cause": "memory_leak_in_cache",
        "metrics": {
            "heap_used_mb": 3950,
            "heap_limit_mb": 4096,
            "gc_pause_ms_avg": 1200,
            "request_success_rate_pct": 61,
            "pod_restarts_1h": 7,
        },
        "logs": [
            "[WARN]  Heap usage at 96% — GC pressure high",
            "[ERROR] Container OOMKilled — pod api-server-78d9f restartCount=7",
            "[DEBUG] LRU cache size: 2.1 GB (expected: <200 MB)",
            "[INFO]  Cache TTL set to 0 (never expire) — possible misconfiguration",
        ],
        "valid_fixes": [
            "rolling_restart_pods", "clear_cache",
            "fix_cache_ttl", "increase_memory_limit",
        ],
        "required_fix_order": ["clear_cache", "fix_cache_ttl", "rolling_restart_pods"],
        "prevention_steps": [
            "Add heap usage alerts at 80%",
            "Code review for cache configuration",
            "Set memory limits in Kubernetes",
        ],
    },
    {
        "id": "cert_expiry",
        "title": "TLS certificate expired — HTTPS broken",
        "severity": "critical",
        "service": "api-gateway",
        "true_team": "infra",
        "true_root_cause": "expired_tls_cert",
        "metrics": {
            "ssl_handshake_failures_per_min": 1240,
            "https_success_rate_pct": 0,
            "cert_days_remaining": -1,
            "affected_endpoints": 12,
        },
        "logs": [
            "[ERROR] SSL_ERROR_RX_RECORD_TOO_LONG — certificate has expired",
            "[WARN]  Certificate for api.example.com expired 1 day ago",
            "[INFO]  cert-manager renewal job last run: 95 days ago (FAILED)",
            "[ERROR] ACME challenge failed — DNS record not found",
        ],
        "valid_fixes": [
            "renew_certificate", "fix_dns_acme_challenge",
            "deploy_new_cert", "update_cert_manager",
        ],
        "required_fix_order": ["fix_dns_acme_challenge", "renew_certificate", "deploy_new_cert"],
        "prevention_steps": [
            "Set cert expiry alerts at 30 days",
            "Automate cert renewal",
            "Monitor cert-manager job health",
        ],
    },
    {
        "id": "disk_full",
        "title": "Disk 100% full — writes failing",
        "severity": "high",
        "service": "database",
        "true_team": "infra",
        "true_root_cause": "log_rotation_disabled",
        "metrics": {
            "disk_used_pct": 100,
            "disk_free_gb": 0,
            "log_size_gb": 180,
            "write_errors_per_min": 320,
            "inode_used_pct": 88,
        },
        "logs": [
            "[ERROR] write /var/log/app/access.log: no space left on device",
            "[ERROR] PostgreSQL: could not write to file — disk full",
            "[WARN]  /var/log/app — 182 GB of unrotated logs found",
            "[INFO]  logrotate last run: NEVER (service disabled)",
        ],
        "valid_fixes": [
            "delete_old_logs", "enable_log_rotation",
            "add_disk_space", "compress_logs",
        ],
        "required_fix_order": ["delete_old_logs", "enable_log_rotation"],
        "prevention_steps": [
            "Enable logrotate",
            "Add disk usage alerts at 80%",
            "Move logs to object storage",
        ],
    },
    {
        "id": "ddos_attack",
        "title": "DDoS attack — abnormal traffic spike",
        "severity": "critical",
        "service": "api-gateway",
        "true_team": "security",
        "true_root_cause": "layer7_ddos",
        "metrics": {
            "requests_per_sec": 85000,
            "baseline_rps": 1200,
            "unique_source_ips": 12000,
            "waf_blocks_per_min": 45000,
            "origin_cpu_pct": 98,
        },
        "logs": [
            "[WARN]  Rate limit exceeded from 12,000 unique IPs",
            "[ERROR] Upstream timeout — origin servers overloaded",
            "[INFO]  WAF: 45,231 requests blocked in last minute (rule: rate-limit)",
            "[WARN]  Suspicious pattern: GET /api/search?q=[random] — 85k rps",
        ],
        "valid_fixes": [
            "enable_ddos_protection", "block_ip_ranges",
            "enable_rate_limiting", "scale_out_origin", "activate_challenge_page",
        ],
        "required_fix_order": [
            "enable_ddos_protection", "activate_challenge_page", "block_ip_ranges",
        ],
        "prevention_steps": [
            "Enable always-on DDoS protection",
            "Set rate limiting rules",
            "Use CDN with WAF",
        ],
    },
]

# Lookup by id
TEMPLATE_BY_ID: dict[str, dict] = {t["id"]: t for t in INCIDENT_TEMPLATES}

VALID_TEAMS: list[str] = ["backend", "database", "infra", "frontend", "security"]
