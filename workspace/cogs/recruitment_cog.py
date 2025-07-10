# cogs/recruitment_cog.py

from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands
from functools import partial

# 【↓修正点↓】Recruitmentモデルをインポート
from db.recruitment_repository import Recruitment
from services.recruitment_service import RecruitmentService
from views.recruitment_modal import RecruitmentModal
from views.recruitment_view import RecruitmentView


class RecruitmentCog(commands.Cog):
    """
    募集関連のコマンド (/joinus, /cancel, /edit) を管理するCog
    """

    def __init__(self, bot: commands.Bot, recruitment_service: RecruitmentService):
        self.bot = bot
        self.recruitment_service = recruitment_service

    def _build_recruitment_embed(
        self, recruitment: dict, participants: List[discord.User]
    ) -> discord.Embed:
        participant_mentions = [p.mention for p in participants]
        remaining_count = recruitment["max_participants"] - len(participants)

        embed = discord.Embed(
            title=f"【募集中】VALORANT @{recruitment['max_participants']}",
            description=f"**{recruitment['party_type']}** で参加者を募集しています！",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="募集主", value=f"<@{recruitment['creator_id']}>", inline=False
        )
        embed.add_field(
            name="締切",
            value=f"<t:{int(recruitment['deadline'].timestamp())}:R>",
            inline=False,
        )
        embed.add_field(
            name="残り人数",
            value=f"あと {remaining_count}人" if remaining_count > 0 else "満員",
            inline=False,
        )
        embed.add_field(
            name=f"現在の参加者 ({len(participants)}/{recruitment['max_participants']})",
            value=", ".join(participant_mentions)
            if participant_mentions
            else "まだいません",
            inline=False,
        )
        embed.set_footer(text=f"Recruitment ID | {recruitment['id']}")
        return embed

    async def on_modal_submit(
        self,
        interaction: discord.Interaction,
        party_type: str,
        needed_count_str: str,
        deadline_str: str,
        other_members: List[discord.Member],
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            needed_count = int(needed_count_str)
            if needed_count < 0:
                raise ValueError
        except ValueError:
            await interaction.followup.send(
                "残り必要人数は0以上の半角数字で入力してください。", ephemeral=True
            )
            return

        recruitment, message = await self.recruitment_service.create_recruitment(
            interaction=interaction,
            party_type=party_type,
            needed_count=needed_count,
            deadline_str=deadline_str,
            other_members=other_members,
        )

        if not recruitment:
            await interaction.followup.send(
                f"募集の作成に失敗しました: {message}", ephemeral=True
            )
            return

        recruitment_channel = interaction.channel

        initial_participants = {interaction.user} | set(other_members)
        if isinstance(interaction.user, discord.Member) and interaction.user.voice:
            initial_participants.update(interaction.user.voice.channel.members)

        embed = self._build_recruitment_embed(
            recruitment.model_dump(), list(initial_participants)
        )
        view = RecruitmentView(self.recruitment_service)

        sent_message = await recruitment_channel.send(embed=embed, view=view)

        self.recruitment_service.recruitment_repo.update_recruitment(
            recruitment.id, {"message_id": str(sent_message.id)}
        )

        await interaction.followup.send("募集を開始しました！", ephemeral=True)

    async def on_edit_modal_submit(
        self,
        interaction: discord.Interaction,
        recruitment: Recruitment,
        party_type: str,
        max_participants_str: str,
        deadline_str: str,
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            max_participants = int(max_participants_str)
            if max_participants <= 0:
                raise ValueError
        except ValueError:
            await interaction.followup.send(
                "募集定員は1以上の半角数字で入力してください。", ephemeral=True
            )
            return

        updates = {
            "party_type": party_type,
            "max_participants": max_participants,
            "deadline_str": deadline_str,
        }
        updated_recruitment, message = self.recruitment_service.edit_recruitment(
            recruitment.id, updates
        )

        if not updated_recruitment:
            await interaction.followup.send(
                f"編集に失敗しました: {message}", ephemeral=True
            )
            return

        try:
            channel = await self.bot.fetch_channel(interaction.channel_id)
            original_message = await channel.fetch_message(int(recruitment.message_id))

            participants = self.recruitment_service.participant_repo.get_participants_by_recruitment_id(
                recruitment.id
            )
            participant_users = [
                await self.bot.fetch_user(int(p.user_id)) for p in participants
            ]

            new_embed = self._build_recruitment_embed(
                updated_recruitment.model_dump(), participant_users
            )
            await original_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Error editing message for edit: {e}")

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="joinus", description="VALORANTの参加者募集を開始します。"
    )
    @app_commands.describe(
        other_member_1="他に確定しているメンバー1",
        other_member_2="他に確定しているメンバー2",
    )
    async def joinus(
        self,
        interaction: discord.Interaction,
        other_member_1: Optional[discord.Member] = None,
        other_member_2: Optional[discord.Member] = None,
    ):
        other_members = [m for m in [other_member_1, other_member_2] if m is not None]

        callback = partial(self.on_modal_submit, other_members=other_members)
        modal = RecruitmentModal(on_submit_callback=callback)
        await interaction.response.send_modal(modal)

    @app_commands.command(
        name="cancel", description="自身が開始した募集をキャンセルします。"
    )
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        recruitment, participant_ids, message = (
            self.recruitment_service.cancel_recruitment(str(interaction.user.id))
        )

        if not recruitment:
            await interaction.followup.send(message, ephemeral=True)
            return

        try:
            channel = await self.bot.fetch_channel(interaction.channel_id)
            original_message = await channel.fetch_message(int(recruitment.message_id))

            cancelled_embed = discord.Embed(
                title="【募集キャンセル】",
                description="この募集は募集主によってキャンセルされました。",
                color=discord.Color.dark_grey(),
            )
            cancelled_embed.set_footer(text=f"Recruitment ID | {recruitment.id}")

            await original_message.edit(embed=cancelled_embed, view=None)

        except discord.NotFound:
            print(f"Original message for recruitment {recruitment.id} not found.")
        except Exception as e:
            print(f"Error editing message for cancellation: {e}")

        if participant_ids:
            notification_message = f"募集主 <@{recruitment.creator_id}> によって募集がキャンセルされました。"
            for user_id in participant_ids:
                if user_id == str(interaction.user.id):
                    continue
                try:
                    member = await self.bot.fetch_user(int(user_id))
                    await member.send(notification_message)
                except Exception as e:
                    print(f"Failed to send DM to {user_id}: {e}")

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="edit", description="自身が開始した募集内容を編集します。"
    )
    async def edit(self, interaction: discord.Interaction):
        recruitment = self.recruitment_service.recruitment_repo.get_open_recruitment_by_creator_id(
            str(interaction.user.id)
        )
        if not recruitment:
            await interaction.response.send_message(
                "あなたが編集できる募集中(open)の募集はありません。", ephemeral=True
            )
            return

        callback = partial(self.on_edit_modal_submit, recruitment=recruitment)

        modal = RecruitmentModal(on_submit_callback=callback)
        modal.title = "募集内容の編集"
        modal.party_type.default = recruitment.party_type
        modal.needed_count.label = "募集定員（合計人数）"
        modal.needed_count.default = str(recruitment.max_participants)
        modal.deadline_str.default = recruitment.deadline.astimezone(
            self.recruitment_service.JST
        ).strftime("%H:%M")

        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot):
    recruitment_service = bot.recruitment_service
    await bot.add_cog(RecruitmentCog(bot, recruitment_service))
