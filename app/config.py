"""P0 knobs. Live / broker mode is not implemented — SHADOW_ONLY must stay true."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.timeutil import parse_clock


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    shadow_only: bool = Field(
        default=True,
        validation_alias=AliasChoices("SHADOW_ONLY", "CHOCH_SHADOW_ONLY"),
    )
    pairs: tuple[str, ...] = Field(
        default=("EURUSD", "AUDUSD"),
        validation_alias=AliasChoices("PAIRS", "CHOCH_PAIRS"),
    )
    session_london: str = Field(
        default="16:00-20:59",
        validation_alias=AliasChoices("SESSION_LONDON", "CHOCH_SESSION_LONDON"),
    )
    session_ny: str = Field(
        default="09:00-12:00",
        validation_alias=AliasChoices("SESSION_NY", "CHOCH_SESSION_NY"),
    )
    ny_session_enabled: bool = Field(default=False)
    risk_usd: float = Field(
        default=100.0,
        validation_alias=AliasChoices("RISK_USD", "CHOCH_RISK_USD"),
    )
    be_at_r: float = Field(
        default=1.0,
        validation_alias=AliasChoices("BE_AT_R", "CHOCH_BE_AT_R"),
    )
    scalp_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("SCALP_MODE", "CHOCH_SCALP_MODE"),
    )
    stop_after_losses: int = 2
    sl_buffer_pips: float = 2.0
    pip_size: float = 0.0001
    asia_start: str = "07:00"
    asia_end: str = "15:59"
    flatten_clock: str = "21:00"
    two_year_flat: bool = False
    red_folder_buffer_min: int = 30
    news_stub_path: str = "data/news_stub.json"
    db_path: str = "data/choch.db"
    swing_left: int = 2
    swing_right: int = 2
    htf_min_move: float = 0.0008

    @field_validator("pairs", mode="before")
    @classmethod
    def _split_pairs(cls, value: object) -> object:
        if isinstance(value, str):
            parts = tuple(p.strip().upper() for p in value.replace(";", ",").split(",") if p.strip())
            return parts
        if isinstance(value, list):
            return tuple(str(v).upper() for v in value)
        return value

    @model_validator(mode="after")
    def _require_shadow(self) -> Self:
        if not self.shadow_only:
            raise ValueError(
                "Choch Rocket P0 is shadow-only. SHADOW_ONLY must remain true; "
                "live broker orders are out of scope."
            )
        return self

    @property
    def london_window(self) -> tuple:
        start_s, end_s = self.session_london.split("-")
        return parse_clock(start_s.strip()), parse_clock(end_s.strip())

    @property
    def asia_window(self) -> tuple:
        return parse_clock(self.asia_start), parse_clock(self.asia_end)

    @property
    def flatten_time(self):
        return parse_clock(self.flatten_clock)

    @property
    def be_trigger_r(self) -> float:
        return 0.5 if self.scalp_mode else self.be_at_r

    @property
    def sl_buffer(self) -> float:
        return self.sl_buffer_pips * self.pip_size

    def allowed_symbol(self, symbol: str) -> bool:
        return symbol.upper().replace("/", "") in self.pairs


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
