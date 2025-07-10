# tests/services/test_activity_service.py

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# テスト対象のクラスをインポート
from services.activity_service import (
    ActivityService,
    REGULAR_MEMBER_ROLE_NAME,
    GHOST_MEMBER_ROLE_NAME,
)


# pytest-asyncioを使うため、テスト関数にデコレータを付与
@pytest.mark.asyncio
class TestActivityService:
    """ActivityServiceのテストクラス"""

    @pytest.fixture
    def mock_user_repo(self, mocker):
        """UserRepositoryのモック"""
        return mocker.Mock()

    @pytest.fixture
    def mock_activity_log_repo(self, mocker):
        """ActivityLogRepositoryのモック"""
        return mocker.Mock()

    @pytest.fixture
    def service(self, mock_user_repo, mock_activity_log_repo) -> ActivityService:
        """テスト対象のActivityServiceインスタンス"""
        return ActivityService(
            user_repo=mock_user_repo, activity_log_repo=mock_activity_log_repo
        )

    # 【修正点】idを引数で受け取るように変更
    def _create_mock_member(self, mocker, id: str, roles=None):
        """メンバーのモックを作成するヘルパー関数"""
        member = MagicMock()
        member.id = id  # メンバーにIDを設定
        member.add_roles = AsyncMock()
        member.remove_roles = AsyncMock()
        member.roles = roles if roles is not None else []
        member.bot = False  # botではないことを明示
        return member

    async def test_update_regular_members_role(
        self, service: ActivityService, mock_activity_log_repo, mocker
    ):
        """レギュラーメンバーのロールが正しく更新されるか"""
        # --- 準備 (Arrange) ---
        mock_guild = mocker.Mock()
        mock_role = MagicMock()
        mock_role.name = REGULAR_MEMBER_ROLE_NAME

        # 【修正点】各メンバーに一意のIDを設定
        member_a = self._create_mock_member(mocker, id="user_a", roles=[mock_role])
        member_b = self._create_mock_member(mocker, id="user_b", roles=[])
        member_c = self._create_mock_member(mocker, id="user_c", roles=[mock_role])
        member_d = self._create_mock_member(mocker, id="user_d")
        member_e = self._create_mock_member(mocker, id="user_e")
        member_f = self._create_mock_member(mocker, id="user_f")

        mock_guild.members = [
            member_a,
            member_b,
            member_c,
            member_d,
            member_e,
            member_f,
        ]
        mock_guild.roles = [mock_role]
        mock_guild.create_role = AsyncMock(return_value=mock_role)

        # DBからの戻り値をIDベースで設定
        def get_join_count_side_effect(user_id, start_date, end_date):
            counts = {
                "user_a": 10,
                "user_b": 15,
                "user_c": 1,
                "user_d": 8,
                "user_e": 7,
                "user_f": 6,
            }
            return counts.get(user_id, 0)

        mock_activity_log_repo.get_user_join_count_in_period.side_effect = (
            get_join_count_side_effect
        )

        # --- 実行 (Act) ---
        await service._update_regular_members_role(
            mock_guild, datetime.now(), datetime.now()
        )

        # --- 検証 (Assert) ---
        member_a.add_roles.assert_not_called()
        member_a.remove_roles.assert_not_called()

        member_b.add_roles.assert_called_once_with(
            mock_role, reason="Top 5 active member"
        )
        member_b.remove_roles.assert_not_called()

        member_c.add_roles.assert_not_called()
        member_c.remove_roles.assert_called_once_with(
            mock_role, reason="No longer a top 5 active member"
        )

        member_d.add_roles.assert_called_once_with(
            mock_role, reason="Top 5 active member"
        )
        member_e.add_roles.assert_called_once_with(
            mock_role, reason="Top 5 active member"
        )
        member_f.add_roles.assert_called_once_with(
            mock_role, reason="Top 5 active member"
        )

    async def test_update_ghost_members_role(
        self, service: ActivityService, mock_activity_log_repo, mocker
    ):
        """幽霊部員のロールが正しく更新されるか"""
        # --- 準備 (Arrange) ---
        mock_guild = mocker.Mock()
        mock_role = MagicMock()
        mock_role.name = GHOST_MEMBER_ROLE_NAME

        # 【修正点】各メンバーに一意のIDを設定
        member_a = self._create_mock_member(mocker, id="user_a", roles=[])
        member_b = self._create_mock_member(mocker, id="user_b", roles=[mock_role])
        member_c = self._create_mock_member(mocker, id="user_c", roles=[])

        mock_guild.members = [member_a, member_b, member_c]
        mock_guild.roles = [mock_role]
        mock_guild.create_role = AsyncMock(return_value=mock_role)

        mock_activity_log_repo.get_guild_total_recruitment_count_in_period.return_value = 10

        def get_join_count_side_effect(user_id, start_date, end_date):
            counts = {"user_a": 0, "user_b": 5, "user_c": 8}
            return counts.get(user_id, 0)

        mock_activity_log_repo.get_user_join_count_in_period.side_effect = (
            get_join_count_side_effect
        )

        # --- 実行 (Act) ---
        await service._update_ghost_members_role(
            mock_guild, datetime.now(), datetime.now()
        )

        # --- 検証 (Assert) ---
        member_a.add_roles.assert_called_once_with(
            mock_role, reason="Non-participation rate > 90%"
        )
        member_a.remove_roles.assert_not_called()

        member_b.add_roles.assert_not_called()
        member_b.remove_roles.assert_called_once_with(
            mock_role, reason="Participation rate increased"
        )

        member_c.add_roles.assert_not_called()
        member_c.remove_roles.assert_not_called()
