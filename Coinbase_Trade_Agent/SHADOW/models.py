from dataclasses import dataclass, asdict
from decimal import Decimal
import hashlib
import json

@dataclass(frozen=True)
class Candle:
    start: int
    seconds: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass(frozen=True)
class Book:
    product_id: str
    source_time: int
    fetched_at: int
    bids: tuple
    asks: tuple

@dataclass(frozen=True)
class FeeSnapshot:
    maker: Decimal
    taker: Decimal
    observed_at: int
    source: str

@dataclass(frozen=True)
class MarketSnapshot:
    product_id: str
    as_of: int
    candles: dict
    book: Book
    product: dict
    fees: FeeSnapshot

@dataclass(frozen=True)
class Candidate:
    signal_id: str
    product_id: str
    strategy_id: str
    rules_version: str
    bar_start: int
    entry: Decimal
    stop: Decimal
    target: Decimal
    expires_at: int
    primary_minutes: int
    score: int
    reasons: tuple

@dataclass(frozen=True)
class PaperEvent:
    event_id: str
    signal_id: str
    timestamp: int
    event_type: str
    payload: dict

def encode(value):
    if isinstance(value, Decimal): return str(value)
    if hasattr(value, '__dataclass_fields__'): return asdict(value)
    raise TypeError(type(value).__name__)

def dumps(value):
    return json.dumps(value, default=encode, sort_keys=True, allow_nan=False)

def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()
