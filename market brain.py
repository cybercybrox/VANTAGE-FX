from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from typing import Optional, Union

from .indicators import MovingAverageSet
from .structure import MarketStructure, SidewaysRangeDetector


class MarketState(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Candle:
    high: float
    low: float
    close: float

    def __post_init__(self):
        values = (self.high, self.low, self.close)

        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            for value in values
        ):
            raise TypeError(
                "high, low and close must be numeric"
            )

        if any(
            not isfinite(float(value))
            for value in values
        ):
            raise ValueError(
                "candle values must be finite"
            )

        if self.high < self.low:
            raise ValueError(
                "high cannot be below low"
            )

        if not self.low <= self.close <= self.high:
            raise ValueError(
                "close must be between high and low"
            )

        if self.low < 0:
            raise ValueError(
                "prices cannot be negative"
            )


@dataclass(frozen=True)
class MarketBrainConfig:
    fast_ma_period: int = 20
    slow_ma_period: int = 50
    ma_slope_period: int = 5

    swing_left_bars: int = 2
    swing_right_bars: int = 2

    sideways_lookback: int = 20
    sideways_min_bars: int = 15
    sideways_min_touches: int = 2

    sideways_max_range_pct: float = 0.02
    sideways_touch_tolerance_pct: float = 0.15

    ma_compression_pct: float = 0.002

    def __post_init__(self):
        if (
            self.fast_ma_period < 1
            or self.slow_ma_period <= self.fast_ma_period
        ):
            raise ValueError(
                "moving-average periods must be positive "
                "and fast must be smaller than slow"
            )

        if self.ma_slope_period < 1:
            raise ValueError(
                "ma_slope_period must be positive"
            )

        if (
            self.ma_compression_pct <= 0
            or not isfinite(self.ma_compression_pct)
        ):
            raise ValueError(
                "ma_compression_pct must be finite and positive"
            )


@dataclass(frozen=True)
class MarketSnapshot:
    state: MarketState
    confidence: str
    reason: str

    candle_count: int
    close: float

    ma20: Optional[float]
    ma50: Optional[float]
    ma20_slope: Optional[float]

    ma_alignment: str

    structure: dict
    range_data: dict
    confirmations: dict

    def to_dict(self) -> dict:
        result = asdict(self)

        result["state"] = self.state.value

        return result


class MarketBrain:

    def __init__(
        self,
        config: Optional[MarketBrainConfig] = None
    ):
        self.config = config or MarketBrainConfig()

        self.moving_averages = MovingAverageSet(
            self.config.fast_ma_period,
            self.config.slow_ma_period,
            self.config.ma_slope_period
        )

        self.structure_detector = MarketStructure(
            self.config.swing_left_bars,
            self.config.swing_right_bars
        )

        self.sideways_detector = SidewaysRangeDetector(
            self.config.sideways_lookback,
            self.config.sideways_min_bars,
            self.config.sideways_min_touches,
            self.config.sideways_max_range_pct,
            self.config.sideways_touch_tolerance_pct
        )

        self.candle_count = 0
        self.last_snapshot = None

    def add_candle(
        self,
        candle: Union[Candle, dict]
    ) -> MarketSnapshot:

        if isinstance(candle, dict):
            try:
                candle = Candle(
                    high=candle["high"],
                    low=candle["low"],
                    close=candle["close"]
                )

            except KeyError as exc:
                raise ValueError(
                    f"missing candle field: {exc.args[0]}"
                ) from exc

        elif not isinstance(candle, Candle):
            raise TypeError(
                "candle must be a Candle or a dictionary "
                "with high, low and close"
            )

        self.candle_count += 1

        ma = self.moving_averages.add(
            candle.close
        )

        structure = self.structure_detector.add(
            candle.high,
            candle.low
        )

        range_data = self.sideways_detector.add(
            candle.high,
            candle.low,
            candle.close
        )

        ready = ma["ready"]

        ma20 = ma["ma20"]
        ma50 = ma["ma50"]
        slope = ma["ma20_slope"]

        bullish_ma = (
            ready
            and candle.close > ma20
            and ma20 > ma50
            and slope is not None
            and slope > 0
        )

        bearish_ma = (
            ready
            and candle.close < ma20
            and ma20 < ma50
            and slope is not None
            and slope < 0
        )

        ma_alignment = "UNAVAILABLE"

        if ready:
            if ma20 > ma50:
                ma_alignment = "BULLISH"

            elif ma20 < ma50:
                ma_alignment = "BEARISH"

            else:
                ma_alignment = "NEUTRAL"

        ma_compressed = (
            ready
            and abs(ma20 - ma50) / candle.close
            <= self.config.ma_compression_pct
        )

        bullish_structure = structure[
            "bullish_structure"
        ]

        bearish_structure = structure[
            "bearish_structure"
        ]

        sideways = (
            range_data["sideways"]
            and ma_compressed
        )

        if bullish_structure and bullish_ma:

            state = MarketState.BULLISH

            confidence = "HIGH"

            reason = (
                "Higher highs and higher lows are confirmed, "
                "with bullish MA20/MA50 alignment "
                "and positive MA20 slope."
            )

        elif bearish_structure and bearish_ma:

            state = MarketState.BEARISH

            confidence = "HIGH"

            reason = (
                "Lower highs and lower lows are confirmed, "
                "with bearish MA20/MA50 alignment "
                "and negative MA20 slope."
            )

        elif (
            sideways
            and not bullish_structure
            and not bearish_structure
        ):

            state = MarketState.SIDEWAYS

            confidence = "MEDIUM"

            reason = (
                "Price is inside a compact range "
                "with repeated boundary tests "
                "and compressed moving averages."
            )

        else:

            state = MarketState.UNKNOWN

            confidence = "LOW"

            reason = self._unknown_reason(
                ready,
                structure,
                range_data,
                bullish_ma,
                bearish_ma,
                ma_compressed
            )

        confirmations = {
            "moving_averages_ready": ready,

            "bullish_ma_confirmation": bool(
                bullish_ma
            ),

            "bearish_ma_confirmation": bool(
                bearish_ma
            ),

            "ma_compressed": bool(
                ma_compressed
            ),

            "bullish_structure_confirmation": bool(
                bullish_structure
            ),

            "bearish_structure_confirmation": bool(
                bearish_structure
            ),

            "sideways_range_confirmation": bool(
                range_data["sideways"]
            )
        }

        snapshot = MarketSnapshot(
            state=state,
            confidence=confidence,
            reason=reason,

            candle_count=self.candle_count,
            close=float(candle.close),

            ma20=ma20,
            ma50=ma50,
            ma20_slope=slope,

            ma_alignment=ma_alignment,

            structure=structure,
            range_data=range_data,
            confirmations=confirmations
        )

        self.last_snapshot = snapshot

        return snapshot

    def add_candles(self, candles) -> list:
        return [
            self.add_candle(candle)
            for candle in candles
        ]

    def get_current(
        self
    ) -> Optional[MarketSnapshot]:

        return self.last_snapshot

    def reset(self) -> None:
        self.__init__(self.config)

    @staticmethod
    def _unknown_reason(
        ready,
        structure,
        range_data,
        bullish_ma,
        bearish_ma,
        ma_compressed
    ):

        if not ready:
            return (
                "Waiting for enough real candles "
                "to calculate both moving averages."
            )

        if (
            not structure["bullish_structure"]
            and not structure["bearish_structure"]
        ):

            if range_data["sideways"] and not ma_compressed:
                return (
                    "A compact price range is present, "
                    "but moving averages are not "
                    "sufficiently compressed."
                )

            return (
                "Confirmed higher-high/higher-low "
                "or lower-high/lower-low structure "
                "is not available."
            )

        if (
            structure["bullish_structure"]
            and not bullish_ma
        ):
            return (
                "Bullish structure exists, "
                "but moving-average confirmation "
                "is incomplete."
            )

        if (
            structure["bearish_structure"]
            and not bearish_ma
        ):
            return (
                "Bearish structure exists, "
                "but moving-average confirmation "
                "is incomplete."
            )

        if ma_compressed:
            return (
                "Moving averages are compressed "
                "and the market direction "
                "is not sufficiently clear."
            )

        return (
            "The available market evidence is mixed."
        )
