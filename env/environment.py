import random
from models.state import State
from models.action import Action
from models.incident import Incident
from env.generator import generate_incidents
from env.tasks.task1 import TASK1_CONFIG, grade as grade_task1
from env.tasks.task2 import TASK2_CONFIG, grade as grade_task2
from env.tasks.task3 import TASK3_CONFIG, grade as grade_task3, CASCADE_DEPS

TASK_CONFIGS = {1: TASK1_CONFIG, 2: TASK2_CONFIG, 3: TASK3_CONFIG}
GRADERS = {1: grade_task1, 2: grade_task2, 3: grade_task3}

# An open critical/high incident triggers a cascade after this many steps of neglect
CASCADE_AGE_THRESHOLD = 2


class IncidentEnv:
    def __init__(self):
        self.state: State | None = None
        self.steps: int = 0
        self.max_steps: int = 15
        self.task_id: int = 1
        self._cascade_counter: int = 0

    def reset(self, task_id: int = 1) -> State:
        config = TASK_CONFIGS[task_id]
        self.task_id = task_id
        self.steps = 0
        self.max_steps = config.max_steps
        self._cascade_counter = 0
        incidents = generate_incidents(config)
        self.state = State(
            incidents=incidents,
            task_id=task_id,
            step=0,
            max_steps=config.max_steps,
            score=0.0,
        )
        return self.state

    def step(self, action: Action) -> tuple[State, float, bool, dict]:
        self.steps += 1

        incident = next(
            (inc for inc in self.state.incidents if inc.id == action.incident_id),
            None,
        )
        if incident is None:
            return self.state, -1.0, True, {"error": "invalid incident id"}

        status_before = incident.status

        if action.type == "resolve":
            incident.status = "resolved"
            incident.age = 0
        elif action.type == "escalate":
            incident.status = "escalated"
        elif action.type == "mitigate":
            # Buys time: resets age and acknowledges the incident (task 3)
            incident.status = "pending"
            incident.age = 0
        elif action.type == "ignore":
            pass

        # Age every non-resolved / non-escalated incident by one step
        for inc in self.state.incidents:
            if inc.status not in ("resolved", "escalated"):
                inc.age += 1

        # Task 3: check if any ageing incidents trigger cascades
        new_cascades: list[Incident] = []
        if self.task_id == 3:
            new_cascades = self._check_cascades()

        score = GRADERS[self.task_id](self.state)
        self.state.score = score
        self.state.step = self.steps

        # reward placeholder — teammate fills this in with meaningful per-step logic
        reward = 0.1  # TODO: replace with reward function

        done = (
            all(inc.status in ("resolved", "escalated") for inc in self.state.incidents)
            or self.steps >= self.max_steps
        )

        info = {
            "task_id": self.task_id,
            "step": self.steps,
            "steps_remaining": self.max_steps - self.steps,
            "action_type": action.type,
            "incident_id": action.incident_id,
            "incident_severity": incident.severity,
            "incident_service": incident.service,
            "status_before": status_before,
            "status_after": incident.status,
            "score": score,
            "resolved_count": sum(1 for inc in self.state.incidents if inc.status == "resolved"),
            "open_count": sum(1 for inc in self.state.incidents if inc.status == "open"),
            "cascades_triggered": [inc.id for inc in new_cascades],
        }

        return self.state, reward, done, info

    def _check_cascades(self) -> list[Incident]:
        """Spawn cascade incidents from aged critical/high incidents (task 3 only)."""
        new_incidents: list[Incident] = []
        services_with_open = {inc.service for inc in self.state.incidents if inc.status == "open"}

        for inc in list(self.state.incidents):
            if (
                inc.status == "open"
                and inc.severity in ("critical", "high")
                and inc.age >= CASCADE_AGE_THRESHOLD
            ):
                candidates = [s for s in CASCADE_DEPS.get(inc.service, []) if s not in services_with_open]
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
                    )
                    new_incidents.append(cascade)
                    self.state.incidents.append(cascade)
                    services_with_open.add(target_service)

        return new_incidents

    def get_state(self) -> State:
        return self.state
