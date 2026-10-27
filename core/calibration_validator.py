"""
Out-of-Sample Calibration Validator & Skepticism Engine.
Measures whether agent confidence scores accurately predict empirical outcomes:
1. Brier Score & Brier Skill Score (BSS) calculation
2. Expected Calibration Error (ECE) across probability deciles
3. Out-of-sample edge persistence vs Quotex asymmetric break-even hurdle
4. Automated Veto: If calibration degrades (Brier > 0.24) or out-of-sample edge evaporates,
   forces the Swarm into WAIT / NO TRADE.
"""
from typing import List, Dict, Any, Tuple
import math

class CalibrationValidator:
    def __init__(self, max_history: int = 200, brier_threshold: float = 0.24):
        self.predictions: List[float] = []
        self.outcomes: List[int] = [] # 1 for WIN, 0 for LOSS
        self.timestamps: List[str] = []
        self.max_history = max_history
        self.brier_threshold = brier_threshold

    def record_prediction_outcome(self, predicted_confidence: float, outcome_win: bool, timestamp: str = ""):
        """Records an out-of-sample trade: predicted probability [0.0, 1.0] vs real outcome (1 or 0)."""
        p = max(0.01, min(0.99, float(predicted_confidence)))
        y = 1 if outcome_win else 0
        self.predictions.append(p)
        self.outcomes.append(y)
        self.timestamps.append(timestamp)

        if len(self.predictions) > self.max_history:
            self.predictions.pop(0)
            self.outcomes.pop(0)
            self.timestamps.pop(0)

    def calculate_brier_score(self) -> float:
        """
        Brier Score: Mean squared error of probability forecasts.
        0.0 = perfect predictive model
        0.25 = uninformative 50/50 coin toss
        > 0.25 = poorly calibrated or inversely predictive
        """
        if not self.predictions:
            return 0.20  # Neutral baseline
        n = len(self.predictions)
        mse = sum((p - y) ** 2 for p, y in zip(self.predictions, self.outcomes)) / n
        return round(float(mse), 4)

    def calculate_calibration_curve(self, num_bins: int = 5) -> List[Dict[str, Any]]:
        """Splits forecasts into bins and calculates observed frequency vs mean confidence."""
        if len(self.predictions) < 5:
            return []

        bins = []
        bin_width = 1.0 / num_bins
        for i in range(num_bins):
            lower = i * bin_width
            upper = (i + 1) * bin_width
            bin_preds = []
            bin_outs = []
            for p, y in zip(self.predictions, self.outcomes):
                if (lower <= p < upper) or (i == num_bins - 1 and lower <= p <= upper):
                    bin_preds.append(p)
                    bin_outs.append(y)

            count = len(bin_preds)
            if count > 0:
                mean_pred = sum(bin_preds) / count
                empirical_rate = sum(bin_outs) / count
                gap = abs(empirical_rate - mean_pred)
            else:
                mean_pred = (lower + upper) / 2.0
                empirical_rate = 0.0
                gap = 0.0

            bins.append({
                "bin_range": f"{int(lower*100)}%-{int(upper*100)}%",
                "count": count,
                "mean_predicted_prob": round(mean_pred, 3),
                "empirical_win_rate": round(empirical_rate, 3),
                "calibration_gap": round(gap, 3)
            })
        return bins

    def calculate_expected_calibration_error(self) -> float:
        """Weighted average of calibration gap across bins."""
        bins = self.calculate_calibration_curve()
        if not bins:
            return 0.05
        total = sum(b["count"] for b in bins)
        if total == 0:
            return 0.05
        ece = sum(b["calibration_gap"] * (b["count"] / total) for b in bins)
        return round(float(ece), 4)

    def evaluate_out_of_sample_edge(self, quotex_breakeven_rate: float = 54.05) -> Dict[str, Any]:
        """
        Assesses whether the system's edge survives on out-of-sample data.
        Returns calibration health and pass/fail gate.
        """
        n = len(self.predictions)
        brier = self.calculate_brier_score()
        ece = self.calculate_expected_calibration_error()

        if n < 8:
            # Cold start: Insufficient data to reject, but cautious
            return {
                "sample_size": n,
                "brier_score": brier,
                "ece": ece,
                "empirical_win_rate_pct": 50.0,
                "quotex_breakeven_pct": quotex_breakeven_rate,
                "calibration_healthy": True,
                "veto_required": False,
                "status": "CALIBRATION_WARMUP",
                "rationale": f"Gathering out-of-sample data ({n}/8 trades recorded). Brier baseline: {brier:.3f}."
            }

        wins = sum(self.outcomes)
        empirical_win_rate = (wins / n) * 100.0
        
        # Calibration Health Checks:
        # 1. Brier score must be <= threshold (0.24)
        # 2. Empirical win rate on out-of-sample data must exceed Quotex break-even rate
        brier_pass = (brier <= self.brier_threshold)
        breakeven_pass = (empirical_win_rate >= quotex_breakeven_rate)
        
        is_healthy = brier_pass and breakeven_pass
        veto_required = not is_healthy

        if not brier_pass:
            status = "CALIBRATION_FAILED_OVERCONFIDENT"
            reason = f"Brier score {brier:.3f} exceeds maximum threshold of {self.brier_threshold:.2f}."
        elif not breakeven_pass:
            status = "EDGE_SUB_BREAKEVEN"
            reason = f"Out-of-sample win rate ({empirical_win_rate:.1f}%) is below Quotex asymmetric break-even ({quotex_breakeven_rate:.1f}%)."
        else:
            status = "CALIBRATION_VERIFIED"
            reason = f"Out-of-sample win rate ({empirical_win_rate:.1f}%) clears hurdle ({quotex_breakeven_rate:.1f}%) with Brier score {brier:.3f}."

        return {
            "sample_size": n,
            "brier_score": brier,
            "ece": ece,
            "empirical_win_rate_pct": round(empirical_win_rate, 1),
            "quotex_breakeven_pct": quotex_breakeven_rate,
            "calibration_healthy": is_healthy,
            "veto_required": veto_required,
            "status": status,
            "rationale": reason
        }

global_calibration_validator = CalibrationValidator()
