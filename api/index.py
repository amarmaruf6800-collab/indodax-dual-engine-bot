"""
Vercel Serverless Function Entry Point for Indodax Dual Engine Dashboard.
"""

from indodax_bot.main import IndodaxBotController
from indodax_bot.web_dashboard import create_dashboard_app

bot = IndodaxBotController(initial_cash_idr=10_000_000.0)
app = create_dashboard_app(bot)
