# tests/services/test_user_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote  # <-【修正点】エンコード用の関数をインポート

# テスト対象のクラスをインポート
from services.user_service import UserService

# テスト用の固定データ
DISCORD_ID = "user_12345"
RIOT_PUUID = "puuid_abcdef"
AUTH_CODE = "test_auth_code"
STATE = "test_state"
ACCESS_TOKEN = "test_access_token"
REFRESH_TOKEN = "test_refresh_token"


# pytest-asyncioを使うため、テスト関数にデコレータを付与
@pytest.mark.asyncio
class TestUserService:
    """UserServiceのテストクラス"""

    @pytest.fixture
    def mock_user_repo(self, mocker):
        """UserRepositoryのモック"""
        return mocker.Mock()

    @pytest.fixture
    def mock_riot_client(self, mocker):
        """RiotApiClientのモック"""
        client = mocker.Mock()
        client.exchange_code_for_token = AsyncMock()
        client.get_account_puuid = AsyncMock()
        client.client_id = "test_client_id"
        client.redirect_uri = "http://localhost/callback"
        client.AUTH_BASE_URL = "https://auth.riotgames.com"
        return client

    @pytest.fixture
    def service(self, mock_user_repo, mock_riot_client) -> UserService:
        """テスト対象のUserServiceインスタンス"""
        return UserService(user_repo=mock_user_repo, riot_client=mock_riot_client)

    def test_generate_auth_url(self, service: UserService, mock_riot_client):
        """認証URLが正しく生成されるか"""
        # --- 実行 ---
        url = service.generate_auth_url(DISCORD_ID)

        # --- 検証 ---
        assert mock_riot_client.AUTH_BASE_URL in url
        assert mock_riot_client.client_id in url
        # 【修正点】redirect_uriをエンコードしてから比較する
        assert quote(mock_riot_client.redirect_uri, safe="") in url
        assert "response_type=code" in url
        assert "scope=openid" in url
        assert "state=" in url

    async def test_process_oauth_callback_successfully(
        self, service: UserService, mock_user_repo, mock_riot_client
    ):
        """OAuthコールバック処理が正常に完了するケース"""
        # --- 準備 (Arrange) ---
        mock_riot_client.exchange_code_for_token.return_value = {
            "access_token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
        }
        mock_riot_client.get_account_puuid.return_value = {"puuid": RIOT_PUUID}

        # --- 実行 (Act) ---
        success, message = await service.process_oauth_callback(
            AUTH_CODE, STATE, DISCORD_ID
        )  # discord_idを渡すように変更

        # --- 検証 (Assert) ---
        assert success is True
        assert message == "アカウント連携が正常に完了しました！"

        mock_riot_client.exchange_code_for_token.assert_called_once_with(AUTH_CODE)
        mock_riot_client.get_account_puuid.assert_called_once_with(ACCESS_TOKEN)
        # upsert_userが正しい引数で呼ばれたことを検証
        mock_user_repo.upsert_user.assert_called_once_with(
            discord_id=DISCORD_ID,
            riot_puuid=RIOT_PUUID,
            access_token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
        )

    async def test_process_oauth_callback_token_exchange_fails(
        self, service: UserService, mock_user_repo, mock_riot_client
    ):
        """トークン交換に失敗するケース"""
        # --- 準備 (Arrange) ---
        mock_riot_client.exchange_code_for_token.return_value = None

        # --- 実行 (Act) ---
        success, message = await service.process_oauth_callback(
            AUTH_CODE, STATE, DISCORD_ID
        )

        # --- 検証 (Assert) ---
        assert success is False
        assert message == "Riot APIとのトークン交換に失敗しました。"
        mock_riot_client.get_account_puuid.assert_not_called()
        mock_user_repo.upsert_user.assert_not_called()

    async def test_process_oauth_callback_puuid_fetch_fails(
        self, service: UserService, mock_user_repo, mock_riot_client
    ):
        """PUUID取得に失敗するケース"""
        # --- 準備 (Arrange) ---
        mock_riot_client.exchange_code_for_token.return_value = {
            "access_token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
        }
        mock_riot_client.get_account_puuid.return_value = None

        # --- 実行 (Act) ---
        success, message = await service.process_oauth_callback(
            AUTH_CODE, STATE, DISCORD_ID
        )

        # --- 検証 (Assert) ---
        assert success is False
        assert message == "Riot APIからユーザー情報の取得に失敗しました。"
        mock_user_repo.upsert_user.assert_not_called()
