"""Dependency wiring and settings."""

from pydantic import BaseModel


class Settings(BaseModel):
    env: str = "dev"


def get_settings() -> Settings:
    return Settings()
