from logger import setup_logger
from trading_bot import TradingBot

if __name__ == "__main__":
    setup_logger()
    import asyncio
    bot = TradingBot()
    asyncio.run(bot.start())