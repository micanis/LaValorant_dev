from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    環境変数から設定を読み込むクラス
    .envファイルやOSの環境変数を自動で読み込む
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Discord Setting
    DISCORD_BOT_TOKEN: str

    # Supabase Setting
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Riot API Setting
    RIOT_API_KEY: str
    RIOT_CLIENT_ID: str
    RIOT_CLIENT_SECRET: str

    # Web Server Setting (OAuth Callback)
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = 8080
    BASE_URL: str = "https://9b61-220-148-240-93.ngrok-free.app"
    REDIRECT_PATH: str = "/oauth/callback"

    # Security Settings
    ENCRYPTION_KEY: bytes

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    @property
    def RIOT_REDIRECT_URI(self) -> str:
        return f"{self.BASE_URL}{self.REDIRECT_PATH}"


settings = Settings()
