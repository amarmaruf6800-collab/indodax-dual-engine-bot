"""
Vercel Serverless Function Gateway for Indodax Dual Engine Dashboard.
Proxies requests seamlessly to the live 24/7 VPS Trading Bot Engine (http://103.58.101.236:8080).
"""

import sys
import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

# Add parent directory to sys.path so indodax_bot import works on Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VPS_BACKEND_URL = os.getenv("VPS_BACKEND_URL", "http://103.58.101.236:8080")

app = FastAPI(title="Indodax Dual Engine Vercel Gateway")

@app.get("/api/status")
def proxy_status():
    try:
        resp = requests.get(f"{VPS_BACKEND_URL}/api/status", timeout=6)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"error": f"Unable to connect to VPS Trading Engine at {VPS_BACKEND_URL}: {str(e)}"},
            status_code=502
        )

@app.post("/api/emergency_stop")
def proxy_emergency():
    try:
        resp = requests.post(f"{VPS_BACKEND_URL}/api/emergency_stop", timeout=6)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)

@app.post("/api/manual_buy")
def proxy_manual_buy(req: dict):
    try:
        resp = requests.post(f"{VPS_BACKEND_URL}/api/manual_buy", json=req, timeout=6)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)

@app.post("/api/manual_sell")
def proxy_manual_sell(req: dict):
    try:
        resp = requests.post(f"{VPS_BACKEND_URL}/api/manual_sell", json=req, timeout=6)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)

@app.get("/", response_class=HTMLResponse)
def get_html():
    from indodax_bot.web_dashboard import HTML_DASHBOARD_TEMPLATE
    return HTML_DASHBOARD_TEMPLATE
