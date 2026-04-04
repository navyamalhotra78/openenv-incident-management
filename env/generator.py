import random
from models.incident import Incident

SEVERITIES = ["low", "medium", "high", "critical"]
SERVICES = ["auth", "payments", "trading", "ui"]

def generate_incidents(n=5):
    incidents = []
    for i in range(n):
        incidents.append(
            Incident(
                id=f"INC{i}",
                severity=random.choice(SEVERITIES),
                service=random.choice(SERVICES),
                status="open"
            )
        )
    return incidents