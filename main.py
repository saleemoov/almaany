# ELITE V9 Spot Trading Bot - Entry Point
from config import load_config
from telegram_bot import TelegramBot
from okx_client import OKXClient
from strategy import EliteV9Strategy
from risk_manager import RiskManager
from reports import ReportManager
from logger import get_logger
from database import init_db
import schedule
import time
import sys

logger = get_logger("main")

def main():
    try:
        init_db()
        config = load_config()
        telegram = TelegramBot(config)
        okx = OKXClient(config)
        db = __import__('database')
        config['db'] = db
        risk = RiskManager(config, db, telegram)
        strategy = EliteV9Strategy(config, okx, db, risk, telegram)
        reports = ReportManager(config, db, telegram)

        telegram.send_startup_alert()
        logger.info("ELITE V9 Bot started.")

        schedule.every(30).minutes.at(":00").do(strategy.run)
        schedule.every().day.at("00:00").do(reports.send_daily_report)
        schedule.every().sunday.at("00:00").do(reports.send_weekly_report)

        def monthly_report_wrapper():
            from datetime import datetime
            if datetime.now().day == 1:
                reports.send_monthly_report()
        schedule.every().day.at("00:00").do(monthly_report_wrapper)
        schedule.every(5).minutes.do(strategy.health_check)

        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
