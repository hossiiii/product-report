from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    product_hunt_token: str = ""
    log_level: str = "INFO"

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def posts_dir(self) -> Path:
        return self.data_dir / "posts"

    @property
    def enriched_dir(self) -> Path:
        return self.data_dir / "enriched"

    @property
    def reports_dir(self) -> Path:
        return PROJECT_ROOT / "reports"

    @property
    def skill_dir(self) -> Path:
        return PROJECT_ROOT / ".claude" / "skills" / "research-japan-fit"

    @property
    def skill_schema_path(self) -> Path:
        return self.skill_dir / "SCHEMA.json"


settings = Settings()
