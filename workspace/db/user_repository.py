from datetime import datetime
from typing import List, Optional

from cryptography.fernet import Fernet
from pydantic import BaseModel
from supabase import Client


class User(BaseModel):
    """
    usersテーブルのデータを表現するPydanticモデル
    """

    discord_id: str
    riot_puuid: Optional[str] = None
    riot_access_token: Optional[str] = None
    riot_refresh_token: Optional[str] = None
    created_at: datetime
    updated_ad: datetime

    class Config:
        orm_mode = True


class UserRepository:
    """
    usersテーブルへのデータアクセスを責務にもつクラス
    """

    def __init__(self, db_client: Client, encryption_key: bytes):
        """
        Args:
            db_client (Client): Supabaseクライアント
            encryption_key (bytes): トークン暗号化・復号化用のキー
        """
        self.db = db_client
        self.fernet = Fernet(encryption_key)

    def _encrypt(self, data: str) -> str:
        """文字列を暗号化する"""
        return self.fernet.encrypt(data.encode()).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        """暗号化された文字列を復号化する"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def upsert_user(
        self, discord_id: str, riot_puuid: str, access_token: str, refresh_token: str
    ) -> Optional[User]:
        """
        ユーザー情報を登録または更新する (Upsert)
        トークンは暗号化して保存する
        """
        encrypted_access_token = self._encrypt(access_token)
        encrypted_refresh_token = self._encrypt(refresh_token)

        response = (
            self.db.table("users")
            .upsert(
                {
                    "discord_id": discord_id,
                    "riot_puuid": riot_puuid,
                    "riot_access_token": encrypted_access_token,
                    "riot_refresh_token": encrypted_refresh_token,
                    "updated_at": "now()",
                }
            )
            .execute()
        )

        if response.data:
            user_data = response.data[0]
            user_data["riot_access_token"] = access_token
            user_data["riot_refresh_token"] = refresh_token
            return User.model_validate(user_data)
        return None

    def get_all_linked_users(self) -> List[User]:
        """
        Riotアカウントと連携済みの全ユーザーを取得する
        """
        response = (
            self.db.table("users").select("*").not_.is_("riot_puuid", "null").execute()
        )

        users = []
        if response.data:
            for user_data in response.data:
                if user_data.get("riot_access_token"):
                    user_data["riot_access_token"] = self._decrypt(
                        user_data["riot_access_token"]
                    )
                if user_data.get("riot_refresh_token"):
                    user_data["riot_refresh_token"] = self._decrypt(
                        user_data["riot_refresh_token"]
                    )
                users.append(User.model_validate(user_data))
        return users
