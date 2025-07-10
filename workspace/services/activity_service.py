# services/activity_service.py

from datetime import datetime, timedelta
from typing import Set

import discord

from db.user_repository import UserRepository
from db.activity_log_repository import ActivityLogRepository

# ロール名を定数化
REGULAR_MEMBER_ROLE_NAME = "レギュラーメンバー"
GHOST_MEMBER_ROLE_NAME = "幽霊部員"


class ActivityService:
    """
    ユーザーの活動状況を評価し、ロールを付与する責務を持つ
    """

    def __init__(
        self, user_repo: UserRepository, activity_log_repo: ActivityLogRepository
    ):
        self.user_repo = user_repo
        self.activity_log_repo = activity_log_repo

    async def _get_or_create_role(
        self, guild: discord.Guild, role_name: str, color: discord.Color
    ) -> discord.Role:
        """
        指定された名前のロールを探し、存在しない場合は作成する
        """
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if existing_role:
            return existing_role
        return await guild.create_role(
            name=role_name, color=color, reason="Activity role auto-creation"
        )

    async def _update_regular_members_role(
        self, guild: discord.Guild, start_date: datetime, end_date: datetime
    ):
        """
        「レギュラーメンバー」ロールを更新する
        """
        print("Updating regular member roles...")
        role = await self._get_or_create_role(
            guild, REGULAR_MEMBER_ROLE_NAME, discord.Color.gold()
        )

        member_joins = []
        for member in guild.members:
            if member.bot:
                continue
            join_count = self.activity_log_repo.get_user_join_count_in_period(
                str(member.id), start_date, end_date
            )
            member_joins.append({"member": member, "count": join_count})

        member_joins.sort(key=lambda x: x["count"], reverse=True)

        new_regulars: Set[discord.Member] = {
            item["member"] for item in member_joins[:5] if item["count"] > 0
        }

        for member in guild.members:
            if member.bot:
                continue

            # 【修正点】メンバーが持つロールのリストに、対象ロールが含まれるかチェックする
            has_role = role in member.roles
            should_have_role = member in new_regulars

            if should_have_role and not has_role:
                await member.add_roles(role, reason="Top 5 active member")
                print(f"Added '{REGULAR_MEMBER_ROLE_NAME}' to {member.name}")
            elif not should_have_role and has_role:
                await member.remove_roles(
                    role, reason="No longer a top 5 active member"
                )
                print(f"Removed '{REGULAR_MEMBER_ROLE_NAME}' from {member.name}")

    async def _update_ghost_members_role(
        self, guild: discord.Guild, start_date: datetime, end_date: datetime
    ):
        """
        「幽霊部員」ロールを更新する
        """
        print("Updating ghost member roles...")
        role = await self._get_or_create_role(
            guild, GHOST_MEMBER_ROLE_NAME, discord.Color.dark_grey()
        )

        total_recruitments = (
            self.activity_log_repo.get_guild_total_recruitment_count_in_period(
                str(guild.id), start_date, end_date
            )
        )
        if total_recruitments == 0:
            print("No recruitments in the period. Skipping ghost member update.")
            return

        for member in guild.members:
            if member.bot:
                continue

            join_count = self.activity_log_repo.get_user_join_count_in_period(
                str(member.id), start_date, end_date
            )
            non_participation_rate = (
                (total_recruitments - join_count) / total_recruitments
                if total_recruitments > 0
                else 0
            )

            # 【修正点】こちらも同様に、メンバーのロールリストで直接判断
            has_role = role in member.roles
            should_have_role = non_participation_rate > 0.9

            if should_have_role and not has_role:
                await member.add_roles(role, reason="Non-participation rate > 90%")
                print(f"Added '{GHOST_MEMBER_ROLE_NAME}' to {member.name}")
            elif not should_have_role and has_role:
                await member.remove_roles(role, reason="Participation rate increased")
                print(f"Removed '{GHOST_MEMBER_ROLE_NAME}' from {member.name}")

    async def update_activity_roles(self, guild: discord.Guild):
        """
        全ての活動評価ロールを更新するエントリーポイント
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        await self._update_regular_members_role(guild, start_date, end_date)
        await self._update_ghost_members_role(guild, start_date, end_date)
