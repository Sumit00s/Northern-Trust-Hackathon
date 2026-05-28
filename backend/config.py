"""
IMS Configuration — loaded from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    postgres_user: str = "ims_user"
    postgres_password: str = "ims_secret_2024"
    postgres_db: str = "ims_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "ims_signals"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Application
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    rate_limit_per_second: int = 15000
    buffer_max_size: int = 50000

    # SMTP / Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "your-email@gmail.com"
    smtp_password: str = "your-app-password"

    # Email Recipients
    oncall_email: str = "oncall@company.com"
    app_team_email: str = "appteam@company.com"
    senior_email: str = "senior@company.com"

    # Escalation Settings
    escalation_timeout_minutes: int = 5
    reminder_timeout_minutes: int = 30

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
