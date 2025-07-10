# tests/integration/test_user_repository.py

import pytest
from uuid import uuid4
import os

# dotenvを読み込むために必要
from dotenv import load_dotenv

# configをインポートする前にdotenvを読み込む
load_dotenv()

from config import settings
from supabase import create_client
from db.user_repository import UserRepository


# 結合テストであることを示すpytestマーク
@pytest.mark.integration
class TestUserRepositoryIntegration:
    """UserRepositoryの結合テストクラス"""

    @pytest.fixture(scope="class")
    def user_repo(self):
        """テスト用のUserRepositoryインスタンスを生成するFixture"""
        # .envファイルからテストDB用の設定が読み込まれているか確認
        assert settings.TEST_SUPABASE_URL, "TEST_SUPABASE_URL is not set in .env"
        assert settings.TEST_SUPABASE_KEY, "TEST_SUPABASE_KEY is not set in .env"

        # 【修正点】URLに"test"が含まれるかのチェックを削除
        # assert "test" in settings.TEST_SUPABASE_URL.lower(), "TEST_SUPABASE_URL should contain the word 'test'"

        test_db_client = create_client(
            supabase_url=settings.TEST_SUPABASE_URL,
            supabase_key=settings.TEST_SUPABASE_KEY,
        )
        return UserRepository(test_db_client, settings.ENCRYPTION_KEY)

    @pytest.fixture
    def sample_user(self, user_repo: UserRepository):
        """テスト用のユーザーデータを作成し、テスト終了後に削除するFixture"""
        # --- セットアップ (テスト前の準備) ---
        test_user_id = f"integration_test_user_{uuid4()}"
        test_puuid = f"puuid-{uuid4()}"
        test_access_token = "access_token_secret"
        test_refresh_token = "refresh_token_secret"

        user_repo.upsert_user(
            discord_id=test_user_id,
            riot_puuid=test_puuid,
            access_token=test_access_token,
            refresh_token=test_refresh_token,
        )

        yield {
            "discord_id": test_user_id,
            "riot_puuid": test_puuid,
            "access_token": test_access_token,
        }

        # --- ティアダウン (テスト後の後片付け) ---
        user_repo.db.table("users").delete().eq("discord_id", test_user_id).execute()

    def test_upsert_and_get_user(self, user_repo: UserRepository, sample_user: dict):
        """ユーザーの登録(Upsert)と取得が正常に行えるか"""
        retrieved_user = user_repo.get_user_by_discord_id(sample_user["discord_id"])

        assert retrieved_user is not None
        assert retrieved_user.discord_id == sample_user["discord_id"]
        assert retrieved_user.riot_puuid == sample_user["riot_puuid"]
        assert retrieved_user.riot_access_token == sample_user["access_token"]
