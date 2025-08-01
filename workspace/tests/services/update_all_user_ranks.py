# tests/services/test_rank_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime

# テスト対象のクラスをインポート
from services.rank_service import RankService
from db.user_repository import User


# pytest-asyncioを使うため、テスト関数にデコレータを付与
@pytest.mark.asyncio
class TestRankService:
    """RankServiceのテストクラス"""

    @pytest.fixture
    def mock_user_repo(self, mocker):
        """UserRepositoryのモック"""
        return mocker.Mock()

    @pytest.fixture
    def mock_riot_client(self, mocker):
        """RiotApiClientのモック"""
        client = mocker.Mock()
        client.get_rank_info_by_puuid = AsyncMock()
        return client

    @pytest.fixture
    def service(self, mock_user_repo, mock_riot_client) -> RankService:
        """テスト対象のRankServiceインスタンス"""
        return RankService(user_repo=mock_user_repo, riot_client=mock_riot_client)

    def _create_mock_member(self, mocker, id: str, roles=None):
        """メンバーのモックを作成するヘルパー関数"""
        member = MagicMock()
        member.id = id
        member.name = f"User {id}"
        member.add_roles = AsyncMock()
        member.remove_roles = AsyncMock()
        member.roles = roles if roles is not None else []
        member.bot = False
        return member

    async def test_update_all_user_ranks(
        self, service: RankService, mock_user_repo, mock_riot_client, mocker
    ):
        """全連携ユーザーのランクとロールが正しく更新されるか"""
        # --- 準備 (Arrange) ---

        # 1. ロールとメンバーのモックを作成
        mock_guild = mocker.Mock()
        # 既存のロールをいくつか作成
        mock_role_gold = MagicMock()
        mock_role_gold.name = "Valorant - Gold"
        mock_role_diamond = MagicMock()
        mock_role_diamond.name = "Valorant - Diamond"
        mock_guild.roles = [mock_role_gold, mock_role_diamond]
        mock_guild.create_role = AsyncMock()  # create_roleもモック

        # テスト対象のメンバーを3人作成
        # - member_a: Gold -> Diamond に昇格
        # - member_b: Diamond -> Gold に降格
        # - member_c: ランク情報取得失敗
        member_a = self._create_mock_member(mocker, id="user_a", roles=[mock_role_gold])
        member_b = self._create_mock_member(
            mocker, id="user_b", roles=[mock_role_diamond]
        )
        member_c = self._create_mock_member(mocker, id="user_c", roles=[])
        mock_guild.get_member.side_effect = lambda id: {
            int("user_a"): member_a,
            int("user_b"): member_b,
            int("user_c"): member_c,
        }.get(id)

        # 2. DB (UserRepository) からの戻り値を設定
        db_users = [
            User(
                discord_id="user_a",
                riot_puuid="puuid_a",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            User(
                discord_id="user_b",
                riot_puuid="puuid_b",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            User(
                discord_id="user_c",
                riot_puuid="puuid_c",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]
        mock_user_repo.get_all_linked_users.return_value = db_users

        # 3. Riot APIからの戻り値を設定
        async def get_rank_side_effect(puuid):
            if puuid == "puuid_a":
                return {"tier": "Diamond"}
            if puuid == "puuid_b":
                return {"tier": "Gold"}
            if puuid == "puuid_c":
                return None  # 失敗ケース
            return None

        mock_riot_client.get_rank_info_by_puuid.side_effect = get_rank_side_effect

        # 新しく作成されるロールのモックも用意しておく
        mock_guild.create_role.return_value = MagicMock()

        # --- 実行 (Act) ---
        await service.update_all_user_ranks(mock_guild)

        # --- 検証 (Assert) ---

        # member_a (昇格): Diamondロールを追加し、Goldロールを削除
        member_a.add_roles.assert_called_once()
        # 追加されるロールの名前を検証
        added_role_a = member_a.add_roles.call_args[0][0]
        assert added_role_a.name == "Valorant - Diamond"
        member_a.remove_roles.assert_called_once_with(
            mock_role_gold, reason="Rank update"
        )

        # member_b (降格): Goldロールを追加し、Diamondロールを削除
        member_b.add_roles.assert_called_once()
        added_role_b = member_b.add_roles.call_args[0][0]
        assert added_role_b.name == "Valorant - Gold"
        member_b.remove_roles.assert_called_once_with(
            mock_role_diamond, reason="Rank update"
        )

        # member_c (失敗): ロールの追加・削除は行われない
        # TODO: 失敗カウントのロジックが実装されたら、それに応じたテストを追加
        member_c.add_roles.assert_not_called()
        member_c.remove_roles.assert_not_called()
