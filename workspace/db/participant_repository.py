# db/participant_repository.py
from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel
from supabase import Client


class Participant(BaseModel):
    """
    participantsテーブルのデータを表現するPydanticモデル
    """

    recruitment_id: UUID
    user_id: str
    joined_at: datetime


class ParticipantRepository:
    """
    participantsテーブルへのデータアクセスを責務に持つクラス
    """

    def __init__(self, db_client: Client):
        self.db = db_client

    def add_participant(self, recruitment_id: UUID, user_id: str) -> None:
        """
        募集に参加者を追加する
        仕様書「3.1. 募集Embedメッセージ」の「参加する」ボタンの処理で使用
        """
        # 既に存在する場合はエラーになるが、Service層で事前チェックするためここでは考慮しない
        self.db.table("participants").insert(
            {"recruitment_id": str(recruitment_id), "user_id": user_id}
        ).execute()

    def add_initial_participants(
        self, recruitment_id: UUID, user_ids: List[str]
    ) -> None:
        """
        募集開始時の初期参加者を一括で追加する
        仕様書「2.2. /joinus (募集開始)」の内部処理で使用
        """
        if not user_ids:
            return

        records = [
            {"recruitment_id": str(recruitment_id), "user_id": user_id}
            for user_id in user_ids
        ]
        self.db.table("participants").insert(records).execute()

    def remove_participant(self, recruitment_id: UUID, user_id: str) -> None:
        """
        募集から参加者を取り除く
        仕様書「3.1. 募集Embedメッセージ」の「参加を取り消す」ボタンの処理で使用
        """
        self.db.table("participants").delete().match(
            {"recruitment_id": str(recruitment_id), "user_id": user_id}
        ).execute()

    def get_participants_by_recruitment_id(
        self, recruitment_id: UUID
    ) -> List[Participant]:
        """
        指定された募集の参加者リストを取得する
        """
        response = (
            self.db.table("participants")
            .select("*")
            .eq("recruitment_id", str(recruitment_id))
            .execute()
        )
        if response.data:
            return [Participant.model_validate(p) for p in response.data]
        return []
