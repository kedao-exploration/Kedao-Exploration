from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_url: str = Field(validation_alias="PROJECT_URL")
    pub_key: str = Field(default="", validation_alias="PUB_KEY")
    secret_key: SecretStr = Field(validation_alias="SECRET_KEY")
    siliconflow_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="SILICONFLOW_API_KEY")
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1", validation_alias="SILICONFLOW_BASE_URL")
    siliconflow_model: str = Field(default="deepseek-ai/DeepSeek-V4-Flash", validation_alias="SILICONFLOW_MODEL")
    session_secret: SecretStr = Field(validation_alias="SESSION_SECRET")
    advisor_username: str = Field(default="kedao_college", validation_alias="ADVISOR_USERNAME")
    advisor_password_hash: SecretStr = Field(validation_alias="ADVISOR_PASSWORD_HASH")
    student_site_url: str = Field(default="https://kedao-exploration.github.io/Kedao-Exploration/", validation_alias="STUDENT_SITE_URL")
    data_dir: Path = Field(default=Path("./data"), validation_alias="DATA_DIR")
    snapshot_retention_days: int = Field(default=30, validation_alias="SNAPSHOT_RETENTION_DAYS")
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    timezone: str = "Asia/Shanghai"

    @property
    def rest_url(self) -> str:
        return f"{self.project_url.rstrip('/')}/rest/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
