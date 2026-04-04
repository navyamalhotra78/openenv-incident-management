import random
from typing import Optional
from models.state import State
from models.action import Action
from models.incident import Incident
from env.generator import generate_incidents, spawn_random_incident
from env.tasks.task1 import TASK1_CONFIG, grade as grade_task1
from env.tasks.task2 import TASK2_CONFIG, grade as grade_task2
from env.tasks.task3 import TASK3_CONFIG, grade as grade_task3, CASCADE_DEPS
from env.tasks.task4 import TASK4_CONFIG, grade as grade_task4
from env.graders import grader as GRADER
from env.constants import ESCALATION_STEPS, SEVERITY_UPGRADE, ACK_TIMEOUT, SLA_STEPS

TASK_CONFIGS = {1: TASK1_CONFIG, 2: TASK2_CONFIG, 3: TASK3_CONFIG, 4: TASK4_CONFIG}
GRADERS      = {1: grade_task1,  2: grade_task2,  3: grade_task3,  4: grade_task4}

CASCADE_AGE_THRESHOLD = 2
NEW_INCIDENT_PROB     = {2: 0.15, 3: 0.20}
MAX_EXTRA_INCIDENTS   = {1: 0, 2: 3, 3: 2, 4: 0}


class IncidentEnv:
    def __init__(self):
        self.state: Optional[State] = None
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
        self.state.available_actions = self._compute_available_actions()
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

        # ── 1. Acknowledge ────────────────────────────────────────────────────
        if action.type != "ignore":
            incident.acknowledged = True

        # ── 2. Apply action ───────────────────────────────────────────────────
        root_cause_resolved: list[str] = []
        false_alarm_revealed = False
        grader_feedback = ""

        if action.type == "triage":
            score, feedback = GRADER.grade_triage(action, incident)
            incident.triage_done   = score >= 0.5
            incident.triage_score  = score
            incident.assigned_team = action.team
            grader_feedback = feedback

        elif action.type == "investigate":
            if action.root_cause:
                # Root cause analysis (tasks 2-4)
                score, feedback = GRADER.grade_root_cause(action, incident)
                incident.root_cause_found  = score >= 0.5
                incident.root_cause_score  = score
                grader_feedback = feedback
            else:
                # False alarm reveal (tasks 1-3)
                false_alarm_revealed = True
                if incident.is_false_alarm:
                    incident.status = "dismissed"
                    incident.confirmed = True
                else:
                    incident.confirmed = True
                grader_feedback = (
                    "False alarm — dismissed." if incident.is_false_alarm
                    else "Confirmed real incident."
                )

        elif action.type == "execute_fix":
            if self.task_id == 4 and not incident.root_cause_found:
                grader_feedback = "Identify root cause before executing fixes."
            else:
                score, feedback = GRADER.grade_remediation(action, incident)
                incident.remediation_done     = score >= 0.5
                incident.remediation_score    = score
                incident.resolution_progress += 1
                if incident.remediation_done:
                    if incident.resolution_progress >= incident.resolution_steps:
                        if self.task_id < 4:
                            incident.status = "resolved"
                        # task 4: must write postmortem before resolving
                    else:
                        incident.status = "in_progress"
                grader_feedback = feedback

        elif action.type == "write_postmortem":
            if not incident.remediation_done:
                grader_feedback = "Must remediate before writing post-mortem."
            else:
                score, feedback = GRADER.grade_postmortem(action, incident)
                incident.postmortem_done  = score >= 0.6
                incident.postmortem_score = score
                if incident.postmortem_done:
                    incident.status = "resolved"
                grader_feedback = feedback

        elif action.type == "resolve":
            if not incident.confirmed and incident.is_false_alarm:
                grader_feedback = "Cannot resolve an unconfirmed incident — investigate first."
            elif self.task_id == 4 and not incident.postmortem_done:
                grader_feedback = "Write post-mortem before resolving (Task 4 requirement)."
            else:
                incident.resolution_progress += 1
                if incident.resolution_progress >= incident.resolution_steps:
                    incident.status = "resolved"
                    incident.age = 0
                    root_cause_resolved = self._resolve_symptoms(incident)
                else:
                    incident.status = "in_progress"

        elif action.type == "escalate":
            incident.status = "escalated"
            incident.age = 0

        elif action.type == "mitigate":
            incident.status = "pending"
            incident.age = 0

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
                    inc.age = 0
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

        # ── 8. Mid-episode new incident arrival ───────────────────────────────
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

        # ── 9. Score, available actions, done ────────────────────────────────
        score = GRADERS[self.task_id](self.state)
        self.state.score = score
        self.state.step  = self.steps
        self.state.available_actions = self._compute_available_actions()

        # reward placeholder — teammate fills this in
        reward = 0.1  # TODO: replace with reward function

        done = (
            all(i.status in terminal for i in self.state.incidents)
            or self.steps >= self.max_steps
        )

        info = {
            # ── Existing fields (unchanged for rewards teammate) ──────────────
            "task_id":            self.task_id,
            "step":               self.steps,
            "steps_remaining":    self.max_steps - self.steps,
            "action_type":        action.type,
            "incident_id":        action.incident_id,
            "incident_severity":  incident.severity,
            "incident_service":   incident.service,
            "status_before":      status_before,
            "status_after":       incident.status,
            "score":              score,
            "resolved_count":     sum(1 for i in self.state.incidents if i.status == "resolved"),
            "open_count":         sum(1 for i in self.state.incidents if i.status == "open"),
            "cascades_triggered": [i.id for i in new_cascades],
            # ── New fields ────────────────────────────────────────────────────
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
            "grader_feedback":          grader_feedback,
            "available_actions":        self.state.available_actions,
            "unacknowledged_criticals": sum(
                1 for i in self.state.incidents
                if not i.acknowledged
                and i.severity in ("critical", "high")
                and i.status not in terminal
            ),
            # Task 4 lifecycle scores
            "triage_score":      incident.triage_score,
            "root_cause_score":  incident.root_cause_score,
            "remediation_score": incident.remediation_score,
            "postmortem_score":  incident.postmortem_score,
        }

        return self.state, reward, done, info

    def get_state(self) -> Optional[State]:
        return self.state

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_available_actions(self) -> list[str]:
        terminal = {"resolved", "escalated", "dismissed"}
        active = [i for i in self.state.incidents if i.status not in terminal]

        if not active:
            return []

        if self.task_id == 4:
            actions: set[str] = {"escalate", "ignore"}
            for inc in active:
                if not inc.triage_done:
                    actions.add("triage")
                elif not inc.root_cause_found:
                    actions.add("investigate")
                elif not inc.remediation_done:
                    actions.add("execute_fix")
                elif not inc.postmortem_done:
                    actions.add("write_postmortem")
                else:
                    actions.add("resolve")
            return sorted(actions)

        # Tasks 1–3
        base = {"resolve", "escalate", "ignore", "investigate"}
        if self.task_id == 3:
            base.add("mitigate")
        # Suggest investigate if any unconfirmed incidents exist
        has_unconfirmed = any(not i.confirmed for i in active)
        if not has_unconfirmed:
            base.discard("investigate")
            # But keep it available — agent can still do root cause investigate
            base.add("investigate")
        return sorted(base)

    def _resolve_symptoms(self, root: Incident) -> list[str]:
        resolved = []
        for inc in self.state.incidents:
            if inc.root_cause_id == root.id and inc.status not in ("resolved", "dismissed"):
                inc.status = "resolved"
                inc.age = 0
                resolved.append(inc.id)
        return resolved

    def _check_cascades(self) -> list[Incident]:
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
                    from env.incident_templates import INCIDENT_TEMPLATES
                    import random as _r
                    tmpl = _r.choice(INCIDENT_TEMPLATES)
                    cascade = Incident(
                        id=f"CASCADE-{self._cascade_counter:02d}",
                        severity="high",
                        service=target_service,
                        status="open",
                        age=0,
                        is_cascade=True,
                        parent_id=inc.id,
                        sla_deadline=self.steps + SLA_STEPS["high"],
                        title=tmpl["title"],
                        metrics=dict(tmpl["metrics"]),
                        logs=list(tmpl["logs"]),
                        true_team=tmpl["true_team"],
                        true_root_cause=tmpl["true_root_cause"],
                        valid_fixes=list(tmpl["valid_fixes"]),
                        required_fix_order=list(tmpl["required_fix_order"]),
                        prevention_steps=list(tmpl["prevention_steps"]),
                    )
                    new_incidents.append(cascade)
                    self.state.incidents.append(cascade)
                    services_with_open.add(target_service)

        return new_incidents
