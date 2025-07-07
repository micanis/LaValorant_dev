# tests/services/test_recruitment_service.py

import pytest
from datetime import datetime, timedelta, timezone
from freezegun import freeze_time

# テスト対象のクラスをインポート
from services.recruitment_service import RecruitmentService

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9), "JST")


# テストのために、RecruitmentServiceのインスタンスを生成
# このテストではリポジトリは使用しないため、Noneを渡しておく
@pytest.fixture
def service():
    return RecruitmentService(
        recruitment_repo=None, participant_repo=None, activity_log_repo=None
    )


# freezegunをインストールする必要があります: pip install freezegun
# テストの実行日時を固定することで、結果が安定する
@freeze_time("2025-07-07 12:00:00")
class TestParseDeadline:
    """_parse_deadlineメソッドのテストクラス"""

    # pytest.mark.parametrize を使うと、複数の入力と期待値を効率よくテストできる
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
        self, service: RecruitmentService, time_str, expected_minutes_later
    ):
        """相対時間指定（N分後/N時間後）が正しくパースされるか"""
        now = datetime.now(JST)
        expected = now + timedelta(minutes=expected_minutes_later)
        actual = service._parse_deadline(time_str)

        # 期待値と実際の結果が一致するかを表明(assert)
        assert actual.year == expected.year
        assert actual.month == expected.month
        assert actual.day == expected.day
        assert actual.hour == expected.hour
        assert actual.minute == expected.minute

    @pytest.mark.parametrize(
        "time_str, expected_time",
        [
            ("14:00", datetime(2025, 7, 7, 14, 0, tzinfo=JST)),  # 未来の時刻
            ("23:59", datetime(2025, 7, 7, 23, 59, tzinfo=JST)),  # 未来の時刻
            (
                "11:00",
                datetime(2025, 7, 8, 11, 0, tzinfo=JST),
            ),  # 過去の時刻 -> 翌日扱い
            (
                "09:30",
                datetime(2025, 7, 8, 9, 30, tzinfo=JST),
            ),  # 過去の時刻 -> 翌日扱い
        ],
    )
    def test_parse_deadline_absolute(
        self, service: RecruitmentService, time_str, expected_time
    ):
        """絶対時間指定（HH:MM）が正しくパースされるか"""
        actual = service._parse_deadline(time_str)
        assert actual == expected_time

    @pytest.mark.parametrize(
        "invalid_str",
        [
            "abc",
            "10",
            "10時半",
            "25:00",
            "-30m",
        ],
    )
    def test_parse_deadline_invalid(self, service: RecruitmentService, invalid_str):
        """無効なフォーマットがNoneを返すか"""
        assert service._parse_deadline(invalid_str) is None
