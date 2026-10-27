# Institutional Forex Agent Swarm

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Architecture](https://img.shields.io/badge/architecture-14--Agent%20Swarm-emerald.svg)]()
[![Monte Carlo](https://img.shields.io/badge/simulation-Bootstrap%20Fat--Tail-purple.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An institutional-grade, multi-agent algorithmic Forex trading intelligence system and Web GUI terminal. Designed with **14 specialized Tier-4 autonomous agents**, real-time interbank feeds, fat-tailed **Bootstrap Monte Carlo simulation**, strict risk guardrails, and an interactive **TradingView Lightweight Charts** dashboard.

---

## 🏛 System Architecture

The swarm operates in a continuous blackboard orchestration cycle across four specialized pillars:

```
Institutional Forex Swarm (14 Agents)
├── 📊 Perception & Market Dynamics
│   ├── Microstructure & Order Flow Agent (Tick integrity & spread checks)
│   ├── Data Integrity Agent (Anomaly detection & spike rejection)
│   ├── Regime Classifier Agent (Trend vs Mean-Reverting vs High Volatility)
│   └── Quantitative Technical Agent (RSI, ATR, Bollinger, Multi-TF MAs)
├── 🌐 Macroeconomics & Sentiment
│   ├── Macro Calendar Agent (Embargoes high-impact news releases)
│   ├── Global News Sentiment Agent (Financial narrative & polarity scoring)
│   └── Cross-Pair Scanner Agent (28 Forex pairs ranked by opportunity score)
├── 🎯 Decision & Risk Governance
│   ├── Pattern Recognition Agent (Support/Resistance, Breakout & Reversals)
│   ├── Decision Maker Agent (Consensus synthesis: Direction vs Approval)
│   ├── Portfolio Risk Agent (Currency correlation & heat limits)
│   ├── Risk Manager Agent (Asymmetric payout hurdle & circuit breakers)
│   └── Emergency Halt Agent (Global kill-switch & automatic shutdown)
└── 🔬 Validation, Simulation & Attribution
    ├── Time Machine Monte Carlo Simulator (Fat-tailed bootstrap paths)
    ├── Calibration Validator Agent (Out-of-sample empirical hit-rate check)
    └── Performance Attribution Agent (PnL decomposition & factor audit)
```

---

## 🛡️ Risk Guardrails & Circuit Breakers

* **Direction Separated from Approval**: The system can detect directional bias (`BUY` / `SELL`) without issuing premature execution. Only setups clearing the strict confluence checklist and payout hurdle receive trade approval.
* **Asymmetric Binary Payout Hurdle**: Accommodates platform payouts (~70–92%) where break-even win rate is $1 / (1 + \text{payout})$. Only trades whose 95% Confidence Interval lower bound clears the break-even hurdle + buffer are authorized.
* **Fat-Tailed Monte Carlo (2,000 Paths)**: Replaces standard Brownian motion with historical return bootstrapping and volatility clustering.
* **Strict Capital Limits**:
  * Max Stake per Trade: `0.5%` of balance ($500 on $100k account).
  * Max Consecutive Losses: `2` (triggers automatic cooldown).
  * Max Trades per Session: `3` (prevents overtrading).
  * Max Daily Loss: `1.0%`.
  * Blocked Expiries: `5s` and `15s` are permanently blocked due to negative mathematical expectancy.
* **Session Liquidity Filters**: Trading is permitted only during liquid sessions (London Open, New York Open, London/NY overlap).

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/Irfan-1506/forex_agent_swarm.git
cd forex_agent_swarm
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Tests
Run the complete unit and stress test suites:
```bash
pytest tests -v
```

### 3. Launch the Web GUI Server
Run the local server (binds to `0.0.0.0:8000` for PC, Android, and laptop access):
```bash
python gui_server.py
```

Open in your browser:
* **Local Machine**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Local Network (Android / Phone / Laptop)**: `http://<YOUR_LAN_IP>:8000`

---

## 📈 Web GUI Features

* **TradingView Candlestick Terminal**: Real-time candlestick charts with multi-timeframe support (`1M`, `2M`, `5M`, `15M`, `1H`).
* **Actionable Watchlist**: When trades are vetoed, the dashboard specifies the exact missing conditions (e.g., simulated win prob deficit, spread threshold) and actionable triggers.
* **Quotex Payout Calculator**: Select custom payout percentages (`80%`, `85%`, `87%`, `90%`, `92%`) to re-calibrate the break-even math in real time.
* **Audio Alerts**: Web Audio API buzzer chime triggered on high-conviction signals.
* **Emergency Kill Switch**: One-click manual emergency halt button and automated circuit breaker status monitor.

---

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
