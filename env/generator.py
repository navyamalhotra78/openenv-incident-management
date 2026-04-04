import random
from models.incident import Incident
from models.task_config import TaskConfig

SEVERITIES = ["low", "medium", "high", "critical"]
SERVICES_BASIC = ["auth", "payments", "trading", "ui"]
SERVICES_EXTENDED = ["auth", "payments", "trading", "ui", "database", "api-gateway"]


def generate_incidents(config: TaskConfig) -> list[Incident]:
    if config.task_id == 1:
        return _task1()
    elif config.task_id == 2:
        return _task2()
    elif config.task_id == 3:
        return _task3()
    return []


def _task1() -> list[Incident]:
    return [
        Incident(
            id="INC-001",
            severity=random.choice(SEVERITIES),
            service=random.choice(SERVICES_BASIC),
            status="open",
        )
    ]


def _task2() -> list[Incident]:
    # Guaranteed one of each severity level for meaningful priority decisions
    severities = ["critical", "high", "medium", "low"]
    random.shuffle(severities)
    services = random.sample(SERVICES_BASIC, 4)
    return [
        Incident(id=f"INC-{i + 1:03d}", severity=sev, service=svc, status="open")
        for i, (sev, svc) in enumerate(zip(severities, services))
    ]


def _task3() -> list[Incident]:
    # Two high/critical incidents on cascade-capable services + one medium
    trigger_services = random.sample(["database", "api-gateway", "auth"], 2)
    leaf_service = random.choice(["trading", "ui", "payments"])
    return [
        Incident(id="INC-001", severity="critical", service=trigger_services[0], status="open"),
        Incident(id="INC-002", severity="high",     service=trigger_services[1], status="open"),
        Incident(id="INC-003", severity="medium",   service=leaf_service,        status="open"),
    ]
