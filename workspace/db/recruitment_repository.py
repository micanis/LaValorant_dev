# db/recruitment_repository.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from supabase import Client


# Userリポジトリと同様に、Pydanticモデルでデータの型を定義します
# これにより、Service層とRepository層でのデータの受け渡しが安全かつ明確になります
class Recruitment(BaseModel):
    """
    recruitmentsテーブルのデータを表現するPydanticモデル
    """

    id: UUID
    message_id: str
    guild_id: str
    creator_id: str
    party_type: str
    max_participants: int
    status: str
    deadline: datetime
    created_at: datetime
    updated_at: datetime


class RecruitmentRepository:
    """
    recruitmentsテーブルへのデータアクセスを責務に持つクラス
    """

    def __init__(self, db_client: Client):
        self.db = db_client

    def create_recruitment(
        self,
        message_id: str,
        guild_id: str,
        creator_id: str,
        party_type: str,
        max_participants: int,
        deadline: datetime,
    ) -> Optional[Recruitment]:
        """
        新しい募集を作成する
        仕様書「2.2. /joinus (募集開始)」の内部処理に対応
        """
        response = (
            self.db.table("recruitments")
            .insert(
                {
                    "message_id": message_id,
                    "guild_id": guild_id,
                    "creator_id": creator_id,
                    "party_type": party_type,
                    "max_participants": max_participants,
                    "deadline": deadline.isoformat(),
                    "status": "open",  # 初期ステータスは'open'
                }
            )
            .execute()
        )

        if response.data:
            return Recruitment.model_validate(response.data[0])
        return None

    def get_recruitment_by_message_id(self, message_id: str) -> Optional[Recruitment]:
        """
        DiscordのメッセージIDから募集情報を取得する
        """
        response = (
            self.db.table("recruitments")
            .select("*")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        if response.data:
            return Recruitment.model_validate(response.data[0])
        return None

    def get_open_recruitment_by_creator_id(
        self, creator_id: str
    ) -> Optional[Recruitment]:
        """
        募集主のDiscord IDから、現在も募集中(open)の募集を取得する
        仕様書「2.3. /cancel」や「2.4. /edit」で、操作対象の募集を特定するために使用
        """
        response = (
            self.db.table("recruitments")
            .select("*")
            .eq("creator_id", creator_id)
            .eq("status", "open")
            .limit(1)
            .execute()
        )
        if response.data:
            return Recruitment.model_validate(response.data[0])
        return None

    def update_recruitment(
        self, recruitment_id: UUID, updates: dict
    ) -> Optional[Recruitment]:
        """
        募集情報を更新する
        仕様書「2.4. /edit (募集編集)」に対応
        """
        updates["updated_at"] = "now()"  # 更新日時をDB側で更新
        response = (
            self.db.table("recruitments")
            .update(updates)
            .eq("id", str(recruitment_id))
            .execute()
        )

        if response.data:
            return Recruitment.model_validate(response.data[0])
        return None
