from collections import deque
from dataclasses import dataclass
from math import isfinite
from typing import Deque


@dataclass(frozen=True)
class Swing:
    index: int
    price: float


class MarketStructure:
    def __init__(
        self,
        left_bars: int = 2,
        right_bars: int = 2,
        max_swings: int = 20
    ):
        for name, value in (
            ("left_bars", left_bars),
            ("right_bars", right_bars),
            ("max_swings", max_swings)
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                raise ValueError(
                    f"{name} must be a positive integer"
                )

        self.left_bars = left_bars
        self.right_bars = right_bars

        self.bars = deque(
            maxlen=left_bars + right_bars + 1
        )

        self.high_swings: Deque[Swing] = deque(
            maxlen=max_swings
        )

        self.low_swings: Deque[Swing] = deque(
            maxlen=max_swings
        )

        self.index = -1

    def add(self, high: float, low: float) -> dict:
        self.index += 1

        self.bars.append(
            (self.index, high, low)
        )

        if len(self.bars) == self.bars.maxlen:
            values = list(self.bars)

            candidate = values[self.left_bars]

            candidate_index = candidate[0]
            candidate_high = candidate[1]
            candidate_low = candidate[2]

            left = values[:self.left_bars]

            right = values[self.left_bars + 1:]

            is_swing_high = (
                all(candidate_high > item[1] for item in left)
                and all(candidate_high >= item[1] for item in right)
            )

            is_swing_low = (
                all(candidate_low < item[2] for item in left)
                and all(candidate_low <= item[2] for item in right)
            )

            if is_swing_high:
                self.high_swings.append(
                    Swing(candidate_index, candidate_high)
                )

            if is_swing_low:
                self.low_swings.append(
                    Swing(candidate_index, candidate_low)
                )

        highs = list(self.high_swings)
        lows = list(self.low_swings)

        higher_highs = (
            len(highs) >= 2
            and highs[-1].price > highs[-2].price
        )

        higher_lows = (
            len(lows) >= 2
            and lows[-1].price > lows[-2].price
        )

        lower_highs = (
            len(highs) >= 2
            and highs[-1].price < highs[-2].price
        )

        lower_lows = (
            len(lows) >= 2
            and lows[-1].price < lows[-2].price
        )

        bullish = higher_highs and higher_lows
        bearish = lower_highs and lower_lows

        return {
            "bullish_structure": bullish,
            "bearish_structure": bearish,
            "higher_high": higher_highs,
            "higher_low": higher_lows,
            "lower_high": lower_highs,
            "lower_low": lower_lows,
            "last_swing_high": (
                highs[-1].price if highs else None
            ),
            "previous_swing_high": (
                highs[-2].price if len(highs) >= 2 else None
            ),
            "last_swing_low": (
                lows[-1].price if lows else None
            ),
            "previous_swing_low": (
                lows[-2].price if len(lows) >= 2 else None
            ),
            "confirmed_swing_highs": len(highs),
            "confirmed_swing_lows": len(lows),
        }


class SidewaysRangeDetector:
    def __init__(
        self,
        lookback: int = 20,
        min_bars: int = 15,
        min_touches: int = 2,
        max_range_pct: float = 0.02,
        touch_tolerance_pct: float = 0.15
    ):
        if (
            isinstance(lookback, bool)
            or not isinstance(lookback, int)
            or lookback < 3
        ):
            raise ValueError(
                "lookback must be an integer of at least 3"
            )

        if (
            isinstance(min_bars, bool)
            or not isinstance(min_bars, int)
            or not 3 <= min_bars <= lookback
        ):
            raise ValueError(
                "min_bars must be between 3 and lookback"
            )

        if (
            isinstance(min_touches, bool)
            or not isinstance(min_touches, int)
            or min_touches < 1
        ):
            raise ValueError(
                "min_touches must be a positive integer"
            )

        if not isfinite(max_range_pct) or max_range_pct <= 0:
            raise ValueError(
                "max_range_pct must be finite and positive"
            )

        if (
            not isfinite(touch_tolerance_pct)
            or not 0 < touch_tolerance_pct <= 0.5
        ):
            raise ValueError(
                "touch_tolerance_pct must be in (0, 0.5]"
            )

        self.lookback = lookback
        self.min_bars = min_bars
        self.min_touches = min_touches
        self.max_range_pct = max_range_pct
        self.touch_tolerance_pct = touch_tolerance_pct

        self.window = deque(maxlen=lookback)

    def add(
        self,
        high: float,
        low: float,
        close: float
    ) -> dict:

        previous = list(self.window)

        prior_high = max(
            (item[0] for item in previous),
            default=None
        )

        prior_low = min(
            (item[1] for item in previous),
            default=None
        )

        prior_ready = len(previous) >= self.min_bars

        prior_width = (
            prior_high - prior_low
            if prior_ready else None
        )

        prior_tolerance = (
            prior_width * self.touch_tolerance_pct
            if prior_ready else None
        )

        close_inside_prior_range = (
            prior_ready
            and prior_low <= close <= prior_high
        )

        self.window.append((high, low, close))

        if len(self.window) < self.min_bars:
            return self._result(
                False, None, None, 0, 0, None
            )

        range_high = max(
            item[0] for item in self.window
        )

        range_low = min(
            item[1] for item in self.window
        )

        midpoint = (range_high + range_low) / 2.0

        width = range_high - range_low

        if midpoint <= 0 or width <= 0:
            return self._result(
                False,
                range_high,
                range_low,
                0,
                0,
                None
            )

        range_pct = width / midpoint

        tolerance = width * self.touch_tolerance_pct

        top_flags = [
            item[0] >= range_high - tolerance
            for item in self.window
        ]

        bottom_flags = [
            item[1] <= range_low + tolerance
            for item in self.window
        ]

        top_touches = sum(
            1
            for i, flag in enumerate(top_flags)
            if flag and (i == 0 or not top_flags[i - 1])
        )

        bottom_touches = sum(
            1
            for i, flag in enumerate(bottom_flags)
            if flag and (i == 0 or not bottom_flags[i - 1])
        )

        no_breakout = (
            prior_ready
            and prior_tolerance is not None
            and close >= prior_low - prior_tolerance
            and close <= prior_high + prior_tolerance
        )

        is_sideways = (
            range_pct <= self.max_range_pct
            and top_touches >= self.min_touches
            and bottom_touches >= self.min_touches
            and close_inside_prior_range
            and no_breakout
        )

        return self._result(
            is_sideways,
            range_high,
            range_low,
            top_touches,
            bottom_touches,
            range_pct
        )

    @staticmethod
    def _result(
        sideways,
        range_high,
        range_low,
        top_touches,
        bottom_touches,
        range_pct
    ):
        return {
            "sideways": sideways,
            "range_high": range_high,
            "range_low": range_low,
            "top_touches": top_touches,
            "bottom_touches": bottom_touches,
            "range_pct": range_pct,
        }
