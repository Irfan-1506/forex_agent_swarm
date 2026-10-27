"""
Tier 3: Risk Manager Agent with Absolute Veto Authority.
Upgraded with strict institutional risk controls:
1. Higher-Probability Session Filter (London Open, NY Open, London/NY Overlap only)
2. Blocked Expiries Filter (Blocks 5s and 15s negative-expectancy binary bets)
3. Hard Circuit Breakers:
   - Max 2 consecutive losses shutdown
   - Max 3 trades per session cap
   - Max 1.0% daily loss limit
   - Max 4.0% weekly drawdown limit
4. Fixed-Fractional Sizing (0.5% default balance stake, no martingale)
5. Monte Carlo Time Machine Fat-Tailed Simulation & Out-of-Sample Calibration Gates
6. Watchlist & Missing Conditions Transmittance
"""
from typing import Optional, List, Dict, Any
from agents.base_agent import BaseAgent
from core.models import TradeProposal, RiskEvaluation, SignalDirection, MarketRegime, utc_now
from engine.timemachine_simulator import MonteCarloTimeMachine, get_current_forex_session
from core.alert_dispatcher import global_alert_dispatcher
from core.calibration_validator import global_calibration_validator

class RiskManagerAgent(BaseAgent):
    def __init__(self, event_bus, config=None, initial_equity: float = 100_000.0):
        super().__init__("Risk Manager Agent", event_bus, config)
        self.equity = initial_equity
        self.peak_equity = initial_equity
        self.daily_starting_equity = initial_equity
        self.consecutive_losses = 0
        self.session_trades = 0
        self.time_machine = MonteCarloTimeMachine(
            simulations=self.config.timemachine_simulations,
            horizon_bars=50
        )

    def update_equity(self, current_equity: float):
        self.equity = current_equity
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def record_trade_outcome(self, win: bool):
        self.session_trades += 1
        if win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

    def reset_session_counters(self):
        self.session_trades = 0

    async def evaluate_proposal(self, proposal: TradeProposal) -> RiskEvaluation:
        session_meta = get_current_forex_session()
        session_name = session_meta["session"]
        session_allowed = session_name in self.config.allowed_sessions

        missing_conditions = list(proposal.missing_conditions)
        action_trigger = proposal.action_trigger

        # 1. Check Emergency Halt
        if self.blackboard.emergency_halt.is_halted:
            return self._veto(proposal, f"EMERGENCY_HALT_ACTIVE: {self.blackboard.emergency_halt.halt_reason}", missing_conditions, action_trigger, session_name, session_allowed)

        # 2. Check Hard Circuit Breakers
        # A. Daily Drawdown Limit (1.0% limit)
        daily_loss_pct = (self.daily_starting_equity - self.equity) / self.daily_starting_equity
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            missing_conditions.append(f"Daily drawdown limit reached ({daily_loss_pct*100:.2f}% >= {self.config.max_daily_loss_pct*100:.1f}%)")
            return self._veto(proposal, f"DAILY_DRAWDOWN_BREACH: Daily loss {daily_loss_pct*100:.2f}% >= {self.config.max_daily_loss_pct*100:.1f}% limit.", missing_conditions, action_trigger, session_name, session_allowed)

        # B. Weekly Drawdown Limit (4.0% limit)
        drawdown_pct = (self.peak_equity - self.equity) / self.peak_equity
        if drawdown_pct >= self.config.max_weekly_drawdown_pct:
            missing_conditions.append(f"Weekly drawdown breach: {drawdown_pct*100:.2f}% >= {self.config.max_weekly_drawdown_pct*100:.1f}%")
            return self._veto(proposal, f"WEEKLY_DRAWDOWN_BREACH: Drawdown {drawdown_pct*100:.2f}% >= {self.config.max_weekly_drawdown_pct*100:.1f}% limit.", missing_conditions, action_trigger, session_name, session_allowed)

        # C. Consecutive Losses Breaker (Stop after 2 consecutive losses)
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            missing_conditions.append(f"Hard circuit breaker tripped: {self.consecutive_losses} consecutive losses")
            return self._veto(proposal, f"CONSECUTIVE_LOSS_CIRCUIT_BREAKER: {self.consecutive_losses} consecutive losses (limit: {self.config.max_consecutive_losses}). Trading halted for session.", missing_conditions, action_trigger, session_name, session_allowed)

        # D. Session Trade Count Cap (Max 3 trades per session)
        if self.session_trades >= self.config.max_trades_per_session:
            missing_conditions.append(f"Session trade cap reached ({self.session_trades}/{self.config.max_trades_per_session})")
            return self._veto(proposal, f"SESSION_TRADE_CAP_REACHED: {self.session_trades} trades executed this session (limit: {self.config.max_trades_per_session}).", missing_conditions, action_trigger, session_name, session_allowed)

        # 3. Check Blocked Expiries (e.g. 5s and 15s)
        if proposal.optimal_expiry in self.config.blocked_expiries:
            missing_conditions.append(f"Requested expiry ({proposal.optimal_expiry}) is blocked due to sub-minute negative expectancy")
            return self._veto(proposal, f"EXPIRY_BLOCKED_VETO: Expiry '{proposal.optimal_expiry}' blocked due to negative expectancy.", missing_conditions, action_trigger, session_name, session_allowed)

        # 4. Check Session Liquidity
        if not session_allowed:
            missing_conditions.append(f"Session {session_name} is outside liquid windows ({', '.join(self.config.allowed_sessions)})")
            return self._veto(proposal, f"SESSION_LIQUIDITY_VETO: Active session ({session_name}) is outside approved trading windows.", missing_conditions, action_trigger, session_name, session_allowed)
        if drawdown_pct >= self.config.max_weekly_drawdown_pct:
            missing_conditions.append(f"Weekly drawdown limit reached ({drawdown_pct*100:.2f}% >= {self.config.max_weekly_drawdown_pct*100:.1f}%)")
            return self._veto(proposal, f"MAX_DRAWDOWN_BREACH: Drawdown {drawdown_pct*100:.2f}% >= {self.config.max_weekly_drawdown_pct*100:.1f}% limit.", missing_conditions, action_trigger, session_name, session_allowed)

        # 5. Check Directional Proposal State
        if proposal.direction == SignalDirection.NEUTRAL or proposal.entry_type == "NO_TRADE":
            return self._veto(proposal, "CONFLUENCE_WATCHLIST_STATE: Awaiting confluence confirmation before issuing direct instruction.", missing_conditions, action_trigger, session_name, session_allowed)

        # 6. Check Spread to Stop Ratio
        micro = self.blackboard.microstructure_reports.get(proposal.pair)
        spread_pips = micro.spread_pips if micro else 1.2
        stop_distance = abs(proposal.entry_price - proposal.target_stop_loss)
        pip_unit = 0.01 if "JPY" in proposal.pair else 0.0001
        stop_distance_pips = stop_distance / pip_unit
        spread_ratio = spread_pips / (stop_distance_pips + 1e-6)

        if spread_ratio > self.config.max_spread_to_stop_ratio:
            missing_conditions.append(f"Spread friction ratio {spread_ratio*100:.1f}% exceeds limit {self.config.max_spread_to_stop_ratio*100:.1f}%")
            return self._veto(proposal, f"SPREAD_FRICTION_TOO_HIGH: Spread consumes {spread_ratio*100:.1f}% of stop distance.", missing_conditions, action_trigger, session_name, session_allowed)

        # 7. Check Portfolio Heat & Correlated Exposure
        portfolio_exp = self.blackboard.portfolio_exposure
        if portfolio_exp and not portfolio_exp.can_open_trade:
            missing_conditions.append(f"Portfolio exposure block: {portfolio_exp.blocking_reason}")
            return self._veto(proposal, f"PORTFOLIO_RISK_BLOCK: {portfolio_exp.blocking_reason}", missing_conditions, action_trigger, session_name, session_allowed)

        # 8. Fixed-Fractional Sizing (0.5% default stake)
        stake_pct = self.config.max_stake_per_trade_pct
        stake_usd = round(self.equity * stake_pct, 2)
        pip_value_std_lot = 10.0
        lot_size = round(stake_usd / (stop_distance_pips * pip_value_std_lot), 2)
        lot_size = max(0.01, min(25.0, lot_size))

        # 9. Time Machine Stochastic Fat-Tailed Simulation
        quant = self.blackboard.quant_reports.get(proposal.pair)
        atr_val = quant.atr if quant else (stop_distance / 1.5)
        candles = self.blackboard.candles.get(proposal.pair, [])
        is_jpy = "JPY" in proposal.pair

        tm_results = self.time_machine.simulate_trade_odds(
            entry_price=proposal.entry_price,
            stop_loss=proposal.target_stop_loss,
            take_profit=proposal.target_take_profit,
            direction=proposal.direction,
            atr=atr_val,
            historical_candles=candles,
            regime=proposal.regime,
            spread_pips=spread_pips,
            slippage_pips=0.3,
            commission_usd=self.config.commission_per_lot_round_turn,
            binary_payout_pct=getattr(proposal, "binary_payout_pct", 87.0) or 87.0,
            is_jpy=is_jpy
        )

        # 10. Out-of-Sample Calibration Verification
        calib_eval = global_calibration_validator.evaluate_out_of_sample_edge(
            quotex_breakeven_rate=tm_results["quotex_breakeven_win_rate_pct"]
        )
        if calib_eval.get("veto_required"):
            missing_conditions.append(f"Out-of-sample edge calibration warning: {calib_eval['rationale']}")
            return self._veto(
                proposal,
                f"CALIBRATION_DEFICIT_VETO: Out-of-sample edge unverified ({calib_eval['status']}): {calib_eval['rationale']}",
                missing_conditions, action_trigger, session_name, session_allowed, timemachine_metrics=tm_results
            )

        if not tm_results["simulation_passed"]:
            missing_conditions.append(f"Simulated odds ({tm_results['binary_ci_95_lower']}% lower CI) sub-breakeven hurdle ({tm_results['binary_hurdle_rate_pct']}%)")
            return self._veto(
                proposal,
                f"TIMEMACHINE_STATISTICAL_VETO: {tm_results['rationale']}",
                missing_conditions, action_trigger, session_name, session_allowed, timemachine_metrics=tm_results
            )

        # ALL 10 INSTITUTIONAL GATES CLEARED -> APPROVE DIRECT EXECUTION
        approval = RiskEvaluation(
            proposal_id=proposal.proposal_id,
            approved=True,
            pair=proposal.pair,
            direction=proposal.direction,
            direction_bias=proposal.direction_bias,
            approval_status="APPROVED",
            entry_price=proposal.entry_price,
            calculated_lot_size=lot_size,
            stake_amount_usd=stake_usd,
            stake_pct=round(stake_pct * 100, 2),
            risk_amount_usd=stake_usd,
            portfolio_heat_after_trade_pct=round(((portfolio_exp.total_portfolio_heat_pct if portfolio_exp else 0) + stake_pct), 4),
            spread_to_stop_ratio=round(spread_ratio, 3),
            stop_loss=proposal.target_stop_loss,
            take_profit=proposal.target_take_profit,
            veto_reason=None,
            missing_conditions=[],
            action_trigger=action_trigger,
            timemachine_metrics=tm_results,
            portfolio_equity=round(self.equity, 2),
            daily_drawdown_current_pct=round(daily_loss_pct, 4),
            consecutive_losses=self.consecutive_losses,
            session_trades_count=self.session_trades,
            session_name=session_name,
            session_allowed=session_allowed
        )

        self.blackboard.approved_orders[proposal.proposal_id] = approval
        await self.bus.publish(f"risk.approval.{proposal.pair}", approval)

        global_alert_dispatcher.dispatch_alert(
            title=f"Direct Signal Approved: {proposal.pair} {proposal.direction.value}",
            message=f"Stake: ${stake_usd:.2f} ({stake_pct*100:.1f}%). Confluence Verified. TM Odds: {tm_results['p_target_hit_pct']}%.",
            severity="TRADE",
            pair=proposal.pair
        )
        return approval

    def _veto(
        self,
        proposal: TradeProposal,
        reason: str,
        missing_conditions: List[str],
        action_trigger: Optional[str],
        session_name: str,
        session_allowed: bool,
        timemachine_metrics: dict = None
    ) -> RiskEvaluation:
        daily_loss_pct = (self.daily_starting_equity - self.equity) / self.daily_starting_equity
        stake_usd = round(self.equity * self.config.max_stake_per_trade_pct, 2)
        
        return RiskEvaluation(
            proposal_id=proposal.proposal_id,
            approved=False,
            pair=proposal.pair,
            direction=proposal.direction,
            direction_bias=proposal.direction_bias,
            approval_status="WATCHLIST / VETOED",
            entry_price=proposal.entry_price,
            calculated_lot_size=0.0,
            stake_amount_usd=stake_usd,
            stake_pct=round(self.config.max_stake_per_trade_pct * 100, 2),
            risk_amount_usd=0.0,
            portfolio_heat_after_trade_pct=0.0,
            spread_to_stop_ratio=0.0,
            stop_loss=proposal.target_stop_loss,
            take_profit=proposal.target_take_profit,
            veto_reason=reason,
            missing_conditions=missing_conditions,
            action_trigger=action_trigger,
            timemachine_metrics=timemachine_metrics,
            portfolio_equity=round(self.equity, 2),
            daily_drawdown_current_pct=round(daily_loss_pct, 4),
            consecutive_losses=self.consecutive_losses,
            session_trades_count=self.session_trades,
            session_name=session_name,
            session_allowed=session_allowed
        )
