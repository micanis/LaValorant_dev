# views/recruitment_view.py
from typing import List
import discord

from services.recruitment_service import RecruitmentService
from db.recruitment_repository import Recruitment
from db.participant_repository import Participant


class RecruitmentView(discord.ui.View):
    def __init__(self, recruitment_service: RecruitmentService):
        # timeout=NoneでViewを永続化する
        super().__init__(timeout=None)
        self.recruitment_service = recruitment_service

    async def _update_embed(
        self, original_embed: discord.Embed, interaction: discord.Interaction
    ):
        """
        メッセージのEmbedを最新の状態に更新するヘルパー関数
        """
        # custom_idからrecruitment_idを取得
        recruitment_id = original_embed.footer.text.split(" | ")[1]

        # 最新の参加者リストを取得
        participants = self.recruitment_service.participant_repo.get_participants_by_recruitment_id(
            recruitment_id
        )
        participant_mentions = [f"<@{p.user_id}>" for p in participants]

        # 募集情報を取得
        recruitment = (
            self.recruitment_service.recruitment_repo.get_recruitment_by_message_id(
                str(interaction.message.id)
            )
        )

        # 残り人数を更新
        remaining_count = recruitment.max_participants - len(participants)
        original_embed.set_field_at(
            index=2,  # 「残り人数」フィールドを想定
            name="残り人数",
            value=f"あと {remaining_count}人" if remaining_count > 0 else "満員",
            inline=False,
        )

        # 参加者リストを更新
        original_embed.set_field_at(
            index=3,  # 「参加者」フィールドを想定
            name=f"参加者 ({len(participants)}/{recruitment.max_participants})",
            value=", ".join(participant_mentions)
            if participant_mentions
            else "まだいません",
            inline=False,
        )

        # 満員になったらボタンを無効化する
        if remaining_count <= 0:
            self.get_item("join_button").disabled = True

        await interaction.message.edit(embed=original_embed, view=self)

    @discord.ui.button(
        label="参加する",
        style=discord.ButtonStyle.success,
        custom_id="recruitment_join",
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # custom_idではなく、Embedのフッターから募集IDを取得する方が確実
        recruitment_id_str = interaction.message.embeds[0].footer.text.split(" | ")[1]
        recruitment = (
            self.recruitment_service.recruitment_repo.get_recruitment_by_message_id(
                str(interaction.message.id)
            )
        )

        if not recruitment:
            await interaction.response.send_message(
                "この募集は既に終了しているようです。", ephemeral=True
            )
            return

        success, message = self.recruitment_service.join_recruitment(
            recruitment, interaction.user
        )

        await interaction.response.send_message(message, ephemeral=True)
        if success:
            await self._update_embed(interaction.message.embeds[0], interaction)

    @discord.ui.button(
        label="参加を取り消す",
        style=discord.ButtonStyle.danger,
        custom_id="recruitment_leave",
    )
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        recruitment = (
            self.recruitment_service.recruitment_repo.get_recruitment_by_message_id(
                str(interaction.message.id)
            )
        )

        if not recruitment:
            await interaction.response.send_message(
                "この募集は既に終了しているようです。", ephemeral=True
            )
            return

        success, message = self.recruitment_service.leave_recruitment(
            recruitment, interaction.user
        )

        await interaction.response.send_message(message, ephemeral=True)
        if success:
            await self._update_embed(interaction.message.embeds[0], interaction)
