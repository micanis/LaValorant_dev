# db/activity_log_repository.py
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from supabase import Client

# action_typeは'join'か'leave'のみを受け付けるようにLiteralで型を定義
ActionType = Literal["join", "leave"]


class ActivityLog(BaseModel):
    """
    activity_logsテーブルのデータを表現するPydanticモデル
    """

    id: UUID
    user_id: str
    recruitment_id: UUID
    guild_id: str
    action_type: ActionType
    created_at: datetime


class ActivityLogRepository:
    """
    activity_logsテーブルへのデータアクセスを責務に持つクラス
    """

    def __init__(self, db_client: Client):
        self.db = db_client

    def create_log(
        self, user_id: str, recruitment_id: UUID, guild_id: str, action_type: ActionType
    ) -> None:
        """
        新しい活動履歴ログを作成する。
        Service層で参加/取消処理が行われる際に呼び出される。
        """
        self.db.table("activity_logs").insert(
            {
                "user_id": user_id,
                "recruitment_id": str(recruitment_id),
                "guild_id": guild_id,
                "action_type": action_type,
            }
        ).execute()

    def get_user_join_count_in_period(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> int:
        """
        指定された期間内に、特定のユーザーが募集に参加した回数を取得する。
        仕様書「2.7. 活動評価ロール機能」の「レギュラーメンバー」判定で使用。
        """
        response = (
            self.db.table("activity_logs")
            .select(
                "id",
                count="exact",  # レコードの件数のみを取得
            )
            .match({"user_id": user_id, "action_type": "join"})
            .gte(  # Greater than or equal to
                "created_at", start_date.isoformat()
            )
            .lte(  # Less than or equal to
                "created_at", end_date.isoformat()
            )
            .execute()
        )

        return response.count if response.count is not None else 0

    def get_guild_total_recruitment_count_in_period(
        self, guild_id: str, start_date: datetime, end_date: datetime
    ) -> int:
        """
        指定された期間内に、特定のサーバーで作成された募集の総数を取得する。
        仕様書「2.7. 活動評価ロール機能」の「幽霊部員」判定で使用。

        【設計判断】
        このメソッドは'recruitments'テーブルを参照しますが、「活動評価」という
        ユースケースで必要なデータ取得ロジックであるため、責務の凝集性を考慮して
        このActivityLogRepositoryに配置しています。
        """
        response = (
            self.db.table("recruitments")
            .select("id", count="exact")
            .eq("guild_id", guild_id)
            .gte("created_at", start_date.isoformat())
            .lte("created_at", end_date.isoformat())
            .execute()
        )

        return response.count if response.count is not None else 0
