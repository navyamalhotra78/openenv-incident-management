"""
Shared constants used across graders, generator, and environment.
"""

# Severity weights for grading (sum = 1.0)
SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 0.4,
    "high":     0.3,
    "medium":   0.2,
    "low":      0.1,
}

# Business impact multiplier per service — reflects real-world revenue/user impact
SERVICE_IMPACT: dict[str, float] = {
    "payments":    1.5,
    "trading":     1.4,
    "database":    1.3,
    "auth":        1.2,
    "api-gateway": 1.1,
    "ui":          1.0,
}

# Steps from incident creation before SLA breach
SLA_STEPS: dict[str, int] = {
    "critical": 4,
    "high":     6,
    "medium":   10,
    "low":      15,
}

# Steps open before severity auto-escalates to next level
ESCALATION_STEPS: dict[str, int] = {
    "low":    4,
    "medium": 3,
    "high":   3,
    # critical: no further escalation
}

SEVERITY_UPGRADE: dict[str, str] = {
    "low":    "medium",
    "medium": "high",
    "high":   "critical",
}

# Steps without acknowledgment before critical/high incidents auto-escalate
ACK_TIMEOUT: dict[str, int] = {
    "critical": 2,
    "high":     3,
}


def incident_weight(inc) -> float:
    """Severity × service impact — combined grading weight for one incident."""
    return SEVERITY_WEIGHTS[inc.severity] * SERVICE_IMPACT[inc.service]
