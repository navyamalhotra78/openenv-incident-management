import random
from models.state import State
from models.action import Action
from models.incident import Incident
from env.generator import generate_incidents, spawn_random_incident
from env.tasks.task1 import TASK1_CONFIG, grade as grade_task1
from env.tasks.task2 import TASK2_CONFIG, grade as grade_task2
from env.tasks.task3 import TASK3_CONFIG, grade as grade_task3, CASCADE_DEPS
from env.constants import ESCALATION_STEPS, SEVERITY_UPGRADE, ACK_TIMEOUT, SLA_STEPS

TASK_CONFIGS = {1: TASK1_CONFIG, 2: TASK2_CONFIG, 3: TASK3_CONFIG}
GRADERS      = {1: grade_task1,  2: grade_task2,  3: grade_task3}

# Task 3 cascade: open high/critical triggers after this many steps
CASCADE_AGE_THRESHOLD = 2

# Probability of a new incident arriving each step (tasks 2 and 3)
NEW_INCIDENT_PROB = {2: 0.15, 3: 0.20}
MAX_EXTRA_INCIDENTS = {1: 0, 2: 3, 3: 2}


class IncidentEnv:
    def __init__(self):
        self.state: State | None = None
        self.steps: int = 0
        self.max_steps: int = 15
        self.task_id: int = 1
        self._cascade_counter: int = 0
        self._extra_incident_count: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def reset(self, task_id: int = 1) -> State:
        config = TASK_CONFIGS[task_id]
        self.task_id = task_id
        self.steps = 0
        self.max_steps = config.max_steps
        self._cascade_counter = 0
        self._extra_incident_count = 0

        incidents = generate_incidents(config, current_step=0)
        self.state = State(
            incidents=incidents,
            task_id=task_id,
            step=0,
            max_steps=config.max_steps,
            score=0.0,
            sla_breaches=0,
        )
        return self.state

    def step(self, action: Action) -> tuple[State, float, bool, dict]:
        self.steps += 1

        incident = next(
            (i for i in self.state.incidents if i.id == action.incident_id), None
        )
        if incident is None:
            return self.state, -1.0, True, {"error": "invalid incident id"}

        status_before   = incident.status
        severity_before = incident.severity

        # ── 1. Acknowledge (any non-ignore action) ────────────────────────────
        if action.type != "ignore":
            incident.acknowledged = True

        # ── 2. Apply action ───────────────────────────────────────────────────
        root_cause_resolved: list[str] = []
        false_alarm_revealed = False

        if action.type == "resolve":
            if not incident.confirmed and incident.is_false_alarm:
                # Agent tried to resolve an unconfirmed false alarm — rejected, wastes step
                pass
            else:
                incident.resolution_progress += 1
                if incident.resolution_progress >= incident.resolution_steps:
                    incident.status = "resolved"
                    incident.age = 0
                    # Auto-resolve symptoms if this was the root cause
                    root_cause_resolved = self._resolve_symptoms(incident)
                else:
                    incident.status = "in_progress"

        elif action.type == "escalate":
            incident.status = "escalated"
            incident.age = 0

        elif action.type == "mitigate":
            incident.status = "pending"
            incident.age = 0

        elif action.type == "investigate":
            false_alarm_revealed = True
            if incident.is_false_alarm:
                incident.status = "dismissed"
                incident.confirmed = True
            else:
                incident.confirmed = True  # agent now knows it's real

        elif action.type == "ignore":
            pass

        # ── 3. Age non-terminal incidents ─────────────────────────────────────
        terminal = {"resolved", "escalated", "dismissed"}
        for inc in self.state.incidents:
            if inc.status not in terminal:
                inc.age += 1

        # ── 4. Severity auto-escalation ───────────────────────────────────────
        auto_escalated: list[str] = []
        for inc in self.state.incidents:
            if inc.status not in terminal and inc.severity in ESCALATION_STEPS:
                if inc.age >= ESCALATION_STEPS[inc.severity]:
                    new_sev = SEVERITY_UPGRADE[inc.severity]
                    inc.severity = new_sev
                    # Reset age after escalation so next threshold counts fresh
                    inc.age = 0
                    # Tighten SLA deadline to match new severity urgency
                    inc.sla_deadline = min(inc.sla_deadline, self.steps + SLA_STEPS[new_sev])
                    auto_escalated.append(inc.id)

        # ── 5. SLA breach detection ───────────────────────────────────────────
        newly_breached: list[str] = []
        for inc in self.state.incidents:
            if not inc.sla_breached and inc.status not in terminal:
                if self.steps >= inc.sla_deadline:
                    inc.sla_breached = True
                    self.state.sla_breaches += 1
                    newly_breached.append(inc.id)

        # ── 6. Unacknowledged auto-escalation ─────────────────────────────────
        ack_escalated: list[str] = []
        for inc in self.state.incidents:
            if (
                inc.status not in terminal
                and not inc.acknowledged
                and inc.severity in ACK_TIMEOUT
                and inc.age >= ACK_TIMEOUT[inc.severity]
            ):
                inc.status = "escalated"
                ack_escalated.append(inc.id)

        # ── 7. Task 3 cascade triggers ────────────────────────────────────────
        new_cascades: list[Incident] = []
        if self.task_id == 3:
            new_cascades = self._check_cascades()

        # ── 8. Mid-episode new incident arrival (tasks 2 & 3) ─────────────────
        new_arrivals: list[Incident] = []
        max_extra = MAX_EXTRA_INCIDENTS.get(self.task_id, 0)
        if (
            self._extra_incident_count < max_extra
            and random.random() < NEW_INCIDENT_PROB.get(self.task_id, 0)
        ):
            existing_ids = {i.id for i in self.state.incidents}
            new_inc = spawn_random_incident(existing_ids, self.steps, self.task_id)
            self.state.incidents.append(new_inc)
            new_arrivals.append(new_inc)
            self._extra_incident_count += 1

        # ── 9. Score and done ─────────────────────────────────────────────────
        score = GRADERS[self.task_id](self.state)
        self.state.score = score
        self.state.step = self.steps

        # reward placeholder — teammate fills this in with meaningful per-step logic
        reward = 0.1  # TODO: replace with reward function

        done = (
            all(i.status in ("resolved", "escalated", "dismissed") for i in self.state.incidents)
            or self.steps >= self.max_steps
        )

        info = {
            # ── Core (existing fields, unchanged for rewards teammate) ──────────
            "task_id":            self.task_id,
            "step":               self.steps,
            "steps_remaining":    self.max_steps - self.steps,
            "action_type":        action.type,
            "incident_id":        action.incident_id,
            "incident_severity":  incident.severity,   # current (may have escalated)
            "incident_service":   incident.service,
            "status_before":      status_before,
            "status_after":       incident.status,
            "score":              score,
            "resolved_count":     sum(1 for i in self.state.incidents if i.status == "resolved"),
            "open_count":         sum(1 for i in self.state.incidents if i.status == "open"),
            "cascades_triggered": [i.id for i in new_cascades],
            # ── New fields ──────────────────────────────────────────────────────
            "severity_before":          severity_before,
            "auto_escalated":           auto_escalated,
            "sla_breached_this_step":   newly_breached,
            "sla_breaches_total":       self.state.sla_breaches,
            "ack_auto_escalated":       ack_escalated,
            "root_cause_resolved":      root_cause_resolved,
            "new_arrivals":             [i.id for i in new_arrivals],
            "false_alarm_revealed":     false_alarm_revealed,
            "resolution_progress":      incident.resolution_progress,
            "resolution_steps":         incident.resolution_steps,
            "unacknowledged_criticals": sum(
                1 for i in self.state.incidents
                if not i.acknowledged and i.severity in ("critical", "high")
                and i.status not in ("resolved", "escalated", "dismissed")
            ),
        }

        return self.state, reward, done, info

    def get_state(self) -> State | None:
        return self.state

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_symptoms(self, root: Incident) -> list[str]:
        """Auto-resolve all incidents linked to this root cause."""
        resolved = []
        for inc in self.state.incidents:
            if inc.root_cause_id == root.id and inc.status not in ("resolved", "dismissed"):
                inc.status = "resolved"
                inc.age = 0
                resolved.append(inc.id)
        return resolved

    def _check_cascades(self) -> list[Incident]:
        """Task 3: spawn cascade incidents from aged critical/high open incidents."""
        new_incidents: list[Incident] = []
        services_with_open = {i.service for i in self.state.incidents if i.status == "open"}

        for inc in list(self.state.incidents):
            if (
                inc.status == "open"
                and inc.severity in ("critical", "high")
                and inc.age >= CASCADE_AGE_THRESHOLD
            ):
                candidates = [
                    s for s in CASCADE_DEPS.get(inc.service, [])
                    if s not in services_with_open
                ]
                if candidates:
                    target_service = random.choice(candidates)
                    self._cascade_counter += 1
                    cascade = Incident(
                        id=f"CASCADE-{self._cascade_counter:02d}",
                        severity="high",
                        service=target_service,
                        status="open",
                        age=0,
                        is_cascade=True,
                        parent_id=inc.id,
                        sla_deadline=self.steps + SLA_STEPS["high"],
                    )
                    new_incidents.append(cascade)
                    self.state.incidents.append(cascade)
                    services_with_open.add(target_service)

        return new_incidents
