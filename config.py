"""
Institutional Configuration for the Forex Agent Swarm.
Enforces high signal quality, session liquidity filters, strict fixed-fractional sizing (0.5%),
and hard circuit breakers (max 2 consecutive losses, max 1.0% daily loss).
"""
from pydantic import BaseModel
from typing import List, Dict

class SwarmConfig(BaseModel):
    # Operating Mode
    environment: str = "paper_trading"
    log_level: str = "INFO"
    quotex_enforce_simulation_mode: bool = True
    
    # Currency Universe
    tracked_pairs: List[str] = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF", "NZD/USD"]
    base_currency: str = "USD"
    account_initial_balance: float = 100_000.0
    
    # --- Tier 0: Safety & Data Integrity ---
    max_tick_staleness_seconds: float = 10.0
    max_price_jump_spike_pct: float = 0.008
    emergency_kill_switch_active: bool = False
    max_consecutive_execution_errors: int = 3
    
    # --- Higher-Probability Sessions & Expiry Filters ---
    # Trade only liquid, repeatable sessions; avoid thin liquidity / rollover
    allowed_sessions: List[str] = ["LONDON_MORNING", "LONDON_NY_OVERLAP", "NEW_YORK_AFTERNOON"]
    blocked_expiries: List[str] = ["5s", "15s"]  # Block sub-minute noise with negative expectancy
    
    # --- Confluence & Edge Thresholds ---
    min_confidence_threshold: float = 0.55       # Raised threshold for genuine confluence
    min_risk_to_reward_ratio: float = 1.5
    min_binary_edge_margin_pct: float = 2.0      # Lower bound must exceed break-even + 2.0%
    min_calibration_trades: int = 100
    
    # --- Tier 3: Capital Risk & Hard Circuit Breakers ---
    max_stake_per_trade_pct: float = 0.005       # 0.5% fixed-fractional stake of current balance
    max_open_trades: int = 2                     # Maximum 1-2 open trades at a time
    max_correlated_trades: int = 2               # Maximum 1-2 USD-directional trade across pairs
    max_trades_per_session: int = 3              # Maximum 2-3 trades per session
    max_consecutive_losses: int = 2              # Hard circuit breaker: stop after 2 consecutive losses
    max_daily_loss_pct: float = 0.01             # 1.0% daily account loss shutdown
    max_weekly_drawdown_pct: float = 0.04        # 4.0% weekly drawdown shutdown
    max_portfolio_heat_pct: float = 0.02         # 2.0% max portfolio heat
    max_single_currency_net_exposure: int = 2    # Cap concurrent exposure to single currency
    max_spread_to_stop_ratio: float = 0.18       # Max spread 18% of stop distance
    max_slippage_pips: float = 1.5
    max_spread_pips_allowed: float = 2.2         # Stricter spread ceiling
    adx_trending_threshold: float = 25.0         # ADX trend vs range threshold
    
    # --- Time Machine Monte Carlo Parameters ---
    timemachine_simulations: int = 2000
    timemachine_min_win_prob_pct: float = 46.0
    timemachine_min_expected_r: float = 0.08
    
    # --- Tier 4: Execution Realism & Costs ---
    commission_per_lot_round_turn: float = 5.0
    swap_long_pips_per_day: float = -0.5
    swap_short_pips_per_day: float = 0.2
    simulated_latency_ms: int = 45
    
    # Weights for Chief Decision Maker
    weights: Dict[str, float] = {
        "macro": 0.15,
        "sentiment": 0.20,
        "pattern": 0.35,
        "quant": 0.30
    }
    
    # Macroeconomic Blackouts
    hard_blackout_minutes: int = 15
    soft_blackout_minutes: int = 8

config = SwarmConfig()
