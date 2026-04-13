import time
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import database as db
import market_analyzer as ma
import trading_bot as bot
import telegram_bot as tg
from config import COINS, SCAN_INTERVAL_MINUTES, MIN_SIGNAL_SCORE, MAX_OPEN_TRADES
from logger import get_logger

log = get_logger("main")

# Track last status report time for counting signals
_last_status_time: datetime = datetime.now(timezone.utc)
_status_market_counts: dict = {"up": 0, "sideways": 0, "down": 0}


def scan_coins():
    global _status_market_counts

    tradeable, reason = bot.can_trade()
    if not tradeable:
        log.info(f"Trading paused: {reason}")
        return

    up = sideways = down = 0

    for coin in COINS:
        try:
            market = ma.get_market_condition(coin)
            condition = market["condition"]

            if condition == "TRENDING_DOWN":
                down += 1
                log.info(f"{coin}: TRENDING_DOWN — skipped")
                continue

            if condition == "TRENDING_UP":
                up += 1
            else:
                sideways += 1

            if not bot.can_send_alert(coin):
                log.info(f"{coin}: alert cooldown active — skipped")
                continue

            signal = ma.calculate_signal(coin, condition, market.get("support"))
            score = signal.get("score", 0)
            current_price = signal.get("current_price")
            log.info(f"{coin}: score={score} condition={condition}")

            if score >= MIN_SIGNAL_SCORE and current_price:
                open_count = db.get_open_trades_count()
                if open_count >= MAX_OPEN_TRADES:
                    log.info(f"Max trades open ({open_count}). Skipping {coin}.")
                    continue

                entry = current_price
                from config import TP1_PCT, TP2_PCT, TP3_PCT, STOP_LOSS_PCT, TRADE_SIZE_USD
                tp1 = round(entry * (1 + TP1_PCT), 6)
                tp2 = round(entry * (1 + TP2_PCT), 6)
                tp3 = round(entry * (1 + TP3_PCT), 6)
                sl = round(entry * (1 - STOP_LOSS_PCT), 6)

                # Alert 1: signal
                tg.alert_new_signal(
                    coin=coin,
                    condition=condition,
                    score=score,
                    entry=entry,
                    tp1=tp1, tp2=tp2, tp3=tp3, sl=sl,
                    adx=signal.get("adx", 0),
                    plus_di=signal.get("plus_di", 0),
                    minus_di=signal.get("minus_di", 0),
                )

                trade = bot.open_trade(coin, current_price)
                if trade:
                    bot.record_alert(coin)
                    # Alert 2: executed
                    tg.alert_buy_executed(
                        coin=coin,
                        price=trade["entry_price"],
                        amount_usd=TRADE_SIZE_USD,
                        tp1=trade["tp1"],
                        tp2=trade["tp2"],
                        tp3=trade["tp3"],
                        sl=trade["sl"],
                    )

        except Exception as e:
            log.error(f"Error scanning {coin}: {e}")

    _status_market_counts = {"up": up, "sideways": sideways, "down": down}

    # Monitor open trades
    try:
        events = bot.monitor_trades(tg)
        _process_trade_events(events)
    except Exception as e:
        log.error(f"Error monitoring trades: {e}")

    # Emergency drop check
    for coin in COINS:
        try:
            drop = ma.check_emergency_drop(coin)
            if drop:
                tg.alert_emergency_drop(coin, drop)
        except Exception as e:
            log.error(f"Emergency drop check error for {coin}: {e}")


def _process_trade_events(events: list):
    for event in events:
        etype = event.get("type")
        coin = event.get("coin", "")

        if etype in ("tp1", "tp2", "tp3"):
            label = etype.upper()
            tg.alert_tp_hit(coin, label, event["price"], event["profit_pct"])

        elif etype == "sl":
            tg.alert_sl_hit(coin, event["price"], event["loss_pct"])
            losses = event["consecutive_losses"]
            from config import COOLDOWN_AFTER_LOSS
            hours = COOLDOWN_AFTER_LOSS.get(losses, 24)
            resume = event["cooldown_until"]
            resume_str = resume.strftime("%Y-%m-%d %H:%M") if resume else "—"
            tg.alert_cooldown(losses, hours, resume_str)

        elif etype == "daily_limit":
            tg.alert_daily_limit(event["daily_loss"], event["resume"].strftime("%Y-%m-%d"))

        elif etype == "weekly_limit":
            tg.alert_weekly_limit(event["weekly_loss"], event["resume"].strftime("%Y-%m-%d"))


def send_status_report():
    global _last_status_time
    state = bot.get_state()
    signals = db.get_signals_since(_last_status_time)
    tg.alert_status_report(
        up_count=_status_market_counts.get("up", 0),
        sideways_count=_status_market_counts.get("sideways", 0),
        down_count=_status_market_counts.get("down", 0),
        signals_count=signals,
        open_trades=state["open_trades"],
        daily_loss=state["daily_loss"],
    )
    _last_status_time = datetime.now(timezone.utc)


def send_weekly_report():
    stats = db.get_weekly_stats()
    today = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    date_range = f"{monday.strftime('%Y-%m-%d')} → {today.strftime('%Y-%m-%d')}"
    tg.alert_weekly_report(
        date_range=date_range,
        total=stats["total"],
        wins=stats["wins"],
        losses=stats["losses"],
        rate=stats["rate"],
        pnl=stats["pnl"],
        best=stats["best"],
        worst=stats["worst"],
    )


def main():
    log.info("Bot starting — initializing DB")
    db.init_db()

    try:
        tg.send_message("✅ تم تشغيل Almaany Bot بنجاح. سيتم بدء الفحص الآن.")
    except Exception as e:
        log.error(f"Startup Telegram heartbeat failed: {e}")

    scheduler = BackgroundScheduler(timezone="UTC")

    # Scan every 15 minutes
    scheduler.add_job(
        scan_coins,
        trigger=IntervalTrigger(minutes=SCAN_INTERVAL_MINUTES),
        id="scan_coins",
        replace_existing=True,
        max_instances=1,
    )

    # Status report every 12 hours
    scheduler.add_job(
        send_status_report,
        trigger=IntervalTrigger(hours=12),
        id="status_report",
        replace_existing=True,
    )

    # Weekly report every Sunday 08:00 UTC
    scheduler.add_job(
        send_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=8, minute=0),
        id="weekly_report",
        replace_existing=True,
    )

    scheduler.start()
    log.info(f"Scheduler started. Scanning every {SCAN_INTERVAL_MINUTES} minutes.")

    # Run one scan immediately
    scan_coins()

    # Send one immediate status report on startup for quick health verification.
    try:
        send_status_report()
    except Exception as e:
        log.error(f"Immediate startup status report failed: {e}")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopping.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
