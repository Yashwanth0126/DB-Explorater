from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Credential Rotation System"
    env: str = "development"

    database_url: str = "sqlite:///./credential_rotation.db"

    jwt_secret_key: str = "change_this_to_a_random_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    encryption_key: str = ""

    admin_username: str = "admin"
    admin_password: str = "change_me_please"
    admin_email: str = "admin@example.com"

    scheduler_interval_minutes: int = 60

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    notifications_enabled: bool = False


settings = Settings()
