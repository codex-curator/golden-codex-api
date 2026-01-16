"""Application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # GCP
    gcp_project: str = "the-golden-codex-1111"
    gcp_region: str = "us-west1"
    firestore_database: str = "golden-codex-database"

    # Agent URLs
    nova_agent_url: str = "https://nova-agent-172867820131.us-west1.run.app"
    flux_agent_url: str = "https://flux-agent-172867820131.us-west1.run.app"
    atlas_agent_url: str = "https://atlas-agent-172867820131.us-west1.run.app"

    # Rate limiting defaults by tier
    rate_limit_free: int = 10
    rate_limit_curator: int = 30
    rate_limit_studio: int = 100
    rate_limit_gallery: int = 300

    # Token costs
    cost_nova_standard: int = 1
    cost_nova_full: int = 2
    cost_flux_2x: int = 1
    cost_flux_4x: int = 2
    cost_atlas: int = 1

    # Webhooks
    webhook_timeout: int = 30
    webhook_max_retries: int = 3

    # Cloud Tasks
    cloud_tasks_queue: str = "webhook-delivery"
    cloud_tasks_location: str = "us-west1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
