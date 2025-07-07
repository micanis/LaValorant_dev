# services/recruitment_service.py
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import discord

from db.recruitment_repository import RecruitmentRepository, Recruitment
from db.participant_repository import ParticipantRepository
from db.activity_log_repository import ActivityLogRepository

# 日本時間のタイムゾーン
JST = timezone(timedelta(hours=9), "JST")


class RecruitmentService:
    """
    募集の作成・管理に関するビジネスロジックを担う
    """

    def __init__(
        self,
        recruitment_repo: RecruitmentRepository,
        participant_repo: ParticipantRepository,
        activity_log_repo: ActivityLogRepository,
    ):
        self.recruitment_repo = recruitment_repo
        self.participant_repo = participant_repo
        self.activity_log_repo = activity_log_repo

    def _parse_deadline(self, time_str: str) -> Optional[datetime]:
        """
        ユーザーが入力した募集締め切り時間をdatetimeオブジェクトに変換する
        許容フォーマット: "HH:MM" (例: "22:00"), "N分後"/"Nm" (例: "30分後"), "N時間後"/"Nh" (例: "1時間後")
        """
        now = datetime.now(JST)

        # "HH:MM" 形式の処理
        match_hm = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
        if match_hm:
            try:
                hour = int(match_hm.group(1))
                minute = int(match_hm.group(2))

                # 時と分の値が有効かチェック (25:00のような値をここで弾く)
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    return None

                # 【最終修正】datetimeオブジェクトではなく、時・分の数値で直接比較する
                is_future_time = False
                if hour > now.hour:
                    is_future_time = True
                elif hour == now.hour and minute > now.minute:
                    is_future_time = True

                deadline = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

                if is_future_time:
                    # 未来の時刻なら今日の日付
                    return deadline
                else:
                    # 過去の時刻なら翌日の日付
                    return deadline + timedelta(days=1)

            except ValueError:
                return None

        # "N分後" or "Nm" 形式の処理
        match_m = re.match(r"^(\d+)(m|分|分後)$", time_str)
        if match_m:
            minutes = int(match_m.group(1))
            return now + timedelta(minutes=minutes)

        # "N時間後" or "Nh" 形式の処理
        match_h = re.match(r"^(\d+)(h|時間|時間後)$", time_str)
        if match_h:
            hours = int(match_h.group(1))
            return now + timedelta(hours=hours)

        return None

    async def create_recruitment(
        self,
        *,
        interaction: discord.Interaction,
        party_type: str,
        needed_count: int,
        deadline_str: str,
        other_members: List[discord.Member],
    ) -> Tuple[Optional[Recruitment], str]:
        """
        新しい募集を作成するフロー全体を管理する

        """
        # 1. 締切時間をパース
        deadline = self._parse_deadline(deadline_str)
        if not deadline or deadline <= datetime.now(JST):
            return (
                None,
                "募集締め切り時間の形式が正しくないか、過去の時間を指定しています。",
            )

        # 2. 初期参加者をリストアップ
        creator = interaction.user
        initial_participants = {creator}  # 重複を避けるためセットを使用
        initial_participants.update(other_members)

        # VC参加者を追加
        if (
            isinstance(creator, discord.Member)
            and creator.voice
            and creator.voice.channel
        ):
            initial_participants.update(creator.voice.channel.members)

        # 3. 募集定員を計算
        max_participants = len(initial_participants) + needed_count

        # 4. DBに募集情報を保存 (Repositoryを呼び出し)
        recruitment = self.recruitment_repo.create_recruitment(
            message_id="dummy",  # この後メッセージを送信してから更新する
            guild_id=str(interaction.guild_id),
            creator_id=str(creator.id),
            party_type=party_type,
            max_participants=max_participants,
            deadline=deadline,
        )
        if not recruitment:
            return None, "データベースへの募集情報登録に失敗しました。"

        # 5. 初期参加者をDBに保存 & 活動ログを記録
        participant_ids = [str(p.id) for p in initial_participants]
        self.participant_repo.add_initial_participants(recruitment.id, participant_ids)
        for user_id in participant_ids:
            self.activity_log_repo.create_log(
                user_id, recruitment.id, str(interaction.guild_id), "join"
            )

        return recruitment, "募集の作成に成功しました。"

    def join_recruitment(
        self, recruitment: Recruitment, user: discord.Member
    ) -> Tuple[bool, str]:
        """
        ユーザーが募集に参加する処理
        """
        participants = self.participant_repo.get_participants_by_recruitment_id(
            recruitment.id
        )
        if len(participants) >= recruitment.max_participants:
            return False, "募集は既に満員です。"
        if any(p.user_id == str(user.id) for p in participants):
            return False, "既に参加しています。"

        # 参加者を追加し、ログを記録
        self.participant_repo.add_participant(recruitment.id, str(user.id))
        self.activity_log_repo.create_log(
            str(user.id), recruitment.id, recruitment.guild_id, "join"
        )
        return True, "参加しました。"

    def leave_recruitment(
        self, recruitment: Recruitment, user: discord.Member
    ) -> Tuple[bool, str]:
        """
        ユーザーが募集への参加を取り消す処理
        """
        # 参加者から削除し、ログを記録
        self.participant_repo.remove_participant(recruitment.id, str(user.id))
        self.activity_log_repo.create_log(
            str(user.id), recruitment.id, recruitment.guild_id, "leave"
        )
        return True, "参加を取り消しました。"

    def cancel_recruitment(
        self, creator_id: str
    ) -> Tuple[Optional[Recruitment], List[str], str]:
        """
        募集主のIDから募集中(open)の募集をキャンセル済(cancelled)にする

        Returns:
            Tuple[Optional[Recruitment], List[str], str]: (募集情報, 参加者IDリスト, メッセージ)
        """
        # 1. ユーザーが作成したオープンな募集を探す
        recruitment = self.recruitment_repo.get_open_recruitment_by_creator_id(
            creator_id
        )
        if not recruitment:
            return None, [], "あなたが開始した募集中(open)の募集が見つかりません。"

        # 2. 参加者リストを取得
        participants = self.participant_repo.get_participants_by_recruitment_id(
            recruitment.id
        )
        participant_ids = [p.user_id for p in participants]

        # 3. 募集のステータスを'cancelled'に更新
        updated_recruitment = self.recruitment_repo.update_recruitment(
            recruitment.id, {"status": "cancelled"}
        )
        if not updated_recruitment:
            return (
                None,
                [],
                "募集のキャンセル処理中にデータベースエラーが発生しました。",
            )

        return updated_recruitment, participant_ids, "募集をキャンセルしました。"

    def edit_recruitment(
        self, recruitment_id: UUID, updates: dict
    ) -> Tuple[Optional[Recruitment], str]:
        """
        募集情報を更新する
        """
        if "deadline_str" in updates:
            deadline = self._parse_deadline(updates["deadline_str"])
            if not deadline or deadline <= datetime.now(JST):
                return (
                    None,
                    "募集締め切り時間の形式が正しくないか、過去の時間を指定しています。",
                )
            updates["deadline"] = deadline
            del updates["deadline_str"]

        updated_recruitment = self.recruitment_repo.update_recruitment(
            recruitment_id, updates
        )

        if not updated_recruitment:
            return None, "募集情報の更新に失敗しました。"

        return updated_recruitment, "募集情報を更新しました。"
