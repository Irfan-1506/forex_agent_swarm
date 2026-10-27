"""
Forex Agent Swarm - Web GUI Server (Starlette / Uvicorn).
Provides interactive endpoints for Quotex timeframe selection,
28-pair scanner, Time Machine Monte Carlo simulation telemetry, and live agent reasoning.
"""
import os
import json
import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, Response, FileResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from engine.swarm_orchestrator import SwarmOrchestrator
from core.alert_dispatcher import global_alert_dispatcher

orchestrator = SwarmOrchestrator()
HTML_PATH = os.path.join(os.path.dirname(__file__), "web", "index.html")
CHART_JS_PATH = os.path.join(os.path.dirname(__file__), "web", "lightweight-charts.js")
ZIP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch", "forex_agent_swarm.zip")
if not os.path.exists(ZIP_PATH):
    ZIP_PATH = os.path.join(os.path.dirname(__file__), "forex_agent_swarm.zip")

def safe_json_response(data: any, status_code: int = 200) -> Response:
    content = json.dumps(data, default=str)
    return Response(content=content, status_code=status_code, media_type="application/json")

async def homepage(request):
    if os.path.exists(HTML_PATH):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    return HTMLResponse("<h1>Web GUI file not found</h1>", status_code=404)

async def serve_chart_js(request):
    if os.path.exists(CHART_JS_PATH):
        with open(CHART_JS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content, media_type="application/javascript")
    return Response("// not found", status_code=404)

async def serve_zip(request):
    candidate_paths = [
        r"C:\Users\Asus\.gemini\antigravity\scratch\forex_agent_swarm.zip",
        r"C:\Users\Asus\Downloads\forex_agent_swarm.zip",
        os.path.join(os.path.dirname(__file__), "forex_agent_swarm.zip")
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return FileResponse(p, filename="forex_agent_swarm.zip", media_type="application/zip")
    return Response("Zip archive not found", status_code=404)

async def api_cycle(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    pair = body.get("pair", "EUR/USD")
    timeframe = body.get("timeframe", "1M")
    payout = float(body.get("payout", 87.0))
    result = await orchestrator.run_cycle(pair=pair, timeframe=timeframe, binary_payout_pct=payout)
    return safe_json_response(result)

async def api_tick(request):
    pair = request.query_params.get("pair", "EUR/USD")
    timeframe = request.query_params.get("timeframe", "1M")
    tick = orchestrator.data_feed.generate_tick(pair)
    candles = orchestrator.data_feed.generate_candles(pair, count=60, timeframe=timeframe, end_price=tick.bid)
    latest_candle = {
        "time": int(candles[-1].timestamp.timestamp()),
        "open": candles[-1].open,
        "high": candles[-1].high,
        "low": candles[-1].low,
        "close": candles[-1].close,
        "volume": candles[-1].volume
    } if candles else None

    return safe_json_response({
        "pair": pair,
        "timeframe": timeframe,
        "tick": tick.model_dump(mode="json"),
        "latest_candle": latest_candle,
        "equity": round(orchestrator.broker.equity, 2),
        "balance": round(orchestrator.broker.balance, 2)
    })

async def api_scanner(request):
    results = await orchestrator.scan_cross_pairs()
    return safe_json_response({"ranked_setups": results})

async def api_attribution(request):
    summary = orchestrator.performance_attribution_agent.get_attribution_summary()
    return safe_json_response(summary)

async def api_alerts(request):
    alerts = global_alert_dispatcher.get_recent_alerts(20)
    return safe_json_response({"alerts": alerts})

async def api_kill_switch(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = body.get("action", "trigger")
    reason = body.get("reason", "Manual Operator Trigger")

    if action == "trigger":
        await orchestrator.emergency_halt_agent.trigger_kill_switch(reason, triggered_by="WEB_GUI_OPERATOR")
    else:
        await orchestrator.emergency_halt_agent.reset_kill_switch(operator="WEB_GUI_OPERATOR")

    return safe_json_response({
        "is_halted": orchestrator.blackboard.emergency_halt.is_halted,
        "halt_reason": orchestrator.blackboard.emergency_halt.halt_reason
    })

routes = [
    Route("/", homepage),
    Route("/lightweight-charts.js", serve_chart_js),
    Route("/forex_agent_swarm.zip", serve_zip),
    Route("/download/zip", serve_zip),
    Route("/api/cycle", api_cycle, methods=["POST", "GET"]),
    Route("/api/tick", api_tick, methods=["GET", "POST"]),
    Route("/api/scanner", api_scanner, methods=["GET", "POST"]),
    Route("/api/attribution", api_attribution, methods=["GET"]),
    Route("/api/alerts", api_alerts, methods=["GET"]),
    Route("/api/kill-switch", api_kill_switch, methods=["POST"]),
]

app = Starlette(
    debug=True,
    routes=routes,
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    ]
)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    import socket
    import time
    local_ip = get_local_ip()
    print("=" * 65)
    print("  INSTITUTIONAL FOREX AGENT SWARM - LOCAL SERVER ACTIVE")
    print("=" * 65)
    print(f"  -> On this PC:           http://127.0.0.1:8000")
    print(f"  -> On Android / Laptops: http://{local_ip}:8000")
    print("=" * 65)

    while True:
        try:
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
        except (OSError, Exception) as e:
            print(f"Server caught socket/network event: {e}. Rebinding in 2 seconds...")
            time.sleep(2)
