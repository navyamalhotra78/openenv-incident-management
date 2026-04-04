"""
Graders for Task 4 lifecycle stages.
Each grader takes an Action and an Incident and returns (score: float, feedback: str).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.incident import Incident
    from models.action import Action


class IncidentGrader:

    @staticmethod
    def grade_triage(action: "Action", incident: "Incident") -> tuple[float, str]:
        """
        Did the agent correctly classify severity and assign the right team?
        Severity is visible in the observation; team must be inferred from logs/metrics.
        """
        severity_correct = (action.severity or "").lower() == incident.severity.lower()
        team_correct     = (action.team or "").lower() == (incident.true_team or "").lower()

        score = 0.0
        parts = []

        if severity_correct:
            score += 0.5
            parts.append("severity ✓")
        else:
            parts.append(
                f"severity ✗ (got {action.severity!r}, want {incident.severity!r})"
            )

        if team_correct:
            score += 0.5
            parts.append("team ✓")
        else:
            parts.append(
                f"team ✗ (got {action.team!r}, want {incident.true_team!r})"
            )

        return round(score, 3), " | ".join(parts)

    @staticmethod
    def grade_root_cause(action: "Action", incident: "Incident") -> tuple[float, str]:
        """
        Did the agent identify the correct root cause from logs and metrics?
        Accepts exact matches and partial string matches.
        """
        guessed = (action.root_cause or "").lower().replace(" ", "_").strip()
        actual  = (incident.true_root_cause or "").lower().strip()

        if not guessed:
            return 0.0, "no root_cause provided"

        if guessed == actual:
            return 1.0, f"root cause ✓ exact: {actual}"
        elif actual in guessed or guessed in actual:
            return 0.7, f"root cause ~ partial match: got {guessed!r}, want {actual!r}"
        else:
            return 0.0, f"root cause ✗: got {guessed!r}, want {actual!r}"

    @staticmethod
    def grade_remediation(action: "Action", incident: "Incident") -> tuple[float, str]:
        """
        Did the agent apply valid fixes in the correct order?
        - validity_score: fraction of submitted fixes that are valid
        - order_score:    0.5 × correct_ordering + 0.5 × coverage of required steps
        - total:          0.6 × validity + 0.4 × order
        """
        submitted = [f.lower().replace(" ", "_").strip() for f in (action.fixes or [])]
        valid     = [f.lower() for f in incident.valid_fixes]
        required  = [f.lower() for f in incident.required_fix_order]

        if not submitted:
            return 0.0, "no fixes provided"

        validity_score = sum(1 for f in submitted if f in valid) / max(len(submitted), 1)

        # Check required steps are present and in correct relative order
        in_required = [f for f in submitted if f in required]
        order_score = 0.0
        if in_required:
            correct_order = all(
                required.index(in_required[i]) < required.index(in_required[i + 1])
                for i in range(len(in_required) - 1)
            )
            coverage = len(set(in_required) & set(required)) / len(required)
            order_score = 0.5 * (1.0 if correct_order else 0.0) + 0.5 * coverage

        total = round(0.6 * validity_score + 0.4 * order_score, 3)
        return total, (
            f"validity={validity_score:.2f} order={order_score:.2f} "
            f"submitted={submitted}"
        )

    @staticmethod
    def grade_postmortem(action: "Action", incident: "Incident") -> tuple[float, str]:
        """
        Does the post-mortem text cover the four required sections?
        - Root cause mentioned       → 0.30
        - ≥2 prevention steps hit    → 0.40
        - Timeline present           → 0.20
        - Action items present       → 0.10
        """
        text = (action.postmortem or "").lower()
        score = 0.0
        parts = []

        # Root cause
        rc_keywords = (incident.true_root_cause or "").replace("_", " ").split()
        if any(kw in text for kw in rc_keywords):
            score += 0.30
            parts.append("root_cause ✓")
        else:
            parts.append("root_cause ✗")

        # Prevention steps (need ≥2 out of expected)
        hits = sum(
            1 for step in incident.prevention_steps
            if any(word in text for word in step.lower().split() if len(word) > 4)
        )
        prevention_score = min(hits / 2.0, 1.0) * 0.40
        score += prevention_score
        parts.append(
            f"prevention={hits}/{len(incident.prevention_steps)} ✓"
            if hits >= 2 else "prevention ✗"
        )

        # Timeline
        if any(t in text for t in ["timeline", "00:", "am", "pm", "utc", "minutes", "hours"]):
            score += 0.20
            parts.append("timeline ✓")
        else:
            parts.append("timeline ✗")

        # Action items
        if any(t in text for t in ["action item", "todo", "follow-up", "ticket", "jira", "will be", "should be"]):
            score += 0.10
            parts.append("action_items ✓")
        else:
            parts.append("action_items ✗")

        return round(score, 3), " | ".join(parts)


# Singleton
grader = IncidentGrader()
