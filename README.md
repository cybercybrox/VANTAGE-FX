# VANTAGE-FX
# Market Brain

A streaming market-regime detection engine.

## Requirements

Python 3.9 or newer.

No external dependencies.

## Import

from market_brain import MarketBrain, Candle

## Initialize

brain = MarketBrain()

## Process a real candle

snapshot = brain.add_candle(
    Candle(
        high=actual_high,
        low=actual_low,
        close=actual_close
    )
)

## Read the result

result = snapshot.to_dict()

print(result)

## Supported market states

BULLISH
BEARISH
SIDEWAYS
UNKNOWN

## Decision requirements

BULLISH:
- Higher highs
- Higher lows
- Close above MA20
- MA20 above MA50
- Positive MA20 slope

BEARISH:
- Lower highs
- Lower lows
- Close below MA20
- MA20 below MA50
- Negative MA20 slope

SIDEWAYS:
- Compact price range
- Repeated range boundary tests
- Compressed moving averages
- No confirmed directional structure

UNKNOWN:
- Insufficient evidence
- Conflicting confirmations
- Unconfirmed market structure

## Important

Feed completed real candles in chronological order.

Do not repeatedly submit the same candle.

This engine does not fetch market data or execute trades. 
