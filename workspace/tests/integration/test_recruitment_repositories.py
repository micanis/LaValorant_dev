# tests/integration/test_recruitment_repositories.py

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

# dotenvを読み込むために必要
from dotenv import load_dotenv

# configをインポートする前にdotenvを読み込む
load_dotenv()

from config import settings
from supabase import create_client
from db.recruitment_repository import RecruitmentRepository
from db.participant_repository import ParticipantRepository


# 結合テストであることを示すpytestマーク
@pytest.mark.integration
class TestRecruitmentRepositoriesIntegration:
    """RecruitmentRepositoryとParticipantRepositoryの結合テストクラス"""

    @pytest.fixture(scope="class")
    def db_client(self):
        """テスト用のDBクライアントを生成するFixture"""
        assert settings.TEST_SUPABASE_URL, "TEST_SUPABASE_URL is not set in .env"
        assert settings.TEST_SUPABASE_KEY, "TEST_SUPABASE_KEY is not set in .env"

        return create_client(
            supabase_url=settings.TEST_SUPABASE_URL,
            supabase_key=settings.TEST_SUPABASE_KEY,
        )

    @pytest.fixture(scope="class")
    def recruitment_repo(self, db_client):
        return RecruitmentRepository(db_client)

    @pytest.fixture(scope="class")
    def participant_repo(self, db_client):
        return ParticipantRepository(db_client)

    @pytest.fixture
    def sample_recruitment(self, db_client, recruitment_repo: RecruitmentRepository):
        """テスト用の募集データを作成し、テスト終了後に削除するFixture"""
        # --- セットアップ (テスト前の準備) ---

        # 1. 募集主となるユーザーを先に作成しておく
        creator_id = f"creator_{uuid4()}"
        db_client.table("users").insert({"discord_id": creator_id}).execute()

        # 2. テスト用の募集を作成
        recruitment = recruitment_repo.create_recruitment(
            message_id="integration_test_msg_123",
            guild_id="integration_test_guild_123",
            creator_id=creator_id,
            party_type="テストパーティ",
            max_participants=5,
            deadline=datetime.now() + timedelta(hours=1),
        )

        # yieldでテストに必要なデータを渡す
        yield recruitment

        # --- ティアダウン (テスト後の後片付け) ---
        # 関連するデータをすべて削除 (participants -> recruitments -> users)
        db_client.table("participants").delete().eq(
            "recruitment_id", recruitment.id
        ).execute()
        db_client.table("recruitments").delete().eq("id", recruitment.id).execute()
        db_client.table("users").delete().eq("discord_id", creator_id).execute()

    def test_create_and_get_recruitment(
        self, recruitment_repo: RecruitmentRepository, sample_recruitment
    ):
        """募集の作成と取得が正常に行えるか"""
        # --- 実行 (Act) ---
        retrieved = recruitment_repo.get_recruitment_by_message_id(
            sample_recruitment.message_id
        )

        # --- 検証 (Assert) ---
        assert retrieved is not None
        assert retrieved.id == sample_recruitment.id
        assert retrieved.creator_id == sample_recruitment.creator_id
        assert retrieved.party_type == "テストパーティ"

    def test_add_and_get_participant(
        self, participant_repo: ParticipantRepository, sample_recruitment
    ):
        """募集への参加者の追加と取得が正常に行えるか"""
        # --- 準備 (Arrange) ---
        participant_user_id = f"participant_{uuid4()}"

        # --- 実行 (Act) ---
        # 参加者を追加
        participant_repo.add_participant(sample_recruitment.id, participant_user_id)

        # 参加者リストを取得
        participants = participant_repo.get_participants_by_recruitment_id(
            sample_recruitment.id
        )

        # --- 検証 (Assert) ---
        assert len(participants) == 1
        assert participants[0].recruitment_id == sample_recruitment.id
        assert participants[0].user_id == participant_user_id
