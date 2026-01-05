"""
Preference Learner

Implements "Memory with Judgment" from the END GOAL.

The system remembers:
- What you care about
- What you consider risky
- What you usually approve
- What annoys you
- What "good enough" means

And acts differently over time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json


@dataclass
class UserPreference:
    """A learned user preference."""
    category: str
    key: str
    value: Any
    confidence: float  # 0.0 to 1.0
    learned_from: List[str]  # Evidence for this preference
    last_updated: datetime


@dataclass
class ApprovalPattern:
    """Pattern of what user approves/denies."""
    action_type: str
    context_pattern: str
    approved_count: int = 0
    denied_count: int = 0
    last_seen: Optional[datetime] = None


class PreferenceLearner:
    """
    Learns user preferences over time.

    Per END GOAL:
    - Remembers what you care about
    - Remembers what you consider risky
    - Remembers what you usually approve
    - Remembers what annoys you
    - Remembers what "good enough" means
    """

    def __init__(self, storage_path: str = "state/preferences.json"):
        self.storage_path = Path(storage_path)
        self.preferences: Dict[str, UserPreference] = {}
        self.approval_patterns: Dict[str, ApprovalPattern] = {}
        self.feedback_history: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load learned preferences."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))

                for pref_data in data.get("preferences", []):
                    pref = UserPreference(
                        category=pref_data["category"],
                        key=pref_data["key"],
                        value=pref_data["value"],
                        confidence=pref_data["confidence"],
                        learned_from=pref_data.get("learned_from", []),
                        last_updated=datetime.fromisoformat(pref_data["last_updated"]),
                    )
                    self.preferences[f"{pref.category}:{pref.key}"] = pref

                for pattern_data in data.get("approval_patterns", []):
                    pattern = ApprovalPattern(
                        action_type=pattern_data["action_type"],
                        context_pattern=pattern_data["context_pattern"],
                        approved_count=pattern_data.get("approved_count", 0),
                        denied_count=pattern_data.get("denied_count", 0),
                    )
                    key = f"{pattern.action_type}:{pattern.context_pattern}"
                    self.approval_patterns[key] = pattern

                self.feedback_history = data.get("feedback_history", [])[-100:]

            except Exception:
                pass

    def _save(self):
        """Save learned preferences."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "updated_at": datetime.now().isoformat(),
            "preferences": [
                {
                    "category": p.category,
                    "key": p.key,
                    "value": p.value,
                    "confidence": p.confidence,
                    "learned_from": p.learned_from[-10:],  # Keep last 10 evidence
                    "last_updated": p.last_updated.isoformat(),
                }
                for p in self.preferences.values()
            ],
            "approval_patterns": [
                {
                    "action_type": p.action_type,
                    "context_pattern": p.context_pattern,
                    "approved_count": p.approved_count,
                    "denied_count": p.denied_count,
                }
                for p in self.approval_patterns.values()
            ],
            "feedback_history": self.feedback_history[-100:],
        }

        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Learning methods

    def learn_from_approval(
        self,
        action_type: str,
        context: str,
        approved: bool,
        details: Optional[str] = None
    ):
        """Learn from user approval/denial."""
        key = f"{action_type}:{context}"

        if key not in self.approval_patterns:
            self.approval_patterns[key] = ApprovalPattern(
                action_type=action_type,
                context_pattern=context,
            )

        pattern = self.approval_patterns[key]
        if approved:
            pattern.approved_count += 1
        else:
            pattern.denied_count += 1
        pattern.last_seen = datetime.now()

        # Update feedback history
        self.feedback_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "approval",
            "action_type": action_type,
            "context": context,
            "approved": approved,
            "details": details,
        })

        self._save()

    def learn_from_feedback(
        self,
        category: str,
        feedback: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Learn from explicit or implicit feedback.

        Categories:
        - risk: What user considers risky
        - annoyance: What annoys the user
        - quality: What "good enough" means
        - priority: What user cares about
        """
        # Analyze feedback for preference signals
        signals = self._analyze_feedback(feedback)

        for key, value in signals.items():
            pref_key = f"{category}:{key}"

            if pref_key in self.preferences:
                pref = self.preferences[pref_key]
                # Reinforce or update
                pref.learned_from.append(feedback[:100])
                pref.confidence = min(1.0, pref.confidence + 0.1)
                pref.last_updated = datetime.now()
            else:
                self.preferences[pref_key] = UserPreference(
                    category=category,
                    key=key,
                    value=value,
                    confidence=0.5,
                    learned_from=[feedback[:100]],
                    last_updated=datetime.now(),
                )

        self.feedback_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "feedback",
            "category": category,
            "feedback": feedback[:200],
            "context": context,
        })

        self._save()

    def learn_from_correction(
        self,
        what_was_wrong: str,
        what_was_expected: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Learn from user corrections."""
        # This is high-signal feedback
        self.feedback_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "correction",
            "wrong": what_was_wrong[:200],
            "expected": what_was_expected[:200],
            "context": context,
        })

        # Analyze and extract preference
        if "too much" in what_was_wrong.lower():
            self._update_preference("verbosity", "verbose", False)
        if "not enough" in what_was_wrong.lower():
            self._update_preference("verbosity", "verbose", True)
        if "too slow" in what_was_wrong.lower():
            self._update_preference("speed", "prefer_speed", True)
        if "too risky" in what_was_wrong.lower():
            self._update_preference("risk", "tolerance", "low")
        if "ask less" in what_was_wrong.lower():
            self._update_preference("autonomy", "auto_approve", True)
        if "ask more" in what_was_wrong.lower() or "should have asked" in what_was_wrong.lower():
            self._update_preference("autonomy", "auto_approve", False)

        self._save()

    def _update_preference(self, category: str, key: str, value: Any):
        """Update or create a preference."""
        pref_key = f"{category}:{key}"

        if pref_key in self.preferences:
            pref = self.preferences[pref_key]
            pref.value = value
            pref.confidence = min(1.0, pref.confidence + 0.15)
            pref.last_updated = datetime.now()
        else:
            self.preferences[pref_key] = UserPreference(
                category=category,
                key=key,
                value=value,
                confidence=0.6,
                learned_from=["direct correction"],
                last_updated=datetime.now(),
            )

    def _analyze_feedback(self, feedback: str) -> Dict[str, Any]:
        """Analyze feedback text for preference signals."""
        signals = {}
        feedback_lower = feedback.lower()

        # Risk signals
        if any(w in feedback_lower for w in ["risky", "dangerous", "careful", "worried"]):
            signals["high_risk_aversion"] = True
        if any(w in feedback_lower for w in ["fine", "go ahead", "trust you", "your call"]):
            signals["low_risk_aversion"] = True

        # Verbosity signals
        if any(w in feedback_lower for w in ["too long", "verbose", "tldr", "shorter"]):
            signals["prefer_brief"] = True
        if any(w in feedback_lower for w in ["more detail", "explain", "elaborate"]):
            signals["prefer_detailed"] = True

        # Autonomy signals
        if any(w in feedback_lower for w in ["stop asking", "just do it", "figure it out"]):
            signals["prefer_autonomous"] = True
        if any(w in feedback_lower for w in ["check with me", "confirm first", "ask before"]):
            signals["prefer_confirmation"] = True

        return signals

    # Query methods

    def get_preference(self, category: str, key: str, default: Any = None) -> Any:
        """Get a learned preference."""
        pref_key = f"{category}:{key}"
        pref = self.preferences.get(pref_key)
        if pref and pref.confidence > 0.4:
            return pref.value
        return default

    def should_auto_approve(self, action_type: str, context: str) -> Tuple[bool, float]:
        """
        Determine if an action should be auto-approved based on history.

        Returns (should_approve, confidence)
        """
        key = f"{action_type}:{context}"
        pattern = self.approval_patterns.get(key)

        if not pattern:
            # No history, check general autonomy preference
            auto_approve = self.get_preference("autonomy", "auto_approve", None)
            if auto_approve is True:
                return True, 0.5
            return False, 0.0

        total = pattern.approved_count + pattern.denied_count
        if total < 3:
            return False, 0.3  # Not enough data

        approval_rate = pattern.approved_count / total
        confidence = min(0.95, 0.5 + (total * 0.05))  # More data = more confidence

        return approval_rate > 0.7, confidence

    def get_risk_tolerance(self) -> str:
        """Get user's risk tolerance level."""
        if self.get_preference("risk", "high_risk_aversion", False):
            return "low"
        if self.get_preference("risk", "low_risk_aversion", False):
            return "high"

        tolerance = self.get_preference("risk", "tolerance", "medium")
        return tolerance

    def get_communication_style(self) -> Dict[str, Any]:
        """Get preferred communication style."""
        return {
            "verbose": not self.get_preference("verbosity", "prefer_brief", False),
            "detailed": self.get_preference("verbosity", "prefer_detailed", False),
            "autonomous": self.get_preference("autonomy", "prefer_autonomous", True),
        }

    def what_annoys_user(self) -> List[str]:
        """Get list of things that annoy the user."""
        annoyances = []
        for key, pref in self.preferences.items():
            if pref.category == "annoyance" and pref.confidence > 0.5:
                annoyances.append(pref.key)
        return annoyances

    def what_user_cares_about(self) -> List[str]:
        """Get list of things the user cares about."""
        priorities = []
        for key, pref in self.preferences.items():
            if pref.category == "priority" and pref.confidence > 0.5:
                priorities.append(pref.key)
        return priorities

    def export_for_context(self) -> Dict[str, Any]:
        """Export preferences for inclusion in Claude's context."""
        return {
            "risk_tolerance": self.get_risk_tolerance(),
            "communication_style": self.get_communication_style(),
            "annoyances": self.what_annoys_user(),
            "priorities": self.what_user_cares_about(),
            "auto_approve_patterns": [
                {
                    "action": p.action_type,
                    "context": p.context_pattern,
                    "approval_rate": p.approved_count / max(1, p.approved_count + p.denied_count),
                }
                for p in self.approval_patterns.values()
                if p.approved_count + p.denied_count >= 3
            ][:10],  # Top 10 patterns
        }
