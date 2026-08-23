"""Small persistent tabular Q-learning policy for seller strategy selection."""
import json
import random
from pathlib import Path
from typing import Any


ACTIONS = ("ACCEPT", "SMALL_COUNTER", "TARGET_COUNTER", "REJECT")
DEFAULT_Q_TABLE_PATH = Path(__file__).resolve().parents[1] / "merchant_q_table.json"


class MerchantPolicy:
    def __init__(self, path: str | Path = DEFAULT_Q_TABLE_PATH, learning_rate: float = 0.2, discount: float = 0.8, exploration: float = 0.15):
        self.path = Path(path)
        self.learning_rate = learning_rate
        self.discount = discount
        self.exploration = exploration
        self.q_table: dict[str, dict[str, float]] = {}
        self.metrics = {"before": {"negotiations": 0, "conversions": 0, "profit": 0.0, "accepted_price": 0.0}, "after": {"negotiations": 0, "conversions": 0, "profit": 0.0, "accepted_price": 0.0}}
        self._load()

    def state_key(self, sku: str, inventory: int, buyer_offer: float | None, buyer_max_price: float, margin: float, round_number: int) -> str:
        return json.dumps([sku, inventory, self._bucket(buyer_offer), self._bucket(buyer_max_price), round(margin, 2), round_number], separators=(",", ":"))

    def select_action(self, state: str, allowed_actions: tuple[str, ...] = ACTIONS) -> str:
        self._ensure_state(state)
        row = self.q_table[state]
        if random.random() < self.exploration:
            return random.choice(allowed_actions)
        if not row or all(value == 0 for value in row.values()):
            return "TARGET_COUNTER"
        return max(allowed_actions, key=lambda action: (row.get(action, 0.0), -allowed_actions.index(action)))

    @property
    def has_learning(self) -> bool:
        return any(any(value != 0 for value in row.values()) for row in self.q_table.values())

    def update(self, state: str, action: str, reward: float, next_state: str | None = None) -> None:
        self._ensure_state(state)
        next_best = max(self.q_table.get(next_state, {}).values(), default=0.0) if next_state else 0.0
        old_value = self.q_table[state][action]
        self.q_table[state][action] = round(old_value + self.learning_rate * (reward + self.discount * next_best - old_value), 6)
        self._save()

    def record_episode(self, learned: bool, converted: bool, profit: float, accepted_price: float | None) -> None:
        bucket = self.metrics["after" if learned else "before"]
        bucket["negotiations"] += 1
        bucket["conversions"] += int(converted)
        bucket["profit"] = round(bucket["profit"] + (profit if converted else 0.0), 2)
        bucket["accepted_price"] = round(bucket["accepted_price"] + (accepted_price if converted and accepted_price is not None else 0.0), 2)
        self._save()

    def metric_summary(self) -> dict[str, dict[str, float]]:
        summary: dict[str, dict[str, float]] = {}
        for phase, values in self.metrics.items():
            count = values["negotiations"]
            conversions = values["conversions"]
            summary[phase] = {
                "conversion_rate": round(conversions / count, 4) if count else 0.0,
                "average_profit": round(values["profit"] / count, 2) if count else 0.0,
                "average_accepted_price": round(values["accepted_price"] / conversions, 2) if conversions else 0.0,
                "negotiations": count,
            }
        return summary

    def _ensure_state(self, state: str) -> None:
        self.q_table.setdefault(state, {action: 0.0 for action in ACTIONS})

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.q_table = data.get("q_table", {})
            self.metrics.update(data.get("metrics", {}))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self.q_table = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"q_table": self.q_table, "metrics": self.metrics}, indent=2), encoding="utf-8")

    @staticmethod
    def _bucket(value: float | None) -> float | None:
        return round(value / 10) * 10 if value is not None else None


def reward_for_episode(converted: bool, profit: float, margin: float, rejected: bool) -> float:
    if not converted:
        return -2.0 if rejected else -1.0
    reward = 2.0 + max(0.0, profit) / 10.0 + max(0.0, margin) * 5.0
    return round(reward, 4)
