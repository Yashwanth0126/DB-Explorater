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

    # SMTP (replaces Resend HTTP API). Common providers: Gmail (smtp.gmail.com:587,
    # use an App Password, not your normal password), SendGrid (smtp.sendgrid.net:587),
    # Mailgun (smtp.mailgun.org:587), or your own mail server.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True  # STARTTLS on 587. Set False + smtp_port=465 for implicit SSL.
    notification_from_email: str = "noreply@example.com"
    notification_from_name: str = "Credential Rotation System"
    notifications_enabled: bool = False


settings = Settings()