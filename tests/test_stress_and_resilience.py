"""
Stress, Edge Case & Resilience Test Suite.
Tests portfolio heat limits, consecutive failure kill-switches, and audit loops.
"""
import pytest
from core.models import (
    TradeProposal, SignalDirection, MarketTick, OrderExecutionReport, OrderStatus
)
from core.bus import SwarmEventBus
from config import config
from agents import (
    PortfolioRiskAgent, RiskManagerAgent, EmergencyHaltAgent,
    DataIntegrityAgent, AuditFeedbackAgent, PerformanceAttributionAgent
)
from engine.mock_broker import MockBrokerEngine

@pytest.fixture
def bus():
    return SwarmEventBus()

@pytest.mark.asyncio
async def test_consecutive_broker_errors_trigger_kill_switch(bus):
    emergency_agent = EmergencyHaltAgent(bus, config)
    
    # 3 errors in a row should trigger kill switch
    await emergency_agent.record_execution_error("Error 1")
    assert emergency_agent.is_active_halt() is False
    await emergency_agent.record_execution_error("Error 2")
    assert emergency_agent.is_active_halt() is False
    await emergency_agent.record_execution_error("Error 3")
    assert emergency_agent.is_active_halt() is True

@pytest.mark.asyncio
async def test_portfolio_correlation_caps(bus):
    port_agent = PortfolioRiskAgent(bus, config)
    
    # Simulate 2 existing BUY positions on EUR/USD and GBP/USD (Net USD is -2)
    pos1 = OrderExecutionReport(
        proposal_id="p1", pair="EUR/USD", direction=SignalDirection.BUY,
        requested_lot_size=1.0, filled_lot_size=1.0, requested_price=1.0850,
        executed_price=1.0850, slippage_pips=0.0, stop_loss=1.0800, take_profit=1.0950
    )
    pos2 = OrderExecutionReport(
        proposal_id="p2", pair="GBP/USD", direction=SignalDirection.BUY,
        requested_lot_size=1.0, filled_lot_size=1.0, requested_price=1.2950,
        executed_price=1.2950, slippage_pips=0.0, stop_loss=1.2900, take_profit=1.3050
    )
    bus.blackboard.open_positions[pos1.order_id] = pos1
    bus.blackboard.open_positions[pos2.order_id] = pos2

    # Attempt 3rd BUY on AUD/USD (would make USD exposure -3 > max 2)
    exp = await port_agent.evaluate_portfolio_heat("AUD/USD", SignalDirection.BUY)
    assert exp.can_open_trade is False
    assert "CORRELATED_EXPOSURE_BREACH" in exp.blocking_reason

@pytest.mark.asyncio
async def test_daily_drawdown_breaker(bus):
    risk_agent = RiskManagerAgent(bus, config, initial_equity=100_000.0)
    # Simulate 4% drawdown ($96,000 equity)
    risk_agent.update_equity(96_000.0)

    proposal = TradeProposal(
        pair="EUR/USD", direction=SignalDirection.BUY, entry_price=1.0850,
        target_stop_loss=1.0830, target_take_profit=1.0890, rrr=2.0,
        composite_confidence=0.75, rationale="Test"
    )
    proposal.freeze_and_hash()

    eval_res = await risk_agent.evaluate_proposal(proposal)
    assert eval_res.approved is False
    assert "DAILY_DRAWDOWN_BREACH" in eval_res.veto_reason

@pytest.mark.asyncio
async def test_audit_feedback_and_attribution(bus):
    audit_agent = AuditFeedbackAgent(bus, config)
    attrib_agent = PerformanceAttributionAgent(bus, config)

    order = OrderExecutionReport(
        proposal_id="p10", pair="EUR/USD", direction=SignalDirection.BUY,
        requested_lot_size=1.0, filled_lot_size=1.0, requested_price=1.0850,
        executed_price=1.0850, slippage_pips=0.0, commission_usd=5.0,
        stop_loss=1.0830, take_profit=1.0890
    )

    # Exit with 20 pips gain
    audit = await audit_agent.audit_closed_trade(
        order=order, exit_price=1.0870, initial_risk_usd=200.0
    )
    assert audit.outcome == "WIN"
    assert audit.r_multiple > 0
    assert audit.pnl_usd == (20.0 * 10.0 * 1.0) - 5.0  # $195.00

    await attrib_agent.ingest_audit(audit)
    summary = attrib_agent.get_attribution_summary()
    assert summary["total_audited_trades"] == 1
    assert summary["overall_win_rate_pct"] == 100.0

@pytest.mark.asyncio
async def test_calibration_validator_edge_and_brier_evaluation():
    from core.calibration_validator import CalibrationValidator
    calib = CalibrationValidator(max_history=50, brier_threshold=0.24)
    
    # 10 trade predictions of 70% confidence, but only 3 win (30% win rate)
    for _ in range(7):
        calib.record_prediction_outcome(predicted_confidence=0.70, outcome_win=False)
    for _ in range(3):
        calib.record_prediction_outcome(predicted_confidence=0.70, outcome_win=True)

    eval_result = calib.evaluate_out_of_sample_edge(quotex_breakeven_rate=54.05)
    # Win rate is 30% < 54.05% break-even, so edge is invalidated and veto is required
    assert eval_result["veto_required"] is True
    assert eval_result["empirical_win_rate_pct"] == 30.0
    assert eval_result["brier_score"] > 0.20
