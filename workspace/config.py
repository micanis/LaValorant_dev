# config.py (修正後の全文)

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    環境変数から設定を読み込むためのクラス。
    .envファイルやOSの環境変数を自動で読み込む。
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Discord Settings
    DISCORD_BOT_TOKEN: str
    # 【修正点】必須から任意項目に変更
    DISCORD_GUILD_ID: str | None = None

    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Riot API Settings
    RIOT_API_KEY: str
    RIOT_CLIENT_ID: str
    RIOT_CLIENT_SECRET: str

    # Web Server & OAuth Settings
    BASE_URL: str = "http://localhost:8080"
    REDIRECT_PATH: str = "/oauth/callback"
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = 8080

    # Security Settings
    ENCRYPTION_KEY: bytes

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    # Test Database Settings
    TEST_SUPABASE_URL: str | None = None
    TEST_SUPABASE_KEY: str | None = None

    @property
    def RIOT_REDIRECT_URI(self) -> str:
        return f"{self.BASE_URL.rstrip('/')}{self.REDIRECT_PATH}"


# アプリケーション全体でこのインスタンスをインポートして利用する
settings = Settings()
