from supabase import Client, create_client

from config import settings


class Database:
    """
    Supabaseクライアントを管理するクラス
    """

    _instance: Client | None = None

    @classmethod
    def get_client(cls) -> Client:
        """
        Supabaseクライアントのインスタンスを取得

        Returns:
            Client: Supabaseクライアントのインスタンス
        """
        if cls._instance is None:
            try:
                cls._instance = create_client(
                    supabase_url=settings.SUPABASE_URL,
                    supabase_key=settings.SUPABASE_KEY,
                )
                print("Successfully connected to Supabase")
            except Exception as e:
                print(f"FATAL: Failled to connect to Supabase: {e}")
                raise

        return cls._instance


def get_db_client() -> Client:
    return Database.get_client()
