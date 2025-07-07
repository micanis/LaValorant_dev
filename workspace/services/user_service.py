# services/user_service.py
import secrets
from urllib.parse import urlencode
from typing import Tuple

from api_clients.riot_api_client import RiotApiClient
from db.user_repository import UserRepository


class UserService:
    """
    ユーザー登録やRiotアカウント連携に関するビジネスロジックを担当する
    """

    def __init__(self, user_repo: UserRepository, riot_client: RiotApiClient):
        self.user_repo = user_repo
        self.riot_client = riot_client

    def generate_auth_url(self, discord_id: str) -> str:
        """
        ユーザーをRiotの認証ページにリダイレクトするためのURLを生成する
        設計書「6.2. /rank (Riotアカウント連携フロー)」のステップ5に対応
        """
        # CSRF攻撃を防ぐため、推測困難なstateを生成
        state = secrets.token_urlsafe(16)
        # TODO: このstateとdiscord_idを一時的にキャッシュ(Redisなど)またはDBに保存する
        #       コールバック時にstateを検証し、対応するdiscord_idを取得できるようにする

        params = {
            "client_id": self.riot_client.client_id,
            "redirect_uri": self.riot_client.redirect_uri,
            "response_type": "code",
            "scope": "openid",  # PUUID取得に必要な最低限のスコープ
            "state": state,
        }
        return (
            f"{self.riot_client.AUTH_BASE_URL}/api/oauth/authorize?{urlencode(params)}"
        )

    async def process_oauth_callback(self, code: str, state: str) -> Tuple[bool, str]:
        """
        OAuthコールバックを処理し、ユーザー情報をDBに保存する
        設計書「6.2. /rank (Riotアカウント連携フロー)」のステップ11に対応

        Returns:
            Tuple[bool, str]: (成功フラグ, メッセージ)
        """
        # TODO: 保存しておいたstateを検証する

        # 1. 認証コードをトークンに交換
        token_data = await self.riot_client.exchange_code_for_token(code)
        if not token_data or "access_token" not in token_data:
            return False, "Riot APIとのトークン交換に失敗しました。"

        access_token = token_data["access_token"]
        refresh_token = token_data.get(
            "refresh_token", ""
        )  # refresh_tokenは存在しない場合もある

        # 2. トークンを使ってPUUIDを取得
        account_data = await self.riot_client.get_account_puuid(access_token)
        if not account_data or "puuid" not in account_data:
            return False, "Riot APIからユーザー情報の取得に失敗しました。"

        puuid = account_data["puuid"]
        # TODO: stateから取得したdiscord_idを使用する
        discord_id = "..."  # 仮

        # 3. 取得した情報をUserRepository経由でDBに保存
        try:
            self.user_repo.upsert_user(
                discord_id=discord_id,
                riot_puuid=puuid,
                access_token=access_token,
                refresh_token=refresh_token,
            )
            return True, "アカウント連携が正常に完了しました！"
        except Exception as e:
            print(f"DB Error during user upsert: {e}")
            return False, "データベースへのユーザー情報保存中にエラーが発生しました。"
