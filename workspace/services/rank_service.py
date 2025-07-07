# services/rank_service.py
import discord
from typing import List, Dict

from db.user_repository import UserRepository, User
from api_clients.riot_api_client import RiotApiClient

# VALORANTのランク階層を定義
# ロール名や順序の基準となる
RANK_TIERS = [
    "Unrated",
    "Iron",
    "Bronze",
    "Silver",
    "Gold",
    "Platinum",
    "Diamond",
    "Ascendant",
    "Immortal",
    "Radiant",
]


class RankService:
    """
    ランク情報の取得と、それに応じたDiscordロールの管理を責務に持つ
    """

    def __init__(self, user_repo: UserRepository, riot_client: RiotApiClient):
        self.user_repo = user_repo
        self.riot_client = riot_client

    async def _get_or_create_role(
        self, guild: discord.Guild, role_name: str, color: discord.Color
    ) -> discord.Role:
        """
        指定された名前のロールを探し、存在しない場合は作成する
        """
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            return existing_role

        # ロールが存在しない場合は作成
        return await guild.create_role(
            name=role_name,
            color=color,
            hoist=True,
            reason="Valorant rank role auto-creation",
        )

    async def _update_discord_role(
        self, guild: discord.Guild, member: discord.Member, new_rank_tier: str
    ):
        """
        メンバーのDiscordロールを新しいランクに合わせて更新する
        """
        if not member:
            return

        # "Valorant - Gold" のようなロール名を生成
        target_role_name = f"Valorant - {new_rank_tier}"

        # 既存のランク関連ロールを特定
        roles_to_remove = [
            role
            for role in member.roles
            if role.name.startswith("Valorant - ") and role.name != target_role_name
        ]

        # 新しいランクのロールを取得または作成
        # TODO: 各ランクの色を定義しておくと良い
        target_role = await self._get_or_create_role(
            guild, target_role_name, discord.Color.default()
        )

        # ロールを更新
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Rank update")
        if target_role not in member.roles:
            await member.add_roles(target_role, reason="Rank update")

    def _parse_rank_tier(self, rank_data: Dict) -> str:
        """
        Riot APIのレスポンスからランクのティア名（例: Gold）を抽出する
        """
        # APIレスポンスの構造によって調整が必要
        try:
            # 例: {'tier': 'Gold', 'rank': 2} のような形式を想定
            return rank_data["tier"].capitalize()
        except (TypeError, KeyError):
            return "Unrated"

    async def update_all_user_ranks(self, guild: discord.Guild):
        """
        全連携ユーザーのランク情報を更新し、ロールを再付与する
        """
        print("Starting daily rank update process...")
        linked_users: List[User] = self.user_repo.get_all_linked_users()

        for user in linked_users:
            member = guild.get_member(int(user.discord_id))
            if not member:
                print(f"User {user.discord_id} not found in this guild. Skipping.")
                continue

            # 1. Riot APIから最新ランク情報を取得
            rank_data = await self.riot_client.get_rank_info_by_puuid(user.riot_puuid)

            if rank_data:
                # 2a. ランク取得成功
                new_rank_tier = self._parse_rank_tier(rank_data)
                await self._update_discord_role(guild, member, new_rank_tier)

                # TODO: DBを更新 (成功時)
                # self.user_repo.update_user_rank(user.discord_id, new_rank_tier, 0)
                print(f"Successfully updated rank for {member.name} to {new_rank_tier}")

            else:
                # 2b. ランク取得失敗
                # TODO: DBを更新 (失敗時)
                # fail_count = user.rank_fetch_fail_count + 1
                # self.user_repo.update_user_fail_count(user.discord_id, fail_count)
                # print(f"Failed to fetch rank for {member.name}. Fail count: {fail_count}")

                # if fail_count >= 3:
                #     await self._update_discord_role(guild, member, "Unrated") # ロールを未設定状態にする
                #     print(f"Removed rank roles for {member.name} due to 3 consecutive failures.")
                pass
        print("Daily rank update process finished.")
