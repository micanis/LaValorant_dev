# scheduler/daily_tasks.py (更新後の全文)
import asyncio
import discord
import aiohttp

from config import settings
from db.database import get_db_client
from db.user_repository import UserRepository
from db.activity_log_repository import ActivityLogRepository  # <--- インポート
from api_clients.riot_api_client import RiotApiClient
from services.rank_service import RankService
from services.activity_service import ActivityService  # <--- インポート


class DailyTaskRunner:
    """
    定期実行タスクを起動するためのクラス
    """

    def __init__(self):
        # 依存関係をここで解決・インスタンス化
        self.bot = discord.Client(intents=discord.Intents.default())
        self.db_client = get_db_client()

        # Repository層
        self.user_repo = UserRepository(self.db_client, settings.ENCRYPTION_KEY)
        self.activity_log_repo = ActivityLogRepository(self.db_client)  # <--- 追記

        # APIクライアント層
        self.aiohttp_session = aiohttp.ClientSession()
        self.riot_api_client = RiotApiClient(
            self.aiohttp_session,
            settings.RIOT_API_KEY,
            settings.RIOT_CLIENT_ID,
            settings.RIOT_CLIENT_SECRET,
            settings.RIOT_REDIRECT_URI,
        )

        # Service層
        self.rank_service = RankService(self.user_repo, self.riot_api_client)
        self.activity_service = ActivityService(
            self.user_repo, self.activity_log_repo
        )  # <--- 追記

    async def run_all_tasks(self):
        """
        全てのデイリータスクを実行する
        """
        await self.bot.login(settings.DISCORD_BOT_TOKEN)
        try:
            guild = await self.bot.fetch_guild(int(settings.DISCORD_GUILD_ID))
            if not guild:
                print(f"Error: Guild with ID {settings.DISCORD_GUILD_ID} not found.")
                return

            print("--- Running Daily Tasks ---")
            # 1. ランク更新タスクの実行
            await self.rank_service.update_all_user_ranks(guild)

            # 2. 活動評価ロール付与タスクの実行
            await self.activity_service.update_activity_roles(guild)  # <--- 追記
            print("--- Daily Tasks Finished ---")

        finally:
            await self.aiohttp_session.close()
            await self.bot.close()


if __name__ == "__main__":
    if not settings.DISCORD_GUILD_ID:
        raise ValueError("DISCORD_GUILD_ID must be set in your .env file.")

    runner = DailyTaskRunner()
    asyncio.run(runner.run_all_tasks())
