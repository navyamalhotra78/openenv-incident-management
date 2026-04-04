from env.environment import IncidentEnv
from models.action import Action

env = IncidentEnv()
state = env.reset()

print("Initial State:", state)

done = False

while not done:
    incident_id = state.incidents[0].id

    action = Action(type="resolve", incident_id=incident_id)

    state, reward, done, _ = env.step(action)

    print("Step reward:", reward)

print("Finished")