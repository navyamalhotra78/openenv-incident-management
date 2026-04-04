import random
from models.incident import Incident
from models.task_config import TaskConfig
from env.constants import SLA_STEPS
from env.incident_templates import INCIDENT_TEMPLATES, TEMPLATE_BY_ID

SERVICES_BASIC    = ["auth", "payments", "trading", "ui"]
SERVICES_EXTENDED = ["auth", "payments", "trading", "ui", "database", "api-gateway"]


def generate_incidents(config: TaskConfig, current_step: int = 0) -> list[Incident]:
    if config.task_id == 1:
        return _task1(current_step)
    elif config.task_id == 2:
        return _task2(current_step)
    elif config.task_id == 3:
        return _task3(current_step)
    elif config.task_id == 4:
        return _task4(current_step)
    return []


def _sla(severity: str, step: int) -> int:
    return step + SLA_STEPS[severity]


def _incident_from_template(
    template: dict,
    incident_id: str,
    step: int,
    **overrides,
) -> Incident:
    """Build an Incident from a template dict, merging any overrides."""
    severity = overrides.pop("severity", template["severity"])
    return Incident(
        id=incident_id,
        severity=severity,
        service=overrides.pop("service", template["service"]),
        status="open",
        title=template["title"],
        metrics=dict(template["metrics"]),
        logs=list(template["logs"]),
        sla_deadline=_sla(severity, step),
        true_team=template["true_team"],
        true_root_cause=template["true_root_cause"],
        valid_fixes=list(template["valid_fixes"]),
        required_fix_order=list(template["required_fix_order"]),
        prevention_steps=list(template["prevention_steps"]),
        **overrides,
    )


# ── Task 1 — single alert ─────────────────────────────────────────────────────
def _task1(step: int) -> list[Incident]:
    tmpl = random.choice(INCIDENT_TEMPLATES)
    return [_incident_from_template(tmpl, "INC-001", step)]


# ── Task 2 — multi-service queue ──────────────────────────────────────────────
def _task2(step: int) -> list[Incident]:
    """
    4 incidents from distinct templates.
    - Guaranteed one critical, one high, one medium, one low.
    - One incident is a false alarm (unconfirmed).
    - Critical incident is root cause of the low-severity incident.
    """
    templates = random.sample(INCIDENT_TEMPLATES, min(4, len(INCIDENT_TEMPLATES)))
    severity_slots = ["critical", "high", "medium", "low"]
    random.shuffle(severity_slots)

    incidents = [
        _incident_from_template(t, f"INC-{i + 1:03d}", step, severity=sev)
        for i, (t, sev) in enumerate(zip(templates, severity_slots))
    ]

    # Root cause link: critical → low
    sorted_inc = sorted(incidents, key=lambda x: ["low","medium","high","critical"].index(x.severity))
    root, symptom = sorted_inc[-1], sorted_inc[0]   # critical, low
    root.is_root_cause = True
    symptom.root_cause_id = root.id

    # False alarm on the second-lowest severity
    false_alarm = sorted_inc[1]
    false_alarm.confirmed = False
    false_alarm.is_false_alarm = True

    return incidents


# ── Task 3 — cascading failures ───────────────────────────────────────────────
def _task3(step: int) -> list[Incident]:
    """
    3 incidents: 2 critical/high on cascade-capable services, 1 medium.
    Critical requires 2 resolution steps.
    Critical is root cause of high.
    """
    cascade_tmpls  = [t for t in INCIDENT_TEMPLATES if t["service"] in ("database", "api-gateway", "auth")]
    leaf_tmpls     = [t for t in INCIDENT_TEMPLATES if t["service"] in ("trading", "ui", "payments", "auth")]

    t1 = random.choice(cascade_tmpls)
    t2 = random.choice([t for t in cascade_tmpls if t["id"] != t1["id"]] or cascade_tmpls)
    t3 = random.choice(leaf_tmpls)

    inc1 = _incident_from_template(t1, "INC-001", step, severity="critical",
                                   is_root_cause=True, resolution_steps=2)
    inc2 = _incident_from_template(t2, "INC-002", step, severity="high",
                                   root_cause_id="INC-001")
    inc3 = _incident_from_template(t3, "INC-003", step, severity="medium")
    return [inc1, inc2, inc3]


# ── Task 4 — full lifecycle ───────────────────────────────────────────────────
def _task4(step: int) -> list[Incident]:
    """Single complex incident requiring the full triage → postmortem lifecycle."""
    tmpl = random.choice(INCIDENT_TEMPLATES)
    return [_incident_from_template(tmpl, "INC-001", step)]


# ── Mid-episode random arrival ────────────────────────────────────────────────
def spawn_random_incident(existing_ids: set[str], current_step: int, task_id: int) -> Incident:
    tmpl = random.choice(INCIDENT_TEMPLATES)
    severity = random.choices(
        ["low", "medium", "high"],
        weights=[0.5, 0.35, 0.15],
    )[0]

    n = len(existing_ids) + 1
    while f"NEW-{n:02d}" in existing_ids:
        n += 1

    return _incident_from_template(tmpl, f"NEW-{n:02d}", current_step, severity=severity)
