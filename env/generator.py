import random
from models.incident import Incident
from models.task_config import TaskConfig
from env.constants import SLA_STEPS

SEVERITIES = ["low", "medium", "high", "critical"]
SERVICES_BASIC = ["auth", "payments", "trading", "ui"]
SERVICES_EXTENDED = ["auth", "payments", "trading", "ui", "database", "api-gateway"]


def generate_incidents(config: TaskConfig, current_step: int = 0) -> list[Incident]:
    if config.task_id == 1:
        return _task1(current_step)
    elif config.task_id == 2:
        return _task2(current_step)
    elif config.task_id == 3:
        return _task3(current_step)
    return []


def _sla(severity: str, current_step: int) -> int:
    return current_step + SLA_STEPS[severity]


# ── Task 1 ────────────────────────────────────────────────────────────────────
def _task1(step: int) -> list[Incident]:
    sev = random.choice(SEVERITIES)
    return [
        Incident(
            id="INC-001",
            severity=sev,
            service=random.choice(SERVICES_BASIC),
            status="open",
            sla_deadline=_sla(sev, step),
        )
    ]


# ── Task 2 ────────────────────────────────────────────────────────────────────
def _task2(step: int) -> list[Incident]:
    """
    4 incidents — guaranteed one of each severity.
    - 1 incident is a false alarm (unconfirmed).
    - INC-001 (critical) is the root cause of INC-003 (medium).
    """
    severities = ["critical", "high", "medium", "low"]
    random.shuffle(severities)
    services = random.sample(SERVICES_BASIC, 4)

    incidents = [
        Incident(
            id=f"INC-{i + 1:03d}",
            severity=sev,
            service=svc,
            status="open",
            sla_deadline=_sla(sev, step),
        )
        for i, (sev, svc) in enumerate(zip(severities, services))
    ]

    # Root cause link: highest-severity incident is root cause of lowest-severity incident
    sorted_by_sev = sorted(incidents, key=lambda x: ["low","medium","high","critical"].index(x.severity))
    root = sorted_by_sev[-1]  # critical
    symptom = sorted_by_sev[0]  # low
    root.is_root_cause = True
    symptom.root_cause_id = root.id

    # One false alarm — pick the medium or low incident
    false_alarm = sorted_by_sev[1]  # second lowest
    false_alarm.confirmed = False
    false_alarm.is_false_alarm = True

    return incidents


# ── Task 3 ────────────────────────────────────────────────────────────────────
def _task3(step: int) -> list[Incident]:
    """
    3 incidents on cascade-capable services.
    - INC-001 (critical): root cause, requires 2 resolve actions.
    - INC-002 (high): symptom of INC-001.
    - INC-003 (medium): independent leaf service.
    """
    trigger_services = random.sample(["database", "api-gateway", "auth"], 2)
    leaf_service = random.choice(["trading", "ui", "payments"])

    inc1 = Incident(
        id="INC-001",
        severity="critical",
        service=trigger_services[0],
        status="open",
        sla_deadline=_sla("critical", step),
        is_root_cause=True,
        resolution_steps=2,
    )
    inc2 = Incident(
        id="INC-002",
        severity="high",
        service=trigger_services[1],
        status="open",
        sla_deadline=_sla("high", step),
        root_cause_id="INC-001",
    )
    inc3 = Incident(
        id="INC-003",
        severity="medium",
        service=leaf_service,
        status="open",
        sla_deadline=_sla("medium", step),
    )
    return [inc1, inc2, inc3]


# ── Dynamic mid-episode spawn ─────────────────────────────────────────────────
def spawn_random_incident(existing_ids: set[str], current_step: int, task_id: int) -> Incident:
    """Generate a new arriving incident during an episode."""
    services = SERVICES_BASIC if task_id == 2 else SERVICES_EXTENDED
    severity = random.choices(
        ["low", "medium", "high"],
        weights=[0.5, 0.35, 0.15],
    )[0]
    service = random.choice(services)

    # Generate a unique ID
    n = len(existing_ids) + 1
    while f"NEW-{n:02d}" in existing_ids:
        n += 1

    return Incident(
        id=f"NEW-{n:02d}",
        severity=severity,
        service=service,
        status="open",
        sla_deadline=_sla(severity, current_step),
    )
