"""
Data models and schemas for communication across the Forex Agent Swarm.
Upgraded with institutional safety contracts, market regime states, portfolio heat,
and immutable proposal hashes.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import uuid
import hashlib

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

class MarketRegime(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGE_BOUND = "RANGE_BOUND"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    COMPRESSION_SQUEEZE = "COMPRESSION_SQUEEZE"
    UNSTABLE = "UNSTABLE"

class EventImpact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class MacroState(str, Enum):
    PRE_EVENT = "PRE_EVENT"
    RELEASE = "RELEASE"
    POST_EVENT = "POST_EVENT"
    CLEAR = "CLEAR"

class OrderStatus(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"

# ----------------- Market Data -----------------
class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class MarketTick(BaseModel):
    pair: str
    bid: float
    ask: float
    timestamp: datetime = Field(default_factory=utc_now)
    spread_pips: float
    source: str = "ECN_FEED_PRIMARY"

# ----------------- Tier 0: Safety & Integrity -----------------
class DataHealthReport(BaseModel):
    agent_name: str = "Data Integrity Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    pair: str
    is_fresh: bool = True
    staleness_seconds: float = 0.0
    price_continuity_valid: bool = True
    feed_healthy: bool = True
    detected_anomalies: List[str] = Field(default_factory=list)
    rationale: str

class EmergencyHaltStatus(BaseModel):
    agent_name: str = "Emergency Halt Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    is_halted: bool = False
    halt_reason: Optional[str] = None
    kill_switch_triggered_by: Optional[str] = None
    consecutive_errors: int = 0

# ----------------- Tier 1: Perception & Regimes -----------------
class NewsSentimentReport(BaseModel):
    agent_name: str = "News & Sentiment Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    currency: str
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    source: str = "FINANCIAL_FEED"
    expiry_time: datetime = Field(default_factory=utc_now)
    is_narrative: bool = True
    contradiction_detected: bool = False
    key_headlines: List[str] = Field(default_factory=list)
    risk_on_off: str = "NEUTRAL"
    breaking_alert: bool = False
    rationale: str

class MacroEventReport(BaseModel):
    agent_name: str = "Macro & Calendar Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    event_name: str
    currency: str
    impact: EventImpact
    state: MacroState = MacroState.CLEAR
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    surprise_magnitude_std: float = 0.0
    lock_trading_window: bool = False
    size_reduction_pct: float = 0.0
    rationale: str

class MicrostructureReport(BaseModel):
    agent_name: str = "Microstructure & Order Flow Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    pair: str
    spread_pips: float
    spread_ratio: float = 1.0
    liquidity_score: float = Field(default=80.0, ge=0.0, le=100.0)
    friction_cost_usd: float = 0.0
    friction_penalty: float = 0.0
    is_tradable: bool = True
    quote_flicker_detected: bool = False
    rationale: str

class RegimeReport(BaseModel):
    agent_name: str = "Regime Classifier Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    pair: str
    regime: MarketRegime = MarketRegime.RANGE_BOUND
    adx: float = 20.0
    atr_percentile: float = 50.0
    trend_persistence_score: float = 0.5
    is_trending: bool = False
    is_squeezed: bool = False
    confidence: float = 0.70
    rationale: str

# ----------------- Tier 2: Technical & Quantitative -----------------
class TechnicalPatternReport(BaseModel):
    agent_name: str = "Pattern Recognition Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    pair: str
    bias: SignalDirection
    detected_patterns: List[str] = Field(default_factory=list)
    key_support: float
    key_resistance: float
    invalidation_level: float
    expected_holding_period_minutes: int = 45
    regime_aligned: bool = True
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str

class QuantIndicatorReport(BaseModel):
    agent_name: str = "Quant & Indicator Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    pair: str
    atr: float
    adx: float = 22.0
    rsi: float
    bollinger_upper: float
    bollinger_lower: float
    z_score: float
    csm_strength: float = 0.0
    realized_volatility_percentile: float = 50.0
    volatility_state: str = "NORMAL"
    bias: SignalDirection
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str

# ----------------- Tier 3: Decision & Portfolio Risk -----------------
class TradeProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=utc_now)
    pair: str
    direction: SignalDirection
    direction_bias: SignalDirection = SignalDirection.NEUTRAL
    approval_status: str = "PENDING"
    confluence_checklist: Dict[str, bool] = Field(default_factory=dict)
    contradiction_detected: bool = False
    optimal_expiry: str = "1M"
    binary_payout_pct: float = 87.0
    missing_conditions: List[str] = Field(default_factory=list)
    action_trigger: Optional[str] = None
    entry_type: str = "MARKET"
    entry_price: float
    target_stop_loss: float
    target_take_profit: float
    rrr: float
    composite_confidence: float
    regime: MarketRegime = MarketRegime.RANGE_BOUND
    valid_until: datetime = Field(default_factory=utc_now)
    invalidation_condition: str = "Structural invalidation price breached"
    component_scores: Dict[str, float] = Field(default_factory=dict)
    rationale: str
    rationale_hash: str = ""

    def freeze_and_hash(self):
        payload = f"{self.proposal_id}:{self.pair}:{self.direction.value}:{self.entry_price}:{self.target_stop_loss}:{self.target_take_profit}:{self.composite_confidence}"
        self.rationale_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

class PortfolioExposure(BaseModel):
    agent_name: str = "Portfolio Risk Agent"
    timestamp: datetime = Field(default_factory=utc_now)
    net_currency_exposures: Dict[str, int] = Field(default_factory=dict)
    total_portfolio_heat_pct: float = 0.0
    open_position_count: int = 0
    can_open_trade: bool = True
    blocking_reason: Optional[str] = None

class RiskEvaluation(BaseModel):
    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    proposal_id: str
    approved: bool
    pair: str
    direction: SignalDirection
    direction_bias: SignalDirection = SignalDirection.NEUTRAL
    approval_status: str = "PENDING"
    entry_price: float
    calculated_lot_size: float = 0.0
    stake_amount_usd: float = 0.0
    stake_pct: float = 0.5
    risk_amount_usd: float = 0.0
    portfolio_heat_after_trade_pct: float = 0.0
    spread_to_stop_ratio: float = 0.0
    stop_loss: float
    take_profit: float
    veto_reason: Optional[str] = None
    missing_conditions: List[str] = Field(default_factory=list)
    action_trigger: Optional[str] = None
    timemachine_metrics: Optional[Dict[str, Any]] = None
    portfolio_equity: float
    daily_drawdown_current_pct: float
    consecutive_losses: int = 0
    session_trades_count: int = 0
    session_name: str = "UNKNOWN"
    session_allowed: bool = True

# ----------------- Tier 4: Execution, Telemetry & Attribution -----------------
class OrderExecutionReport(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    proposal_id: str
    pair: str
    direction: SignalDirection
    requested_lot_size: float
    filled_lot_size: float
    requested_price: float
    executed_price: float
    slippage_pips: float
    spread_at_fill_pips: float = 1.2
    commission_usd: float = 0.0
    latency_ms: int = 45
    stop_loss: float
    take_profit: float
    status: OrderStatus = OrderStatus.FILLED
    execution_time: datetime = Field(default_factory=utc_now)
    belief_snapshot_id: Optional[str] = None

class BeliefSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    proposal_id: str
    pair: str
    direction: SignalDirection
    regime: MarketRegime
    pattern_signal: float
    quant_signal: float
    sentiment_signal: float
    macro_state: str
    decision_confidence: float
    risk_approved: bool
    timestamp: datetime = Field(default_factory=utc_now)
    final_result_r: Optional[float] = None

class AuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    order_id: str
    pair: str
    direction: SignalDirection
    entry_price: float
    exit_price: float
    pnl_usd: float
    pnl_pips: float
    r_multiple: float
    mae_pips: float = 0.0
    mfe_pips: float = 0.0
    holding_time_minutes: float
    outcome: str
    rule_compliant: bool = True
    post_mortem: str
    belief_snapshot: Optional[BeliefSnapshot] = None
