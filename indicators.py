from collections import deque
from math import isfinite
from typing import Deque, Optional


class SMAStream:
    def __init__(self, period: int):
        if isinstance(period, bool) or not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")

        self.period = period
        self.window: Deque[float] = deque()
        self.running_sum = 0.0

    def add(self, value: float) -> Optional[float]:
        value = float(value)

        if not isfinite(value):
            raise ValueError("value must be finite")

        self.window.append(value)
        self.running_sum += value

        if len(self.window) > self.period:
            self.running_sum -= self.window.popleft()

        if len(self.window) < self.period:
            return None

        return self.running_sum / self.period

    def get_current(self) -> Optional[float]:
        if len(self.window) < self.period:
            return None

        return self.running_sum / self.period

    @property
    def ready(self) -> bool:
        return len(self.window) >= self.period


class MovingAverageSet:
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        slope_period: int = 5
    ):
        if fast_period >= slow_period:
            raise ValueError(
                "fast_period must be smaller than slow_period"
            )

        if (
            isinstance(slope_period, bool)
            or not isinstance(slope_period, int)
            or slope_period < 1
        ):
            raise ValueError(
                "slope_period must be a positive integer"
            )

        self.fast = SMAStream(fast_period)
        self.slow = SMAStream(slow_period)

        self.fast_history: Deque[float] = deque(
            maxlen=slope_period + 1
        )

        self.slope_period = slope_period

    def add(self, close: float) -> dict:
        fast_value = self.fast.add(close)
        slow_value = self.slow.add(close)

        if fast_value is not None:
            self.fast_history.append(fast_value)

        fast_slope = None

        if len(self.fast_history) > self.slope_period:
            fast_slope = fast_value - self.fast_history[0]

        return {
            "ma20": fast_value,
            "ma50": slow_value,
            "ma20_slope": fast_slope,
            "ready": (
                fast_value is not None
                and slow_value is not None
            ),
        }
