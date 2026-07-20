import logging
from pyrogram import Client
from config import Config

logging.basicConfig(level=logging.INFO)

class HardSubBot(Client):
    def __init__(self):
        super().__init__(
            "HardSubBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="plugins")
        )
        self.user_app = None
        if Config.STRING_SESSION:
            self.user_app = Client(
                "UserSession",
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                session_string=Config.STRING_SESSION
            )

    async def start(self):
        await super().start()
        if self.user_app:
            await self.user_app.start()
            logging.info("User session client started successfully (4GB upload enabled).")
        logging.info("HardSub Bot is running.")

    async def stop(self, *args):
        if self.user_app:
            await self.user_app.stop()
        await super().stop()

if __name__ == "__main__":
    bot = HardSubBot()
    bot.run()
