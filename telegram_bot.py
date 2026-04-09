from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from logger import logger

class TelegramBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.chat_id = TELEGRAM_CHAT_ID

    async def send_message(self, message):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            logger.info("Telegram message sent")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def send_signal_alert(self, coin, market_condition, score, entry_price, tp1, tp2, tp3, sl, news_status, timestamp):
        condition_ar = {'TRENDING_UP': 'صاعد', 'SIDEWAYS': 'عرضي'}[market_condition]
        news_ar = 'لا أخبار سلبية' if news_status else '⚠️ يوجد أخبار — توخ الحذر'
        message = f"""
🎯 إشارة جديدة

العملة: {coin}
حال السوق: {condition_ar}
قوة الإشارة: {score}/100

💰 سعر الدخول: ${entry_price:.2f}
🎯 TP1: ${tp1:.2f} (+1.5%)
🎯 TP2: ${tp2:.2f} (+3.0%)
🎯 TP3: ${tp3:.2f} (+4.5%)
🛑 Stop Loss: ${sl:.2f} (-2%)

📰 الأخبار: {news_ar}
⏰ الوقت: {timestamp}
        """.strip()
        await self.send_message(message)

    async def send_status_report(self, market_condition, opportunities, open_trades, capital_used, timestamp):
        condition_ar = {'TRENDING_UP': 'صاعد', 'SIDEWAYS': 'عرضي', 'TRENDING_DOWN': 'هابط'}.get(market_condition, 'غير محدد')
        message = f"""
🤖 تقرير النظام

✅ البوت يعمل بشكل طبيعي
📊 حال السوق العام: {condition_ar}
🔍 فرص رُصدت منذ آخر تقرير: {opportunities}
📈 صفقات مفتوحة حالياً: {open_trades}
💼 رأس المال المستخدم: ${capital_used:.2f}
⏰ {timestamp}
        """.strip()
        await self.send_message(message)

    async def send_emergency_alert(self, coin, drop_pct, timestamp):
        message = f"""
⚠️ تحذير عاجل

العملة: {coin}
هبوط مفاجئ: {drop_pct:.1f}%
خلال آخر 60 دقيقة
 🔴 راجع صفقاتك المفتوحة فوراً
⏰ {timestamp}
        """.strip()
        await self.send_message(message)

    async def send_weekly_report(self, date_range, total_trades, wins, losses, win_rate, pnl, best_coin, worst_coin):
        message = f"""
📊 التقرير الأسبوعي

📅 الأسبوع: {date_range}

إجمالي الصفقات: {total_trades}
✅ ناجحة: {wins}
❌ خاسرة: {losses}
📊 نسبة النجاح: {win_rate:.1f}%

💰 إجمالي الربح/الخسارة: ${pnl:.2f}
📈 أفضل عملة هذا الأسبوع: {best_coin}
📉 أسوأ عملة هذا الأسبوع: {worst_coin}
        """.strip()
        await self.send_message(message)

    async def send_trading_pause(self, resume_time):
        message = f"""
🚫 إيقاف مؤقت للتداول

السبب: 3 خسائر متتالية
مدة الإيقاف: 24 ساعة
استئناف التداول: {resume_time}

💡 راجع الظروف العامة للسوق خلال هذه الفترة
        """.strip()
        await self.send_message(message)

    async def send_buy_execution(self, coin, price, amount, tp1, tp2, tp3, sl, timestamp):
        message = f"""
✅ تم تنفيذ أمر الشراء

العملة: {coin}
السعر: ${price:.2f}
الكمية: {amount:.4f}
🎯 TP1: ${tp1:.2f} (+1.5%)
🎯 TP2: ${tp2:.2f} (+3.0%)
🎯 TP3: ${tp3:.2f} (+4.5%)
🛑 Stop Loss: ${sl:.2f} (-2%)
⏰ {timestamp}
        """.strip()
        await self.send_message(message)

    async def send_tp_hit(self, coin, tp_level, price, profit_pct, timestamp):
        message = f"""
🎯 تم تحقيق الهدف

العملة: {coin}
الهدف: {tp_level}
سعر البيع: ${price:.2f}
الربح: +{profit_pct:.2f}%
⏰ {timestamp}
        """.strip()
        await self.send_message(message)

    async def send_sl_hit(self, coin, price, loss_pct, timestamp):
        message = f"""
🛑 تم تفعيل وقف الخسارة

العملة: {coin}
سعر البيع: ${price:.2f}
الخسارة: -{loss_pct:.2f}%
⏰ {timestamp}
        """.strip()
        await self.send_message(message)