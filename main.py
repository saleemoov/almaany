import asyncio
from trading_bot import TradingBot
from logger import setup_logger

async def main():
    setup_logger()
    bot = TradingBot()
    try:
        await bot.start()
    finally:
        await bot.exchange.close()

if __name__ == "__main__":
    asyncio.run(main())