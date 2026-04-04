from models.state import State
from models.action import Action
from env.generator import generate_incidents

class IncidentEnv:
    def __init__(self):
        self.state = None
        self.steps = 0
        self.max_steps = 15

    def reset(self):
        self.state = State(incidents=generate_incidents())
        self.steps = 0
        return self.state

    def step(self, action: Action):
        self.steps += 1
        reward = 0

        # find incident
        incident = None
        for inc in self.state.incidents:
            if inc.id == action.incident_id:
                incident = inc
                break

        if incident is None:
            return self.state, -1, True, {"error": "invalid id"}

        # apply action
        if action.type == "resolve":
            incident.status = "resolved"

        elif action.type == "escalate":
            incident.status = "pending"

        elif action.type == "ignore":
            pass

        # simple reward (temporary)
        reward = 0.1 #update acc to reward logic added later

        # done condition
        done = all(inc.status == "resolved" for inc in self.state.incidents)
        if self.steps >= self.max_steps:
            done = True

        return self.state, reward, done, {}
    
    def get_state(self):
        return self.state