# views/recruitment_modal.py
from typing import Callable, Coroutine
import discord


class RecruitmentModal(discord.ui.Modal):
    def __init__(self, on_submit_callback: Callable[..., Coroutine]):
        super().__init__(title="VALORANT 募集内容の入力")
        self.on_submit_callback = on_submit_callback

        # 仕様書「3.2. モーダルUI」に基づく入力フィールド
        self.party_type = discord.ui.TextInput(
            label="人数形態",
            placeholder="デュオ, トリオ, フルパ, カスタム のいずれかを入力",
            required=True,
        )
        self.needed_count = discord.ui.TextInput(
            label="残り必要人数",
            placeholder="例: 2 (半角数字)",
            required=True,
            style=discord.TextStyle.short,
        )
        self.deadline_str = discord.ui.TextInput(
            label="募集締め切り時間",
            placeholder="例: 22:00  または  30m (30分後), 1h (1時間後)",
            required=True,
            style=discord.TextStyle.short,
        )

        self.add_item(self.party_type)
        self.add_item(self.needed_count)
        self.add_item(self.deadline_str)

    async def on_submit(self, interaction: discord.Interaction):
        """
        ユーザーがモーダルを送信したときに呼び出される
        """
        # Cog側で定義されたコールバック関数を呼び出し、入力値を渡す
        await self.on_submit_callback(
            interaction,
            party_type=self.party_type.value,
            needed_count_str=self.needed_count.value,
            deadline_str=self.deadline_str.value,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"RecruitmentModal error: {error}")
        await interaction.response.send_message(
            "エラーが発生しました。もう一度お試しください。", ephemeral=True
        )
