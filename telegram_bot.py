import asyncio
from datetime import datetime, timezone
from telegram import Bot
from telegram.error import TelegramError
from logger import get_logger
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = get_logger("telegram_bot")


def _get_bot() -> Bot:
    return Bot(token=TELEGRAM_BOT_TOKEN)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _send_async(text: str):
    try:
        bot = _get_bot()
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="HTML",
        )
    except TelegramError as e:
        log.error(f"Telegram send failed: {e}")


def send_message(text: str):
    try:
        asyncio.get_event_loop().run_until_complete(_send_async(text))
    except RuntimeError:
        # Already running event loop (e.g. inside APScheduler)
        import threading
        t = threading.Thread(target=lambda: asyncio.run(_send_async(text)))
        t.start()
        t.join()


# ─── Alert 1: New Signal ─────────────────────────────────────────────────────
def alert_new_signal(coin: str, condition: str, score: int, entry: float,
                     tp1: float, tp2: float, tp3: float, sl: float,
                     adx: float, plus_di: float, minus_di: float):
    cond_ar = "صاعد" if condition == "TRENDING_UP" else "عرضي"
    di_check = "✅" if plus_di > minus_di else "❌"
    text = (
        f"🎯 <b>إشارة جديدة</b>\n\n"
        f"#{coin} | {cond_ar}\n"
        f"⭐ القوة: {score}/100\n\n"
        f"💰 سعر الدخول: ${entry:,.4f}\n"
        f"🎯 TP1: ${tp1:,.4f} (+2.5%)\n"
        f"🎯 TP2: ${tp2:,.4f} (+3.5%)\n"
        f"🎯 TP3: ${tp3:,.4f} (+4.5%)\n"
        f"🛑 Stop Loss: ${sl:,.4f} (-2.0%)\n\n"
        f"📊 ADX: {adx:.1f} | DI+>DI-: {di_check}\n"
        f"⏰ {_now_utc()}"
    )
    send_message(text)


# ─── Alert 2: Buy Executed ───────────────────────────────────────────────────
def alert_buy_executed(coin: str, price: float, amount_usd: float,
                       tp1: float, tp2: float, tp3: float, sl: float):
    text = (
        f"✅ <b>تم تنفيذ أمر الشراء</b>\n\n"
        f"#{coin}\n"
        f"💰 سعر الشراء: ${price:,.4f}\n"
        f"📊 الكمية: ${amount_usd:,.2f}\n"
        f"🎯 TP1: ${tp1:,.4f} | TP2: ${tp2:,.4f} | TP3: ${tp3:,.4f}\n"
        f"🛑 Stop Loss: ${sl:,.4f}\n"
        f"⏰ {_now_utc()}"
    )
    send_message(text)


# ─── Alert 3: Take Profit Hit ────────────────────────────────────────────────
def alert_tp_hit(coin: str, tp_label: str, price: float, profit_pct: float):
    text = (
        f"🎯 <b>تم تحقيق الهدف!</b>\n\n"
        f"#{coin}\n"
        f"✅ {tp_label} تم الوصول\n"
        f"💵 سعر البيع: ${price:,.4f}\n"
        f"📈 الربح: +{profit_pct:.2f}%\n"
        f"⏰ {_now_utc()}"
    )
    send_message(text)


# ─── Alert 4: Stop Loss Hit ──────────────────────────────────────────────────
def alert_sl_hit(coin: str, price: float, loss_pct: float):
    text = (
        f"🛑 <b>وقف الخسارة</b>\n\n"
        f"#{coin}\n"
        f"💵 سعر البيع: ${price:,.4f}\n"
        f"📉 الخسارة: -{loss_pct:.2f}%\n"
        f"⏰ {_now_utc()}"
    )
    send_message(text)


# ─── Alert 5: Status Report (every 12h) ─────────────────────────────────────
def alert_status_report(up_count: int, sideways_count: int, down_count: int,
                        signals_count: int, open_trades: int, daily_loss: float):
    text = (
        f"🤖 <b>تقرير النظام</b>\n\n"
        f"✅ البوت يعمل بشكل طبيعي\n"
        f"📊 حال السوق: ↑{up_count} ↔{sideways_count} ↓{down_count}\n"
        f"🔍 إشارات منذ آخر تقرير: {signals_count}\n"
        f"📈 صفقات مفتوحة: {open_trades}\n"
        f"💸 خسارة اليوم: ${daily_loss:,.2f}\n"
        f"⏰ {_now_utc()}"
    )
    send_message(text)


# ─── Alert 6: Emergency Drop ────────────────────────────────────────────────
def alert_emergency_drop(coin: str, drop_pct: float):
    text = (
        f"⚠️ <b>تحذير عاجل</b>\n\n"
        f"#{coin}\n"
        f"📉 هبوط مفاجئ: {drop_pct:.1f}%\n"
        f"خلال آخر 60 دقيقة\n\n"
        f"🔴 راجع صفقاتك فوراً\n"
        f"⏰ {_now_utc()}"
    )
    send_message(text)


# ─── Alert 7: Weekly Report ──────────────────────────────────────────────────
def alert_weekly_report(date_range: str, total: int, wins: int, losses: int,
                        rate: float, pnl: float, best: str, worst: str):
    text = (
        f"📊 <b>التقرير الأسبوعي</b>\n\n"
        f"📅 {date_range}\n"
        f"إجمالي الصفقات: {total}\n"
        f"✅ ناجحة: {wins} | ❌ خاسرة: {losses}\n"
        f"📊 نسبة النجاح: {rate:.1f}%\n"
        f"💰 الربح/الخسارة: ${pnl:+,.2f}\n"
        f"🏆 أفضل عملة: #{best}\n"
        f"📉 أسوأ عملة: #{worst}"
    )
    send_message(text)


# ─── Alert 8: Cooldown ───────────────────────────────────────────────────────
def alert_cooldown(loss_number: int, hours: int, resume_time: str):
    hours_ar = f"{hours} ساعة" if hours == 1 else f"{hours} ساعات" if hours < 11 else f"{hours} ساعة"
    text = (
        f"⏸ <b>إيقاف مؤقت</b>\n\n"
        f"السبب: خسارة رقم {loss_number}\n"
        f"مدة الانتظار: {hours_ar}\n"
        f"الاستئناف: {resume_time} UTC"
    )
    send_message(text)


# ─── Alert 9: Daily Limit Hit ────────────────────────────────────────────────
def alert_daily_limit(amount: float, resume_date: str):
    text = (
        f"⛔ <b>تم إيقاف التداول اليومي</b>\n\n"
        f"السبب: تجاوز حد الخسارة اليومي 5%\n"
        f"الخسارة اليوم: ${amount:,.2f}\n"
        f"الاستئناف: غداً {resume_date} الساعة 00:00 UTC"
    )
    send_message(text)


# ─── Alert 10: Weekly Limit Hit ─────────────────────────────────────────────
def alert_weekly_limit(amount: float, resume_date: str):
    text = (
        f"🚫 <b>تم إيقاف التداول الأسبوعي</b>\n\n"
        f"السبب: تجاوز حد الخسارة الأسبوعي 10%\n"
        f"الخسارة هذا الأسبوع: ${amount:,.2f}\n"
        f"الاستئناف: {resume_date} الساعة 00:00 UTC"
    )
    send_message(text)
