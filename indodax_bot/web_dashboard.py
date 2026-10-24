"""
FastAPI Real-time Web Dashboard with Interactive Manual Buy & Sell Controls for INDODAX DUAL ENGINE.
Provides dark-theme dashboard with live updates, manual order forms, open position sell buttons, metrics, candidate tables, and emergency controls.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from indodax_bot.config import VERSION, MARKET_NAME, OPERATING_MODE, LIVE_TRADING_ENABLED

logger = logging.getLogger(__name__)

class ManualBuyRequest(BaseModel):
    pair_id: str
    size_idr: float = 1_000_000.0
    engine: str = "MANUAL_ORDER"

class ManualSellRequest(BaseModel):
    position_id: str
    reason: str = "MANUAL_SELL_DASHBOARD"

def create_dashboard_app(bot_controller: Any) -> FastAPI:
    app = FastAPI(title="Indodax Dual Engine Dashboard", version=VERSION)

    @app.get("/api/status", response_class=JSONResponse)
    def get_bot_status():
        """Fetch complete current bot status snapshot."""
        try:
            return bot_controller.get_dashboard_state()
        except Exception as e:
            logger.error(f"Error serving dashboard state: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/emergency_stop", response_class=JSONResponse)
    def trigger_emergency_stop():
        """Trigger Emergency Stop mechanism."""
        bot_controller.emergency_stop_triggered = True
        logger.warning("EMERGENCY STOP TRIGGERED FROM DASHBOARD!")
        return {"status": "EMERGENCY_STOP_ACTIVATED", "message": "All new entries halted immediately."}

    @app.post("/api/manual_buy", response_class=JSONResponse)
    def manual_buy_endpoint(req: ManualBuyRequest):
        """Execute interactive manual buy order."""
        try:
            res = bot_controller.manual_buy(
                pair_id=req.pair_id,
                size_idr=req.size_idr,
                engine=req.engine
            )
            return res
        except Exception as e:
            logger.error(f"Error executing manual buy: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/manual_sell", response_class=JSONResponse)
    def manual_sell_endpoint(req: ManualSellRequest):
        """Execute interactive manual sell / close position."""
        try:
            res = bot_controller.manual_sell(
                position_id=req.position_id,
                reason=req.reason
            )
            return res
        except Exception as e:
            logger.error(f"Error executing manual sell: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard_html():
        """Serve complete modern single-page dashboard HTML/CSS/JS UI."""
        return HTML_DASHBOARD_TEMPLATE

    return app

HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>INDODAX DUAL ENGINE — V5.3-MACO R3</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 20px; }
        .card-header { background-color: #21262d; border-bottom: 1px solid #30363d; font-weight: 600; color: #58a6ff; }
        .metric-title { font-size: 0.85rem; color: #8b949e; text-transform: uppercase; }
        .metric-value { font-size: 1.5rem; font-weight: 700; color: #f0f6fc; }
        .badge-paper { background-color: #238636; color: #ffffff; }
        .badge-live-disabled { background-color: #da3633; color: #ffffff; }
        .table-dark { background-color: #161b22; color: #c9d1d9; }
        .table-dark th { background-color: #21262d; color: #8b949e; }
        .positive { color: #3fb950; font-weight: 600; }
        .negative { color: #f85149; font-weight: 600; }
        .neutral { color: #d29922; }
    </style>
</head>
<body class="p-4">
    <div class="container-fluid">
        <!-- Top Banner -->
        <div class="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom border-secondary">
            <div>
                <h2 class="m-0 text-light font-weight-bold">INDODAX DUAL ENGINE <span class="fs-6 text-primary">V5.3-MACO R3</span></h2>
                <small class="text-secondary">Market: Indodax IDR Spot | Pure Scalping & Extreme Momentum Hunter</small>
            </div>
            <div>
                <span class="badge badge-paper p-2 fs-6">OPERATING MODE: PAPER_TRADING</span>
                <span class="badge badge-live-disabled p-2 fs-6 ms-2">LIVE TRADING: DISABLED</span>
                <button id="btnEmergency" class="btn btn-danger btn-sm ms-3" onclick="triggerEmergencyStop()">🚨 EMERGENCY STOP</button>
            </div>
        </div>

        <!-- Metrics Overview Row -->
        <div class="row">
            <div class="col-md-2">
                <div class="card p-3">
                    <div class="metric-title">Total Equity</div>
                    <div class="metric-value" id="valEquity">Rp 0</div>
                    <small id="valEquityDiff" class="text-secondary">0.0%</small>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card p-3">
                    <div class="metric-title">Available IDR</div>
                    <div class="metric-value" id="valAvailableIdr">Rp 0</div>
                    <small id="valReservePct" class="text-secondary">Reserve: 100%</small>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card p-3">
                    <div class="metric-title">Capital Tier</div>
                    <div class="metric-value text-info" id="valCapitalTier">TIER 1</div>
                    <small id="valTierCap" class="text-secondary">Cap: 40% per asset</small>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card p-3">
                    <div class="metric-title">Portfolio Exposure</div>
                    <div class="metric-value" id="valExposure">0.0%</div>
                    <small class="text-secondary">Max Limit: 80%</small>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card p-3">
                    <div class="metric-title">Combined Portfolio Risk</div>
                    <div class="metric-value" id="valPortfolioRisk">0.0%</div>
                    <small class="text-secondary">Max Budget: 2.0%</small>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card p-3">
                    <div class="metric-title">Daily PnL / Loss</div>
                    <div class="metric-value" id="valDailyPnL">Rp 0</div>
                    <small id="valDailyLossPct" class="text-secondary">Limit: 2.0%</small>
                </div>
            </div>
        </div>

        <!-- Interactive Manual Buy Order Form & Open Positions Row -->
        <div class="row">
            <!-- Manual Buy Order Card -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-dark text-success">🟢 MANUAL BUY ORDER PANEL</div>
                    <div class="card-body">
                        <div class="mb-2">
                            <label class="form-label text-secondary mb-1">Select Pair / Symbol:</label>
                            <input type="text" id="buyPairInput" class="form-control bg-dark text-light border-secondary" placeholder="e.g. btcidr, ethidr, orderlyidr" value="btcidr">
                        </div>
                        <div class="mb-2">
                            <label class="form-label text-secondary mb-1">Order Amount (IDR):</label>
                            <input type="number" id="buyAmountInput" class="form-control bg-dark text-light border-secondary" value="1000000" step="100000">
                        </div>
                        <div class="mb-3">
                            <label class="form-label text-secondary mb-1">Strategy Engine Tag:</label>
                            <select id="buyEngineSelect" class="form-select bg-dark text-light border-secondary">
                                <option value="MANUAL_ORDER">MANUAL_ORDER</option>
                                <option value="ENGINE_A_SCALPER">ENGINE_A_SCALPER</option>
                                <option value="ENGINE_B_MOMENTUM_HUNTER">ENGINE_B_MOMENTUM_HUNTER</option>
                            </select>
                        </div>
                        <button class="btn btn-success w-100 fw-bold" onclick="executeManualBuy()">🟢 EXECUTE PAPER BUY NOW</button>
                    </div>
                </div>
            </div>

            <!-- Open Positions Table Card -->
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>ACTIVE OPEN POSITIONS</span>
                        <span id="openPosCount" class="badge bg-secondary">0 Positions</span>
                    </div>
                    <div class="card-body p-0 table-responsive">
                        <table class="table table-dark table-hover m-0 fs-7">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Engine</th>
                                    <th>Entry Price</th>
                                    <th>Current Price</th>
                                    <th>Size (IDR)</th>
                                    <th>Stop Loss</th>
                                    <th>Unrealized PnL</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="tblOpenPositions">
                                <tr><td colspan="8" class="text-center text-secondary py-3">No active open positions</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Candidate Ranking Tables -->
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">ENGINE A CANDIDATES — PURE SCALPER (1m/5m/15m)</div>
                    <div class="card-body p-0 table-responsive">
                        <table class="table table-dark table-hover m-0 fs-7">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Price</th>
                                    <th>RVOL</th>
                                    <th>ROC</th>
                                    <th>Est Net Return</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="tblEngineA">
                                <tr><td colspan="6" class="text-center text-secondary py-3">Scanning market...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">ENGINE B CANDIDATES — MOMENTUM HUNTER (15m/1h/4h)</div>
                    <div class="card-body p-0 table-responsive">
                        <table class="table table-dark table-hover m-0 fs-7">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Price</th>
                                    <th>Score (0-100)</th>
                                    <th>Spread %</th>
                                    <th>Est Net Return</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="tblEngineB">
                                <tr><td colspan="6" class="text-center text-secondary py-3">Scanning market...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Rejections and API Health Footer -->
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">REJECTED TRADES & RISK REJECTION REASONS LOG</div>
                    <div class="card-body p-0">
                        <ul class="list-group list-group-flush bg-dark" id="listRejections" style="max-height: 150px; overflow-y: auto;">
                            <li class="list-group-item bg-dark text-secondary">No trades rejected yet</li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">INDODAX API & SYSTEM HEALTH</div>
                    <div class="card-body">
                        <div>API Status: <span id="valApiStatus" class="badge bg-success">HEALTHY</span></div>
                        <div>Success Rate: <span id="valApiSuccess">100%</span></div>
                        <div>Latency: <span id="valApiLatency">0 ms</span></div>
                        <div>Emergency Stop: <span id="valEmergencyStatus" class="badge bg-secondary">OFF</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function formatIDR(val) {
            return "Rp " + Math.round(val).toLocaleString("id-ID");
        }

        async function fetchStatus() {
            try {
                const res = await fetch("/api/status");
                if (!res.ok) return;
                const data = await res.json();
                updateDashboard(data);
            } catch (e) {
                console.error("Dashboard update error:", e);
            }
        }

        function updateDashboard(d) {
            document.getElementById("valEquity").innerText = formatIDR(d.portfolio.equity);
            document.getElementById("valAvailableIdr").innerText = formatIDR(d.portfolio.cash);
            document.getElementById("valReservePct").innerText = "Cash Reserve: " + d.portfolio.cash_reserve_pct.toFixed(1) + "%";
            document.getElementById("valCapitalTier").innerText = d.portfolio.capital_tier;
            document.getElementById("valExposure").innerText = d.portfolio.exposure_pct.toFixed(1) + "%";
            document.getElementById("valPortfolioRisk").innerText = d.portfolio.combined_planned_risk_pct.toFixed(2) + "%";
            document.getElementById("valDailyPnL").innerText = formatIDR(d.portfolio.daily_pnl_idr);
            document.getElementById("valDailyLossPct").innerText = "Daily Loss: " + d.portfolio.daily_loss_pct.toFixed(2) + "%";

            // Open Positions
            const tblPos = document.getElementById("tblOpenPositions");
            document.getElementById("openPosCount").innerText = d.open_positions.length + " Positions";
            if (d.open_positions.length === 0) {
                tblPos.innerHTML = '<tr><td colspan="8" class="text-center text-secondary py-3">No active open positions</td></tr>';
            } else {
                let html = "";
                d.open_positions.forEach(p => {
                    const pnlClass = p.unrealized_pnl >= 0 ? "positive" : "negative";
                    html += `<tr>
                        <td><strong>${p.symbol}</strong></td>
                        <td><span class="badge bg-info">${p.engine}</span></td>
                        <td>${formatIDR(p.entry_price)}</td>
                        <td>${formatIDR(p.current_price)}</td>
                        <td>${formatIDR(p.position_size_idr)}</td>
                        <td>${formatIDR(p.stop_loss_price)}</td>
                        <td class="${pnlClass}">${formatIDR(p.unrealized_pnl)} (${(p.unrealized_pnl_pct*100).toFixed(2)}%)</td>
                        <td>
                            <button class="btn btn-danger btn-sm py-0 px-2 fw-bold" onclick="executeManualSell('${p.position_id}')">🔴 SELL NOW</button>
                        </td>
                    </tr>`;
                });
                tblPos.innerHTML = html;
            }

            // Engine A Candidates
            const tblA = document.getElementById("tblEngineA");
            if (!d.candidates_engine_a || d.candidates_engine_a.length === 0) {
                tblA.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-3">No valid Engine A candidates</td></tr>';
            } else {
                let htmlA = "";
                d.candidates_engine_a.forEach(c => {
                    htmlA += `<tr>
                        <td><strong>${c.symbol}</strong></td>
                        <td>${formatIDR(c.entry_price)}</td>
                        <td>${c.rvol.toFixed(1)}</td>
                        <td>${c.roc_pct.toFixed(1)}%</td>
                        <td class="positive">+${(c.expected_net_return_pct*100).toFixed(2)}%</td>
                        <td>
                            <button class="btn btn-success btn-sm py-0 px-2 fw-bold" onclick="quickBuy('${c.pair_id}', 'ENGINE_A_SCALPER')">🟢 BUY</button>
                        </td>
                    </tr>`;
                });
                tblA.innerHTML = htmlA;
            }

            // Engine B Candidates
            const tblB = document.getElementById("tblEngineB");
            if (!d.candidates_engine_b || d.candidates_engine_b.length === 0) {
                tblB.innerHTML = '<tr><td colspan="6" class="text-center text-secondary py-3">No valid Engine B candidates</td></tr>';
            } else {
                let htmlB = "";
                d.candidates_engine_b.forEach(c => {
                    const spread = c.spread_pct ? (c.spread_pct * 100).toFixed(2) : "0.0";
                    htmlB += `<tr>
                        <td><strong>${c.symbol}</strong></td>
                        <td>${formatIDR(c.entry_price)}</td>
                        <td><span class="badge bg-primary fs-6">${c.score}/100</span></td>
                        <td>${spread}%</td>
                        <td class="positive">+${(c.expected_net_return_pct*100).toFixed(2)}%</td>
                        <td>
                            <button class="btn btn-success btn-sm py-0 px-2 fw-bold" onclick="quickBuy('${c.pair_id}', 'ENGINE_B_MOMENTUM_HUNTER')">🟢 BUY</button>
                        </td>
                    </tr>`;
                });
                tblB.innerHTML = htmlB;
            }

            // Rejections
            const listRej = document.getElementById("listRejections");
            if (!d.rejected_trades || d.rejected_trades.length === 0) {
                listRej.innerHTML = '<li class="list-group-item bg-dark text-secondary">No trades rejected</li>';
            } else {
                let htmlR = "";
                d.rejected_trades.slice().reverse().forEach(r => {
                    htmlR += `<li class="list-group-item bg-dark text-warning py-1 px-3 fs-7">
                        [${r.pair_id || 'GENERAL'}] via ${r.engine || 'RISK_CTRL'}: ${r.reason}
                    </li>`;
                });
                listRej.innerHTML = htmlR;
            }

            // API Health
            document.getElementById("valApiStatus").innerText = d.api_health.status;
            document.getElementById("valApiSuccess").innerText = d.api_health.success_rate_pct + "%";
            document.getElementById("valApiLatency").innerText = d.api_health.last_latency_ms + " ms";
            if (d.emergency_stop) {
                document.getElementById("valEmergencyStatus").className = "badge bg-danger";
                document.getElementById("valEmergencyStatus").innerText = "ACTIVATED";
            }
        }

        async function executeManualBuy() {
            const pair_id = document.getElementById("buyPairInput").value;
            const size_idr = parseFloat(document.getElementById("buyAmountInput").value);
            const engine = document.getElementById("buyEngineSelect").value;

            if (!pair_id || size_idr <= 0) {
                alert("Please enter a valid pair and order amount.");
                return;
            }

            const res = await fetch("/api/manual_buy", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pair_id, size_idr, engine })
            });

            const data = await res.json();
            if (data.success) {
                alert("🟢 PAPER BUY EXECUTED SUCCESSFULLY for " + pair_id.toUpperCase());
                fetchStatus();
            } else {
                alert("❌ BUY ORDER REJECTED: " + (data.reason || "Unknown error"));
            }
        }

        async function quickBuy(pair_id, engine) {
            document.getElementById("buyPairInput").value = pair_id;
            document.getElementById("buyEngineSelect").value = engine;
            await executeManualBuy();
        }

        async function executeManualSell(position_id) {
            if (!confirm("Are you sure you want to SELL / CLOSE this position immediately at current market price?")) {
                return;
            }

            const res = await fetch("/api/manual_sell", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ position_id, reason: "MANUAL_SELL_DASHBOARD" })
            });

            const data = await res.json();
            if (data.success) {
                alert("🔴 POSITION CLOSED SUCCESSFULLY!");
                fetchStatus();
            } else {
                alert("❌ SELL ORDER REJECTED: " + (data.reason || "Unknown error"));
            }
        }

        async function triggerEmergencyStop() {
            if (confirm("Are you sure you want to activate EMERGENCY STOP? New trade entries will be stopped immediately.")) {
                await fetch("/api/emergency_stop", { method: "POST" });
                alert("Emergency Stop Activated!");
                fetchStatus();
            }
        }

        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
"""
