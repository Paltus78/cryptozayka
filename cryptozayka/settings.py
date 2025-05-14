from __future__ import annotations   # ← обязан стоять первым

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings

# ────────────────────────── paths ────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_FILE  = ROOT_DIR / "cryptozayka.db"

# ────────────────────────── database dsn ─────────────────────────────────────
def _build_pg_dsn() -> str:
    """Возвращает DSN для asyncpg, приоритет: PG_DSN > POSTGRES_* env."""
    dsn = os.getenv("PG_DSN")
    if dsn:
        return dsn

    user = os.getenv("POSTGRES_USER", "zayka")
    pwd  = os.getenv("POSTGRES_PASSWORD", "secret")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB",   "zayka")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

PG_DSN = _build_pg_dsn()

# ────────────────────────── settings model ──────────────────────────────────
class Settings(BaseSettings):
    """Runtime configuration validated with Pydantic."""

    # ─── Database ───────────────────────────────────────────────────────────
    pg_dsn: str = Field(PG_DSN, alias="PG_DSN")

    # ─── EVM / RPC ──────────────────────────────────────────────────────────
    eth_rpc_url: str  = Field(..., env="ETH_RPC_URL",
                              description="HTTP(s) RPC endpoint")
    gas_price_gwei: int = Field(25, ge=1, le=500,
                                description="Default max gas price, GWei")
    chain_id: int = Field(1, env="CHAIN_ID",
                          description="EVM chain-id (1 = mainnet)")

    # ─── OpenAI ─────────────────────────────────────────────────────────────
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model:   str = Field("gpt-4o-mini", env="OPENAI_MODEL")

    # ─── Telegram ──────────────────────────────────────────────────────────
    telegram_token:      str | None = Field(None, env="TELEGRAM_TOKEN")
    telegram_admin_chat: int | str  = Field(...,  env="TELEGRAM_ADMIN_CHAT")

    # ─── Misc ──────────────────────────────────────────────────────────────
    db_path:   Path = Field(DB_FILE, env="DB_PATH")
    log_level: str  = Field("INFO",   env="LOG_LEVEL")

    # ─── validators ────────────────────────────────────────────────────────
    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        v_up = v.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if v_up not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v_up

    # ─── pydantic-settings config ──────────────────────────────────────────
    model_config = ConfigDict(
        env_file=".env",          # читать переменные из .env
        case_sensitive=False,     # KEY == key
        extra="ignore",           # игнорировать «лишние» env-ключи
    )


@lru_cache(maxsize=1)
def get_settings(**overrides: Any) -> Settings:
    """Возвращает кэшированный singleton-экземпляр Settings."""
    return Settings(**overrides)
