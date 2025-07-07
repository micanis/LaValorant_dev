# api_clients/riot_api_client.py
from typing import Any, Dict, Optional

import aiohttp


class RiotApiClient:
    """
    Riot Games APIとの通信を責務に持つクラス
    """

    AUTH_BASE_URL = "https://auth.riotgames.com"
    API_BASE_URL = "https://asia.api.riotgames.com"  # アジアサーバーを想定

    def __init__(
        self,
        client_session: aiohttp.ClientSession,
        api_key: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ):
        self.session = client_session
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    async def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """
        認証コードをアクセストークンに交換する
        設計書「6.2. /rank (Riotアカウント連携フロー)」のステップ9, 10に対応
        """
        url = f"{self.AUTH_BASE_URL}/api/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        # Basic認証のためにclient_idとclient_secretを使用
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)

        async with self.session.post(url, data=payload, auth=auth) as resp:
            if resp.status == 200:
                return await resp.json()
            # エラーハンドリング: 実際にはここで詳細なログ出力やリトライ処理を行う
            print(f"Error exchanging code: {resp.status} {await resp.text()}")
            return None

    async def get_account_puuid(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        アクセストークンを使用して、ユーザーのPUUIDなどを取得する
        """
        url = f"{self.AUTH_BASE_URL}/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"Error fetching PUUID: {resp.status} {await resp.text()}")
            return None

    async def get_rank_info_by_puuid(self, puuid: str) -> Optional[Dict[str, Any]]:
        """
        PUUIDからランク情報を取得する（VAL-RANKED-V1）
        RankServiceで使用
        """
        url = f"{self.API_BASE_URL}/val/ranked/v1/by-puuid/{puuid}"
        headers = {"X-Riot-Token": self.api_key}

        async with self.session.get(url, headers=headers) as resp:
            # ランク情報がない場合404が返ることがあるため、正常系として扱う
            if resp.status == 200:
                return await resp.json()
            # それ以外のエラー
            if resp.status != 404:
                print(f"Error fetching rank info: {resp.status} {await resp.text()}")
            return None
