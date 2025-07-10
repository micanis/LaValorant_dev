# main.py (修正後の全文)

import asyncio
import os
import aiohttp
import uvicorn
import discord
from discord.ext import commands

from config import settings
from db.database import get_db_client
from db.user_repository import UserRepository
from db.recruitment_repository import RecruitmentRepository
from db.participant_repository import ParticipantRepository
from db.activity_log_repository import ActivityLogRepository
from api_clients.riot_api_client import RiotApiClient
from services.user_service import UserService
from services.recruitment_service import RecruitmentService
from views.recruitment_view import RecruitmentView
from web.server import app as fastapi_app


class LaValorantBot(commands.Bot):
    """
    Botのメインクラス。
    依存性の注入(DI)とコンポーネントの初期化を担う。
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

        # 依存関係のインスタンス化 (同期的なもの)
        self.db_client = get_db_client()
        self.user_repo = UserRepository(self.db_client, settings.ENCRYPTION_KEY)
        self.recruitment_repo = RecruitmentRepository(self.db_client)
        self.participant_repo = ParticipantRepository(self.db_client)
        self.activity_log_repo = ActivityLogRepository(self.db_client)

        # プレースホルダー
        self.aiohttp_session = None
        self.riot_api_client = None
        self.user_service = None
        self.recruitment_service = None

    async def setup_hook(self):
        print("Initializing components...")

        # 依存関係のインスタンス化 (非同期的なもの)
        self.aiohttp_session = aiohttp.ClientSession()
        self.riot_api_client = RiotApiClient(
            self.aiohttp_session,
            settings.RIOT_API_KEY,
            settings.RIOT_CLIENT_ID,
            settings.RIOT_CLIENT_SECRET,
            settings.RIOT_REDIRECT_URI,
        )
        self.user_service = UserService(self.user_repo, self.riot_api_client)
        self.recruitment_service = RecruitmentService(
            self.recruitment_repo, self.participant_repo, self.activity_log_repo
        )

        # FastAPIにUserServiceのインスタンスを渡す
        fastapi_app.state.user_service = self.user_service

        # 永続Viewの登録
        self.add_view(RecruitmentView(self.recruitment_service))

        print("Loading cogs...")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("__"):
                cog_name = filename[:-3]
                try:
                    # 【修正点】問題の2行を削除。
                    # Serviceは既にself(Botインスタンス)にアタッチされているため、
                    # Cog側はsetup(bot)のbot引数から bot.user_service のようにアクセスできる。
                    await self.load_extension(f"cogs.{cog_name}")
                    print(f"✅ Loaded cog: {cog_name}")
                except Exception as e:
                    print(f"❌ Failed to load cog: {cog_name}")
                    print(f"   Reason: {e}")

        # コマンドをDiscordサーバーに同期
        await self.tree.sync()

    async def on_ready(self):
        print("-" * 30)
        print(f"🚀 Bot is ready!")
        print(f"Logged in as: {self.user.name} (ID: {self.user.id})")
        print(f"🌐 Web server running on {settings.BASE_URL}")
        print("-" * 30)

    async def close(self):
        await super().close()
        if self.aiohttp_session:
            await self.aiohttp_session.close()


async def main():
    bot = LaValorantBot()

    uvicorn_config = uvicorn.Config(
        fastapi_app,
        host=settings.WEB_SERVER_HOST,
        port=settings.WEB_SERVER_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        await asyncio.gather(bot.start(settings.DISCORD_BOT_TOKEN), server.serve())
    except discord.errors.LoginFailure:
        print("FATAL: Invalid Discord Bot Token.")
    except Exception as e:
        print(f"FATAL: An unexpected error occurred: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        import fastapi, uvicorn, aiohttp, cryptography
    except ImportError:
        print("必要なライブラリが不足しています。以下を実行してください:")
        print("pip install fastapi uvicorn[standard] aiohttp cryptography")
        exit(1)

    asyncio.run(main())
