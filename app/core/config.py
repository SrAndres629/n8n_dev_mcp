"""
Configuration Management - Pydantic Settings
Securely loads and validates environment variables.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # n8n Configuration
    n8n_base_url: str = Field(default="http://localhost:5678/api/v1", alias="N8N_BASE_URL")
    n8n_api_key: str = Field(..., alias="N8N_API_KEY")
    n8n_data_dir: str = Field(
        default_factory=lambda: os.path.join(os.path.expanduser("~"), ".n8n"),
        alias="N8N_DATA_DIR"
    )
    n8n_editor_url: str = Field(default="http://localhost:5678", alias="N8N_EDITOR_URL")

    @property
    def api_url(self) -> str:
        """Ensure the API URL is correctly formatted."""
        url = self.n8n_base_url.rstrip("/")
        if not url.endswith("/api/v1"):
            url += "/api/v1"
        return url + "/"

    
    # Server Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # HTTP Client Configuration
    http_timeout: float = Field(default=30.0, alias="HTTP_TIMEOUT")
    http_retries: int = Field(default=3, alias="HTTP_RETRIES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings instance
settings = Settings()
