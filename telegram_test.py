import asyncio
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text='اختبار تنبيه من البوت - هل يصلك؟')

if __name__ == "__main__":
    asyncio.run(main())
