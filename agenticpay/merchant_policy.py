"""Persistent tabular Q-learning policy for merchant negotiation strategy."""

import json
import random
from pathlib import Path
from typing import Optional


ACTIONS = (
    "ACCEPT",
    "SMALL_COUNTER",
    "TARGET_COUNTER",
    "REJECT",
)

DEFAULT_Q_TABLE_PATH = (
    Path(__file__).resolve().parents[1] / "merchant_q_table.json"
)


class MerchantPolicy:

    def __init__(
        self,
        path: str | Path = DEFAULT_Q_TABLE_PATH,
        learning_rate: float = 0.2,
        discount: float = 0.8,
        exploration: float = 0.15,
    ):
        self.path = Path(path)
        self.learning_rate = learning_rate
        self.discount = discount
        self.exploration = exploration

        self.q_table: dict[str, dict[str, float]] = {}

        self.metrics = {
            "before": {
                "negotiations": 0,
                "conversions": 0,
                "profit": 0.0,
                "accepted_price": 0.0,
            },
            "after": {
                "negotiations": 0,
                "conversions": 0,
                "profit": 0.0,
                "accepted_price": 0.0,
            },
        }

        self._load()


    def state_key(
        self,
        sku: str,
        inventory: int,
        buyer_offer: Optional[float],
        buyer_max_price: float,
        margin: float,
        round_number: int,
        clv_score: Optional[float] = None,
    ) -> str:

        state = [
            sku,
            inventory,
            self._bucket(buyer_offer),
            self._bucket(buyer_max_price),
            round(margin, 2),
            round_number,
        ]

        # CVO OFF:
        # No CLV component is added.
        #
        # CVO ON:
        # Customer value becomes an additional state feature.
        if clv_score is not None:
            state.append(self._bucket(clv_score))

        return json.dumps(
            state,
            separators=(",", ":"),
        )



    def select_action(
        self,
        state: str,
        allowed_actions: tuple[str, ...] = ACTIONS,
    ) -> str:

        self._ensure_state(state)

        row = self.q_table[state]

        # Exploration remains 0.15 as requested.
        if self.exploration > 0 and random.random() < self.exploration:
            return random.choice(allowed_actions)

        # Unseen state.
        if not any(
            row.get(action, 0.0) != 0.0
            for action in allowed_actions
        ):
            return "TARGET_COUNTER"

        # Deterministic exploitation.
        #
        # ACCEPT > SMALL_COUNTER > TARGET_COUNTER > REJECT
        # only matters when Q-values tie.
        priority = {
            "ACCEPT": 0,
            "SMALL_COUNTER": 1,
            "TARGET_COUNTER": 2,
            "REJECT": 3,
        }

        return max(
            allowed_actions,
            key=lambda action: (
                row.get(action, 0.0),
                -priority.get(action, 99),
            ),
        )

    @property
    def has_learning(self) -> bool:
        return any(
            any(value != 0 for value in row.values())
            for row in self.q_table.values()
        )



    def update(
        self,
        state: str,
        action: str,
        reward: float,
        next_state: Optional[str] = None,
    ) -> None:

        self._ensure_state(state)

        next_best = 0.0

        if next_state is not None:
            next_row = self.q_table.get(next_state)

            if next_row:
                next_best = max(
                    next_row.values(),
                    default=0.0,
                )

        old_value = self.q_table[state][action]

        new_value = (
            old_value
            + self.learning_rate
            * (
                reward
                + self.discount * next_best
                - old_value
            )
        )

        self.q_table[state][action] = round(
            new_value,
            6,
        )

        self._save()


    def record_episode(
        self,
        learned: bool,
        converted: bool,
        profit: float,
        accepted_price: Optional[float],
    ) -> None:

        bucket = self.metrics[
            "after" if learned else "before"
        ]

        bucket["negotiations"] += 1
        bucket["conversions"] += int(converted)

        if converted:
            bucket["profit"] = round(
                bucket["profit"] + profit,
                2,
            )

            if accepted_price is not None:
                bucket["accepted_price"] = round(
                    bucket["accepted_price"] + accepted_price,
                    2,
                )

        self._save()

    def metric_summary(self) -> dict[str, dict[str, float]]:

        summary = {}

        for phase, values in self.metrics.items():

            negotiations = values["negotiations"]
            conversions = values["conversions"]

            summary[phase] = {
                "conversion_rate": (
                    round(
                        conversions / negotiations,
                        4,
                    )
                    if negotiations
                    else 0.0
                ),
                "average_profit": (
                    round(
                        values["profit"] / negotiations,
                        2,
                    )
                    if negotiations
                    else 0.0
                ),
                "average_accepted_price": (
                    round(
                        values["accepted_price"] / conversions,
                        2,
                    )
                    if conversions
                    else 0.0
                ),
                "negotiations": negotiations,
            }

        return summary

   

    def _ensure_state(self, state: str) -> None:

        self.q_table.setdefault(
            state,
            {
                action: 0.0
                for action in ACTIONS
            },
        )

    def _load(self) -> None:

        if not self.path.exists():
            return

        try:
            data = json.loads(
                self.path.read_text(
                    encoding="utf-8",
                )
            )

            self.q_table = data.get(
                "q_table",
                {},
            )

            saved_metrics = data.get(
                "metrics",
                {},
            )

            for phase in ("before", "after"):
                if phase in saved_metrics:
                    self.metrics[phase].update(
                        saved_metrics[phase]
                    )

        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            self.q_table = {}

    def _save(self) -> None:

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path.write_text(
            json.dumps(
                {
                    "q_table": self.q_table,
                    "metrics": self.metrics,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

   

    @staticmethod
    def _bucket(
        value: Optional[float],
    ) -> Optional[float]:

        if value is None:
            return None

        return round(value / 10) * 10



def reward_for_episode(
    converted: bool,
    profit: float,
    margin: float,
    rejected: bool,
) -> float:

    if not converted:
        return -2.0 if rejected else -1.0

    reward = (
        2.0
        + max(0.0, profit) / 10.0
        + max(0.0, margin) * 5.0
    )

    return round(reward, 4)