# cogs/rank_cog.py
import discord
from discord import app_commands
from discord.ext import commands

from services.user_service import UserService


class RankCog(commands.Cog):
    """
    /rankコマンドなど、ランク関連の機能を管理するCog
    """

    def __init__(self, bot: commands.Bot, user_service: UserService):
        self.bot = bot
        self.user_service = user_service

    @app_commands.command(
        name="rank", description="Riotアカウントを連携し、ランク情報を管理します。"
    )
    async def rank_command(self, interaction: discord.Interaction):
        """
        ユーザーにRiotアカウント連携用のURLを送信する
        """
        await interaction.response.defer(
            ephemeral=True
        )  # 処理に時間がかかる可能性を考慮

        try:
            # UserServiceから認証URLを生成
            auth_url = self.user_service.generate_auth_url(str(interaction.user.id))

            embed = discord.Embed(
                title="Riotアカウント連携",
                description=(
                    "VALORANTのランク情報を自動で表示・更新するために、Riotアカウントとの連携が必要です。\n\n"
                    "**下のボタンをクリック**して、Riot Gamesの公式サイトで認証を完了してください。"
                ),
                color=discord.Color.red(),
            )
            embed.set_footer(
                text="※この認証URLはあなた専用であり、一定時間のみ有効です。"
            )

            # ボタン付きのViewを作成
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(label="Riotアカウントで認証する", url=auth_url)
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            print(f"Error generating auth URL: {e}")
            await interaction.followup.send(
                "アカウント連携URLの生成に失敗しました。管理者にお問い合わせください。",
                ephemeral=True,
            )


# Cogを読み込むための必須記述
async def setup(bot: commands.Bot):
    # main.pyでインスタンス化されたUserServiceをここで受け取る想定
    user_service = bot.user_service
    await bot.add_cog(RankCog(bot, user_service))
