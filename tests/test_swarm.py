"""
Unit & Integration Test Suite for the 14-Agent Institutional Forex Swarm.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from core.models import MarketTick, Candle, SignalDirection, EventImpact, MacroState, OrderStatus, TradeProposal, utc_now
from core.bus import SwarmEventBus
from config import config
from agents import (
    DataIntegrityAgent,
    EmergencyHaltAgent,
    RegimeClassifierAgent,
    NewsSentimentAgent,
    MacroCalendarAgent,
    MicrostructureAgent,
    PatternRecognitionAgent,
    QuantIndicatorAgent,
    DecisionMakerAgent,
    PortfolioRiskAgent,
    RiskManagerAgent,
    ExecutionRouterAgent,
    AuditFeedbackAgent,
    PerformanceAttributionAgent,
    CrossPairScannerAgent
)
from engine.mock_broker import MockBrokerEngine
from engine.timemachine_simulator import MonteCarloTimeMachine
from engine.micro_entry_timer import SequentialEntryTimer
from engine.swarm_orchestrator import SwarmOrchestrator

@pytest.fixture
def bus():
    return SwarmEventBus()

@pytest.fixture
def sample_candles():
    base = 1.0850
    candles = []
    now = utc_now()
    for i in range(30):
        t = now - timedelta(minutes=30 - i)
        c = Candle(
            timestamp=t,
            open=base,
            high=base + 0.0005,
            low=base - 0.0003,
            close=base + 0.0002,
            volume=500.0
        )
        candles.append(c)
        base = c.close
    return candles

@pytest.mark.asyncio
async def test_data_integrity_agent(bus):
    agent = DataIntegrityAgent(bus, config)
    # Valid tick
    valid_tick = MarketTick(pair="EUR/USD", bid=1.0850, ask=1.0851, spread_pips=1.0)
    report = await agent.validate_tick(valid_tick)
    assert report.feed_healthy is True
    assert report.is_fresh is True

    # Stale tick
    stale_tick = MarketTick(
        pair="EUR/USD", bid=1.0850, ask=1.0851, spread_pips=1.0,
        timestamp=utc_now() - timedelta(seconds=25)
    )
    stale_report = await agent.validate_tick(stale_tick)
    assert stale_report.is_fresh is False
    assert stale_report.feed_healthy is False

@pytest.mark.asyncio
async def test_emergency_halt_agent(bus):
    agent = EmergencyHaltAgent(bus, config)
    assert agent.is_active_halt() is False
    
    await agent.trigger_kill_switch("Manual Test Kill", triggered_by="TEST")
    assert agent.is_active_halt() is True
    assert bus.blackboard.emergency_halt.is_halted is True

    await agent.reset_kill_switch("TEST")
    assert agent.is_active_halt() is False

@pytest.mark.asyncio
async def test_regime_classifier(bus, sample_candles):
    agent = RegimeClassifierAgent(bus, config)
    report = await agent.classify_regime("EUR/USD", sample_candles)
    assert report.regime is not None
    assert report.adx > 0
    assert 0 <= report.atr_percentile <= 100

@pytest.mark.asyncio
async def test_news_sentiment_contradiction(bus):
    agent = NewsSentimentAgent(bus, config)
    headlines = [
        {"text": "Strong jobs report boosts dollar", "score": 0.8},
        {"text": "Manufacturing PMI collapses unexpectedly", "score": -0.7}
    ]
    report = await agent.analyze_sentiment("USD", headlines)
    assert report.contradiction_detected is True

@pytest.mark.asyncio
async def test_macro_calendar_blackout(bus):
    agent = MacroCalendarAgent(bus, config)
    # Event in 5 minutes -> within 15m blackout
    event = {
        "name": "US Non-Farm Payrolls",
        "impact": EventImpact.HIGH,
        "time": utc_now() + timedelta(minutes=5)
    }
    report = await agent.evaluate_economic_schedule("USD", event)
    assert report.state == MacroState.PRE_EVENT
    assert report.lock_trading_window is True

@pytest.mark.asyncio
async def test_microstructure_spread_penalty(bus):
    agent = MicrostructureAgent(bus, config)
    tick = MarketTick(pair="EUR/USD", bid=1.0850, ask=1.0855, spread_pips=5.0)
    report = await agent.analyze_tick(tick)
    assert report.is_tradable is False  # Blown spread > 3.5 pips
    assert report.friction_penalty > 0

@pytest.mark.asyncio
async def test_timemachine_fat_tailed_simulation():
    tm = MonteCarloTimeMachine(simulations=500, horizon_bars=40)
    res = tm.simulate_trade_odds(
        entry_price=1.0850,
        stop_loss=1.0830,
        take_profit=1.0880,
        direction=SignalDirection.BUY,
        atr=0.0015,
        binary_payout_pct=85.0
    )
    assert "p_target_hit_pct" in res
    assert "ci_target_hit_95_lower" in res
    assert "ci_target_hit_95_upper" in res
    assert "expected_payoff_r" in res
    assert "quotex_breakeven_win_rate_pct" in res
    assert res["quotex_breakeven_win_rate_pct"] == 54.05
    assert "session_profile" in res
    assert res["simulations_run"] == 500

@pytest.mark.asyncio
async def test_cross_pair_scanner(bus):
    agent = CrossPairScannerAgent(bus, config)
    results = await agent.scan_market()
    assert len(results) > 0
    assert "conviction_score" in results[0]

@pytest.mark.asyncio
async def test_end_to_end_orchestrator():
    orchestrator = SwarmOrchestrator()
    cycle = await orchestrator.run_cycle(pair="EUR/USD", timeframe="1M")
    assert cycle["pair"] == "EUR/USD"
    assert "tick" in cycle
    assert "explanation" in cycle
    assert "proposal" in cycle
    assert "risk_evaluation" in cycle

@pytest.mark.asyncio
async def test_sub_minute_expiries_blocked(bus):
    risk_agent = RiskManagerAgent(bus, config, initial_equity=100_000.0)
    proposal = TradeProposal(
        pair="EUR/USD",
        direction=SignalDirection.BUY,
        entry_price=1.0850,
        target_stop_loss=1.0830,
        target_take_profit=1.0880,
        rrr=1.5,
        composite_confidence=0.85,
        rationale="Sub-minute test",
        optimal_expiry="5s",
        confluence_checklist={"trend": True, "momentum": True, "structure": True}
    )
    eval_result = await risk_agent.evaluate_proposal(proposal)
    assert eval_result.approved is False
    assert any("blocked" in cond.lower() for cond in eval_result.missing_conditions)

@pytest.mark.asyncio
async def test_two_consecutive_losses_circuit_breaker(bus):
    risk_agent = RiskManagerAgent(bus, config, initial_equity=100_000.0)
    # Record 2 consecutive losses
    risk_agent.record_trade_outcome(win=False)
    risk_agent.record_trade_outcome(win=False)
    assert risk_agent.consecutive_losses == 2
    
    proposal = TradeProposal(
        pair="EUR/USD",
        direction=SignalDirection.BUY,
        entry_price=1.0850,
        target_stop_loss=1.0830,
        target_take_profit=1.0880,
        rrr=1.5,
        composite_confidence=0.85,
        rationale="Loss streak test",
        optimal_expiry="2M - 5M",
        confluence_checklist={"trend": True, "momentum": True, "structure": True}
    )
    eval_result = await risk_agent.evaluate_proposal(proposal)
    assert eval_result.approved is False
    assert any("circuit breaker" in cond.lower() for cond in eval_result.missing_conditions)

@pytest.mark.asyncio
async def test_fixed_fractional_stake(bus):
    risk_agent = RiskManagerAgent(bus, config, initial_equity=100_000.0)
    proposal = TradeProposal(
        pair="EUR/USD",
        direction=SignalDirection.BUY,
        entry_price=1.0850,
        target_stop_loss=1.0830,
        target_take_profit=1.0880,
        rrr=1.5,
        composite_confidence=0.85,
        rationale="Stake test",
        optimal_expiry="2M - 5M"
    )
    eval_result = await risk_agent.evaluate_proposal(proposal)
    # Stake must be 0.5% of $100,000 = $500.00
    assert eval_result.stake_amount_usd == 500.0
