import discord
from discord import app_commands
from discord.ext import commands


class UtilityCog(commands.Cog):
    """
    Botのユーティリティ関連のコマンドを管理する
    /helpなどが含まれる
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.commands(
        name="help", description="Botコマンドの一覧や使い方を表示する"
    )
    async def help_command(self, interaction: discord.Interaction):
        """
        ユーザーにヘルプメッセージを送信する
        """
        embed = discord.Embed(
            title="👋 LaValorant Bot ヘルプ",
            description=f"「{self.bot.user.name}」は、VALORANTの募集を円滑に行うためのBotです。\n以下にコマンドの一覧と使い方を記載します。",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🤝 `/joinus [other_member_n]`",
            value="参加者募集を開始します。ボイスチャンネルに接続した状態で実行すると、VC内のメンバーも自動で参加者に追加されます。",
            inline=False,
        )
        embed.add_field(
            name="✏️ `/edit`",
            value="自身が開始した募集中（締切前）の募集内容（人数、締切など）を編集します。",
            inline=False,
        )
        embed.add_field(
            name="❌ `/cancel`",
            value="自身が開始した募集をキャンセルします。参加者にはDMで通知が送られます。",
            inline=False,
        )
        embed.add_field(
            name="👑 `/rank`",
            value="Riotアカウントと連携し、VALORANTのランクに応じたDiscordロールを自動で付与・更新します。",
            inline=False,
        )
        embed.add_field(
            name="❓ `/help`", value="このヘルプメッセージを表示します。", inline=False
        )

        embed.add_field(
            name="✅ 募集への参加・取消方法",
            value="募集メッセージに表示される「参加する」「参加を取り消す」ボタンを押してください。",
            inline=False,
        )

        embed.add_field(
            name="⚠️ `/rank`連携時の注意",
            value="`/rank`実行後に送られる認証URLは、セキュリティのため有効期限が設定されています。期限が切れた場合は、再度コマンドを実行してください。",
            inline=False,
        )

        embed.set_footer(text="LaValorant Bot | v1.0.0")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
