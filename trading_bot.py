import time
import ccxt
from datetime import datetime, timezone, timedelta
from logger import get_logger
from config import (
    OKX_API_KEY, OKX_SECRET, OKX_PASSWORD,
    TRADE_SIZE_USD, MAX_OPEN_TRADES,
    STOP_LOSS_PCT, TP1_PCT, TP2_PCT, TP3_PCT,
    TP1_SELL_PCT, TP2_SELL_PCT, TP3_SELL_PCT,
    DAILY_LOSS_LIMIT_USD, WEEKLY_LOSS_LIMIT_USD,
    COOLDOWN_AFTER_LOSS, ALERT_COOLDOWN_HOURS,
    COINS,
)
import database as db

log = get_logger("trading_bot")

MAX_RETRIES = 3
RETRY_WAIT = 5

# ─── Alert deduplication ────────────────────────────────────────────────────
last_alert_time: dict[str, datetime] = {}


def can_send_alert(coin: str) -> bool:
    if coin not in last_alert_time:
        return True
    elapsed = (datetime.now(timezone.utc) - last_alert_time[coin]).total_seconds() / 3600
    return elapsed >= ALERT_COOLDOWN_HOURS


def record_alert(coin: str):
    last_alert_time[coin] = datetime.now(timezone.utc)


def reset_alert(coin: str):
    last_alert_time.pop(coin, None)


# ─── Loss management state ───────────────────────────────────────────────────
consecutive_losses: int = 0
cooldown_until: datetime | None = None
daily_stop_until: datetime | None = None
weekly_stop_until: datetime | None = None


def can_trade() -> tuple[bool, str]:
    now = datetime.now(timezone.utc)

    if daily_stop_until and now < daily_stop_until:
        return False, f"daily_limit|{daily_stop_until.strftime('%Y-%m-%d')} 00:00 UTC"

    if weekly_stop_until and now < weekly_stop_until:
        return False, f"weekly_limit|{weekly_stop_until.strftime('%Y-%m-%d')} 00:00 UTC"

    if cooldown_until and now < cooldown_until:
        return False, f"cooldown|{cooldown_until.strftime('%Y-%m-%d %H:%M UTC')}"

    return True, ""


def _get_exchange() -> ccxt.okx:
    return ccxt.okx({
        "apiKey": OKX_API_KEY,
        "secret": OKX_SECRET,
        "password": OKX_PASSWORD,
        "sandbox": True,
        "enableRateLimit": True,
        "headers": {"x-simulated-trading": "1"},
    })


def _place_buy_order_with_retry(exchange: ccxt.okx, symbol: str, quantity: float) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            order = exchange.create_market_buy_order(symbol, quantity)
            return order
        except Exception as e:
            log.warning(f"Buy order attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
    log.error(f"All buy order retries exhausted for {symbol}. Skipping.")
    return None


def _place_sell_order_with_retry(exchange: ccxt.okx, symbol: str, quantity: float) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            order = exchange.create_market_sell_order(symbol, quantity)
            return order
        except Exception as e:
            log.warning(f"Sell order attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
    log.error(f"All sell order retries exhausted for {symbol}. Skipping.")
    return None


def open_trade(coin: str, current_price: float) -> dict | None:
    global daily_stop_until, weekly_stop_until

    if db.get_open_trades_count() >= MAX_OPEN_TRADES:
        log.info(f"Max open trades reached. Skipping {coin}.")
        return None

    # Check daily / weekly loss limits before opening
    daily_loss = db.get_daily_loss_usd()
    if daily_loss >= DAILY_LOSS_LIMIT_USD:
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        daily_stop_until = tomorrow
        return None

    weekly_loss = db.get_weekly_loss_usd()
    if weekly_loss >= WEEKLY_LOSS_LIMIT_USD:
        today = datetime.now(timezone.utc)
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = (today + timedelta(days=days_until_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        weekly_stop_until = next_monday
        return None

    exchange = _get_exchange()
    symbol = f"{coin}/USDT"
    quantity = round(TRADE_SIZE_USD / current_price, 6)

    order = _place_buy_order_with_retry(exchange, symbol, quantity)
    if order is None:
        return None

    entry_price = float(order.get("average") or order.get("price") or current_price)
    tp1 = round(entry_price * (1 + TP1_PCT), 6)
    tp2 = round(entry_price * (1 + TP2_PCT), 6)
    tp3 = round(entry_price * (1 + TP3_PCT), 6)
    sl = round(entry_price * (1 - STOP_LOSS_PCT), 6)

    trade_id = db.insert_trade(
        coin=coin,
        entry_price=entry_price,
        quantity=quantity,
        tp1=tp1, tp2=tp2, tp3=tp3, sl=sl,
        order_id=str(order.get("id", "")),
    )

    log.info(f"Trade opened: {coin} @ {entry_price}, ID={trade_id}")
    return {
        "id": trade_id,
        "coin": coin,
        "entry_price": entry_price,
        "quantity": quantity,
        "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl,
        "order_id": order.get("id"),
    }


def monitor_trades(notify_callback) -> list[dict]:
    global consecutive_losses, cooldown_until, daily_stop_until, weekly_stop_until

    events = []
    open_trades = db.get_open_trades()

    for trade in open_trades:
        coin = trade["coin"]
        from market_analyzer import get_current_price
        current_price = get_current_price(coin)

        if current_price is None:
            continue

        trade_id = trade["id"]
        entry = trade["entry_price"]
        quantity = trade["quantity"]
        tp1 = trade["tp1_price"]
        tp2 = trade["tp2_price"]
        tp3 = trade["tp3_price"]
        sl = trade["sl_price"]
        sold_tp1 = bool(trade["sold_tp1"])
        sold_tp2 = bool(trade["sold_tp2"])

        exchange = _get_exchange()
        symbol = f"{coin}/USDT"

        # TP1
        if not sold_tp1 and current_price >= tp1:
            sell_qty = round(quantity * TP1_SELL_PCT, 6)
            order = _place_sell_order_with_retry(exchange, symbol, sell_qty)
            if order:
                db.update_trade_tp1(trade_id)
                # Move SL to breakeven
                db.get_connection().execute(
                    "UPDATE trades SET sl_price=? WHERE id=?", (entry, trade_id)
                )
                db.get_connection().commit()
                profit_pct = round(TP1_PCT * 100, 2)
                profit_usd = round(sell_qty * (current_price - entry), 2)
                events.append({
                    "type": "tp1",
                    "coin": coin,
                    "price": current_price,
                    "profit_pct": profit_pct,
                    "profit_usd": profit_usd,
                    "trade_id": trade_id,
                })
                log.info(f"TP1 hit {coin} @ {current_price}")

        # TP2
        elif sold_tp1 and not sold_tp2 and current_price >= tp2:
            sell_qty = round(quantity * TP2_SELL_PCT, 6)
            order = _place_sell_order_with_retry(exchange, symbol, sell_qty)
            if order:
                db.update_trade_tp2(trade_id)
                profit_pct = round(TP2_PCT * 100, 2)
                profit_usd = round(sell_qty * (current_price - entry), 2)
                events.append({
                    "type": "tp2",
                    "coin": coin,
                    "price": current_price,
                    "profit_pct": profit_pct,
                    "profit_usd": profit_usd,
                    "trade_id": trade_id,
                })
                log.info(f"TP2 hit {coin} @ {current_price}")

        # TP3 (close trade)
        elif sold_tp1 and sold_tp2 and current_price >= tp3:
            sell_qty = round(quantity * TP3_SELL_PCT, 6)
            order = _place_sell_order_with_retry(exchange, symbol, sell_qty)
            if order:
                total_pnl_pct = round((current_price - entry) / entry * 100, 2)
                total_pnl_usd = round(quantity * (current_price - entry), 2)
                db.close_trade(trade_id, current_price, total_pnl_pct, total_pnl_usd, "win")
                reset_alert(coin)
                consecutive_losses = 0
                events.append({
                    "type": "tp3",
                    "coin": coin,
                    "price": current_price,
                    "profit_pct": round(TP3_PCT * 100, 2),
                    "profit_usd": round(sell_qty * (current_price - entry), 2),
                    "trade_id": trade_id,
                })
                log.info(f"TP3 hit {coin} @ {current_price} — trade closed WIN")

        # SL hit
        elif current_price <= sl:
            remaining_qty = quantity
            if sold_tp1:
                remaining_qty -= round(quantity * TP1_SELL_PCT, 6)
            if sold_tp2:
                remaining_qty -= round(quantity * TP2_SELL_PCT, 6)
            remaining_qty = max(remaining_qty, 0)

            if remaining_qty > 0:
                _place_sell_order_with_retry(exchange, symbol, remaining_qty)

            loss_pct = round((entry - current_price) / entry * 100, 2)
            loss_usd = round(remaining_qty * (entry - current_price), 2)
            db.close_trade(trade_id, current_price, -loss_pct, -loss_usd, "loss")
            reset_alert(coin)

            consecutive_losses += 1

            # Cooldown logic
            pause_hours = COOLDOWN_AFTER_LOSS.get(consecutive_losses)
            if pause_hours:
                cooldown_until = datetime.now(timezone.utc) + timedelta(hours=pause_hours)
            else:
                # Loss #3+ always uses 24h
                cooldown_until = datetime.now(timezone.utc) + timedelta(hours=24)

            # Check daily/weekly limits
            daily_loss = db.get_daily_loss_usd()
            weekly_loss = db.get_weekly_loss_usd()

            events.append({
                "type": "sl",
                "coin": coin,
                "price": current_price,
                "loss_pct": loss_pct,
                "loss_usd": loss_usd,
                "trade_id": trade_id,
                "consecutive_losses": consecutive_losses,
                "cooldown_until": cooldown_until,
                "daily_loss": daily_loss,
                "weekly_loss": weekly_loss,
            })
            log.info(f"SL hit {coin} @ {current_price} — consecutive losses: {consecutive_losses}")

            # Daily limit
            if daily_loss >= DAILY_LOSS_LIMIT_USD:
                tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                daily_stop_until = tomorrow
                events.append({"type": "daily_limit", "daily_loss": daily_loss, "resume": tomorrow})

            # Weekly limit
            if weekly_loss >= WEEKLY_LOSS_LIMIT_USD:
                today = datetime.now(timezone.utc)
                days_until_monday = (7 - today.weekday()) % 7 or 7
                next_monday = (today + timedelta(days=days_until_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                weekly_stop_until = next_monday
                events.append({"type": "weekly_limit", "weekly_loss": weekly_loss, "resume": next_monday})

    return events


def get_state() -> dict:
    return {
        "open_trades": db.get_open_trades_count(),
        "consecutive_losses": consecutive_losses,
        "cooldown_until": cooldown_until,
        "daily_stop_until": daily_stop_until,
        "weekly_stop_until": weekly_stop_until,
        "daily_loss": db.get_daily_loss_usd(),
    }
