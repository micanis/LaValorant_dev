# services/user_service.py

import secrets
from urllib.parse import urlencode
from typing import Optional, Tuple, Dict

from api_clients.riot_api_client import RiotApiClient
from db.user_repository import UserRepository


class UserService:
    """
    ユーザー登録やRiotアカウント連携に関するビジネスロジックを担当する
    """

    def __init__(self, user_repo: UserRepository, riot_client: RiotApiClient):
        self.user_repo = user_repo
        self.riot_client = riot_client
        # 【修正点】stateとdiscord_idを一時保存するキャッシュ
        self.state_cache: Dict[str, str] = {}

    def generate_auth_url(self, discord_id: str) -> str:
        """
        ユーザーをRiotの認証ページにリダイレクトするためのURLを生成する
        """
        state = secrets.token_urlsafe(16)
        # 【修正点】生成したstateとdiscord_idを紐づけてキャッシュに保存
        self.state_cache[state] = discord_id

        params = {
            "client_id": self.riot_client.client_id,
            "redirect_uri": self.riot_client.redirect_uri,
            "response_type": "code",
            "scope": "openid",
            "state": state,
        }
        return (
            f"{self.riot_client.AUTH_BASE_URL}/api/oauth/authorize?{urlencode(params)}"
        )

    async def process_oauth_callback(self, code: str, state: str) -> Tuple[bool, str]:
        """
        OAuthコールバックを処理し、ユーザー情報をDBに保存する
        """
        # 【修正点】stateを使ってキャッシュからdiscord_idを取得
        discord_id = self.state_cache.pop(state, None)
        if not discord_id:
            return False, "無効な認証セッションです。state情報が見つかりません。"

        token_data = await self.riot_client.exchange_code_for_token(code)
        if not token_data or "access_token" not in token_data:
            return False, "Riot APIとのトークン交換に失敗しました。"

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")

        account_data = await self.riot_client.get_account_puuid(access_token)
        if not account_data or "puuid" not in account_data:
            return False, "Riot APIからユーザー情報の取得に失敗しました。"

        puuid = account_data["puuid"]

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
