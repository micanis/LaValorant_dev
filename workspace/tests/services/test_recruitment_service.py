# tests/services/test_recruitment_service.py

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from freezegun import freeze_time

# テスト対象のクラスと、それが依存するクラスのPydanticモデルをインポート
from services.recruitment_service import RecruitmentService
from db.recruitment_repository import Recruitment
from db.participant_repository import Participant

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9), "JST")


# --- 既存のテスト ---
@pytest.fixture
def service_for_parse():
    """_parse_deadlineメソッドのテスト専用のFixture"""
    return RecruitmentService(
        recruitment_repo=None, participant_repo=None, activity_log_repo=None
    )


@freeze_time("2025-07-07 03:00:00")  # UTCの午前3時 = 日本時間の昼12時
class TestParseDeadline:
    """_parse_deadlineメソッドのテストクラス"""

    @pytest.mark.parametrize(
        "time_str, expected_minutes_later",
        [
            ("30m", 30),
            ("10分", 10),
            ("60分後", 60),
            ("1h", 60),
            ("2時間", 120),
            ("3時間後", 180),
        ],
    )
    def test_parse_deadline_relative(
        self, service_for_parse: RecruitmentService, time_str, expected_minutes_later
    ):
        """相対時間指定（N分後/N時間後）が正しくパースされるか"""
        now = datetime.now(JST)
        expected = now + timedelta(minutes=expected_minutes_later)
        actual = service_for_parse._parse_deadline(time_str)

        assert actual.year == expected.year
        assert actual.month == expected.month
        assert actual.day == expected.day
        assert actual.hour == expected.hour
        assert actual.minute == expected.minute

    @pytest.mark.parametrize(
        "time_str, expected_time",
        [
            ("14:00", datetime(2025, 7, 7, 14, 0, tzinfo=JST)),
            ("23:59", datetime(2025, 7, 7, 23, 59, tzinfo=JST)),
            ("11:00", datetime(2025, 7, 8, 11, 0, tzinfo=JST)),
            ("09:30", datetime(2025, 7, 8, 9, 30, tzinfo=JST)),
        ],
    )
    def test_parse_deadline_absolute(
        self, service_for_parse: RecruitmentService, time_str, expected_time
    ):
        """絶対時間指定（HH:MM）が正しくパースされるか"""
        actual = service_for_parse._parse_deadline(time_str)
        assert actual == expected_time

    @pytest.mark.parametrize(
        "invalid_str",
        ["abc", "10", "10時半", "25:00", "-30m"],
    )
    def test_parse_deadline_invalid(
        self, service_for_parse: RecruitmentService, invalid_str
    ):
        """無効なフォーマットがNoneを返すか"""
        assert service_for_parse._parse_deadline(invalid_str) is None


# --- モッキング関連のテスト ---

# テストで使用する固定のデータ
RECRUITMENT_ID = uuid4()
GUILD_ID = "guild_123"
USER_ID = "user_123"
CREATOR_ID = "creator_456"


@pytest.fixture
def mock_user(mocker):
    """Discordユーザーのモック"""
    user = mocker.Mock()
    user.id = USER_ID
    return user


@pytest.fixture
def mock_creator(mocker):
    """募集主のDiscordユーザーのモック"""
    creator = mocker.Mock()
    creator.id = CREATOR_ID
    creator.voice.channel.members = [creator]
    return creator


@pytest.fixture
def mock_interaction(mocker, mock_creator):
    """discord.Interactionのモック"""
    interaction = mocker.Mock()
    interaction.user = mock_creator
    interaction.guild_id = GUILD_ID
    return interaction


@pytest.fixture
def mock_recruitment():
    """募集情報のテストデータ"""
    return Recruitment(
        id=RECRUITMENT_ID,
        message_id="msg_123",
        guild_id=GUILD_ID,
        creator_id=CREATOR_ID,
        party_type="フルパ",
        max_participants=5,
        status="open",
        deadline=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def service_with_mocks(mocker):
    """依存関係をモックに差し替えたRecruitmentServiceのインスタンス"""
    mock_recruitment_repo = mocker.Mock()
    mock_participant_repo = mocker.Mock()
    mock_activity_log_repo = mocker.Mock()

    service = RecruitmentService(
        recruitment_repo=mock_recruitment_repo,
        participant_repo=mock_participant_repo,
        activity_log_repo=mock_activity_log_repo,
    )
    service.mocks = {
        "recruitment": mock_recruitment_repo,
        "participant": mock_participant_repo,
        "activity_log": mock_activity_log_repo,
    }
    return service


class TestJoinRecruitment:
    """join_recruitmentメソッドのテストクラス"""

    def test_join_successfully(
        self, service_with_mocks: RecruitmentService, mock_recruitment, mock_user
    ):
        service_with_mocks.mocks[
            "participant"
        ].get_participants_by_recruitment_id.return_value = []

        success, message = service_with_mocks.join_recruitment(
            mock_recruitment, mock_user
        )

        assert success is True
        assert message == "参加しました。"
        service_with_mocks.mocks["participant"].add_participant.assert_called_once_with(
            RECRUITMENT_ID, USER_ID
        )
        service_with_mocks.mocks["activity_log"].create_log.assert_called_once_with(
            USER_ID, RECRUITMENT_ID, GUILD_ID, "join"
        )

    def test_join_when_full(
        self,
        service_with_mocks: RecruitmentService,
        mock_recruitment,
        mock_user,
        mocker,
    ):
        mock_participants = [mocker.Mock() for _ in range(5)]
        service_with_mocks.mocks[
            "participant"
        ].get_participants_by_recruitment_id.return_value = mock_participants

        success, message = service_with_mocks.join_recruitment(
            mock_recruitment, mock_user
        )

        assert success is False
        assert message == "募集は既に満員です。"
        service_with_mocks.mocks["participant"].add_participant.assert_not_called()
        service_with_mocks.mocks["activity_log"].create_log.assert_not_called()

    def test_join_when_already_joined(
        self, service_with_mocks: RecruitmentService, mock_recruitment, mock_user
    ):
        mock_participant_me = Participant(
            recruitment_id=RECRUITMENT_ID, user_id=USER_ID, joined_at=datetime.now()
        )
        service_with_mocks.mocks[
            "participant"
        ].get_participants_by_recruitment_id.return_value = [mock_participant_me]

        success, message = service_with_mocks.join_recruitment(
            mock_recruitment, mock_user
        )

        assert success is False
        assert message == "既に参加しています。"
        service_with_mocks.mocks["participant"].add_participant.assert_not_called()
        service_with_mocks.mocks["activity_log"].create_log.assert_not_called()


class TestLeaveRecruitment:
    """leave_recruitmentメソッドのテストクラス"""

    def test_leave_successfully(
        self, service_with_mocks: RecruitmentService, mock_recruitment, mock_user
    ):
        success, message = service_with_mocks.leave_recruitment(
            mock_recruitment, mock_user
        )

        assert success is True
        assert message == "参加を取り消しました。"
        service_with_mocks.mocks[
            "participant"
        ].remove_participant.assert_called_once_with(RECRUITMENT_ID, USER_ID)
        service_with_mocks.mocks["activity_log"].create_log.assert_called_once_with(
            USER_ID, RECRUITMENT_ID, GUILD_ID, "leave"
        )


class TestCancelRecruitment:
    """cancel_recruitmentメソッドのテストクラス"""

    def test_cancel_successfully(
        self, service_with_mocks: RecruitmentService, mock_recruitment
    ):
        service_with_mocks.mocks[
            "recruitment"
        ].get_open_recruitment_by_creator_id.return_value = mock_recruitment

        mock_participants = [
            Participant(
                recruitment_id=RECRUITMENT_ID,
                user_id="participant_1",
                joined_at=datetime.now(),
            ),
            Participant(
                recruitment_id=RECRUITMENT_ID,
                user_id="participant_2",
                joined_at=datetime.now(),
            ),
        ]
        service_with_mocks.mocks[
            "participant"
        ].get_participants_by_recruitment_id.return_value = mock_participants

        cancelled_recruitment = mock_recruitment.model_copy(
            update={"status": "cancelled"}
        )
        service_with_mocks.mocks[
            "recruitment"
        ].update_recruitment.return_value = cancelled_recruitment

        recruitment, participant_ids, message = service_with_mocks.cancel_recruitment(
            CREATOR_ID
        )

        assert recruitment.status == "cancelled"
        assert message == "募集をキャンセルしました。"
        assert participant_ids == ["participant_1", "participant_2"]
        service_with_mocks.mocks[
            "recruitment"
        ].get_open_recruitment_by_creator_id.assert_called_once_with(CREATOR_ID)
        service_with_mocks.mocks[
            "recruitment"
        ].update_recruitment.assert_called_once_with(
            RECRUITMENT_ID, {"status": "cancelled"}
        )

    def test_cancel_when_no_recruitment_found(
        self, service_with_mocks: RecruitmentService
    ):
        service_with_mocks.mocks[
            "recruitment"
        ].get_open_recruitment_by_creator_id.return_value = None

        recruitment, participant_ids, message = service_with_mocks.cancel_recruitment(
            CREATOR_ID
        )

        assert recruitment is None
        assert participant_ids == []
        assert message == "あなたが開始した募集中(open)の募集が見つかりません。"
        service_with_mocks.mocks["recruitment"].update_recruitment.assert_not_called()


@pytest.mark.asyncio
class TestCreateRecruitment:
    """create_recruitmentメソッドのテストクラス"""

    @freeze_time("2025-07-07 03:00:00")
    async def test_create_successfully(
        self, service_with_mocks, mock_interaction, mock_recruitment, mocker
    ):
        service_with_mocks.mocks[
            "recruitment"
        ].create_recruitment.return_value = mock_recruitment

        other_members = [mocker.Mock(), mocker.Mock()]

        recruitment, message = await service_with_mocks.create_recruitment(
            interaction=mock_interaction,
            party_type="フルパ",
            needed_count=2,
            deadline_str="22:00",
            other_members=other_members,
        )

        assert recruitment is not None
        assert message == "募集の作成に成功しました。"

        service_with_mocks.mocks["recruitment"].create_recruitment.assert_called_once()
        call_args, call_kwargs = service_with_mocks.mocks[
            "recruitment"
        ].create_recruitment.call_args
        assert call_kwargs.get("creator_id") == CREATOR_ID
        assert call_kwargs.get("max_participants") == 5

        service_with_mocks.mocks[
            "participant"
        ].add_initial_participants.assert_called_once()
        args, _ = service_with_mocks.mocks[
            "participant"
        ].add_initial_participants.call_args
        assert len(args[1]) == 3

        assert service_with_mocks.mocks["activity_log"].create_log.call_count == 3

    async def test_create_with_invalid_deadline(
        self, service_with_mocks, mock_interaction
    ):
        recruitment, message = await service_with_mocks.create_recruitment(
            interaction=mock_interaction,
            party_type="デュオ",
            needed_count=1,
            deadline_str="あした",
            other_members=[],
        )

        assert recruitment is None
        assert (
            message
            == "募集締め切り時間の形式が正しくないか、過去の時間を指定しています。"
        )
        service_with_mocks.mocks["recruitment"].create_recruitment.assert_not_called()
        service_with_mocks.mocks[
            "participant"
        ].add_initial_participants.assert_not_called()


# 【↓ここから新しいテストクラスを追加↓】


@freeze_time("2025-07-07 03:00:00")
class TestEditRecruitment:
    """edit_recruitmentメソッドのテストクラス"""

    def test_edit_successfully(
        self, service_with_mocks: RecruitmentService, mock_recruitment
    ):
        """正常に編集できるケース"""
        # --- 準備 (Arrange) ---
        # update_recruitmentが呼ばれたら、更新後のデータを返すように設定
        updated_recruitment = mock_recruitment.model_copy(
            update={"party_type": "トリオ"}
        )
        service_with_mocks.mocks[
            "recruitment"
        ].update_recruitment.return_value = updated_recruitment

        updates = {
            "party_type": "トリオ",
            "max_participants": 3,
            "deadline_str": "23:00",
        }

        # --- 実行 (Act) ---
        recruitment, message = service_with_mocks.edit_recruitment(
            RECRUITMENT_ID, updates
        )

        # --- 検証 (Assert) ---
        assert recruitment is not None
        assert recruitment.party_type == "トリオ"
        assert message == "募集情報を更新しました。"

        # recruitment_repo.update_recruitment が期待通りに呼ばれたか
        service_with_mocks.mocks["recruitment"].update_recruitment.assert_called_once()
        # 呼び出し時の引数を取得して詳細に検証
        call_args, call_kwargs = service_with_mocks.mocks[
            "recruitment"
        ].update_recruitment.call_args
        assert call_args[0] == RECRUITMENT_ID  # 最初の引数がrecruitment_idであること
        update_dict = call_args[1]
        assert update_dict["party_type"] == "トリオ"
        assert update_dict["max_participants"] == 3
        # deadlineはdatetimeオブジェクトに変換されているはず
        assert isinstance(update_dict["deadline"], datetime)

    def test_edit_with_invalid_deadline(self, service_with_mocks: RecruitmentService):
        """不正な締切時間で編集しようとしたケース"""
        # --- 準備 (Arrange) ---
        updates = {
            "party_type": "トリオ",
            "max_participants": 3,
            "deadline_str": "きのう",  # 不正なフォーマット
        }

        # --- 実行 (Act) ---
        recruitment, message = service_with_mocks.edit_recruitment(
            RECRUITMENT_ID, updates
        )

        # --- 検証 (Assert) ---
        assert recruitment is None
        assert (
            message
            == "募集締め切り時間の形式が正しくないか、過去の時間を指定しています。"
        )
        service_with_mocks.mocks["recruitment"].update_recruitment.assert_not_called()
