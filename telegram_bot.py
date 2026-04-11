from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from logger import logger

class TelegramBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.chat_id = TELEGRAM_CHAT_ID

    def send(self, message):
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            logger.info("Telegram message sent")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")

    # All alert templates will be implemented in trading_bot.py and call self.send(...)