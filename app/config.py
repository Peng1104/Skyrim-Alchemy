"""
Application settings module.

`game_directory` and `log_language` are non-secret user preferences loaded
from `config.toml`. `game_directory` falls back to an auto-detected Skyrim
Special Edition install path (see `app.steam`) when unset; `log_language`
defaults to `"en"`.

These settings are only ever read by the CLI (`cli.py`) - the API never
touches `Settings` at all, and its one secret (`OCR_SERVICE_TOKEN`) is read
directly from the environment in `app/ocr_client.py`/`ocr_service/main.py`,
never through this class. Environment variable / `.env` support was
deliberately dropped here: `config.toml` was already the only source
actually in use (nothing in this project's Docker setup needs to inject
these via env var anymore), so keeping unused input sources around was just
a footgun waiting to confuse someone about precedence.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from app.steam import default_game_directory

Language = Literal["en", "pt", "de"]


class Settings(BaseSettings):
    """Application settings, loaded from `config.toml` (CLI use only)."""

    model_config = SettingsConfigDict(
        toml_file="config.toml",
        extra="ignore",
    )

    game_directory: str = Field(
        default_factory=default_game_directory,
        description="Path to the Skyrim game installation directory. Auto-detected "
                    "from the Steam client's libraryfolders.vdf when not set in config.toml.",
    )
    log_language: Language = Field(
        default="en",
        description="Language for console log messages: 'en', 'pt', or 'de'.",
    )

    plugins_txt_path: str | None = Field(
        default=None,
        description="Explicit path to the active-plugins list (a Mod Organizer 2 "
                    "profile's plugins.txt, or the native Skyrim Plugins.txt). "
                    "Auto-detected when unset - tries every MO2 profile under any "
                    "Steam library's Proton compatdata for this game, then the "
                    "native Plugins.txt location. Set this explicitly if "
                    "auto-detection picks the wrong MO2 profile/instance.",
    )

    perk_physician: bool = Field(
        default=False,
        description="Physician perk: potions AND poisons are 25% more powerful.",
    )
    perk_benefactor: bool = Field(
        default=False,
        description="Benefactor perk: potions with only beneficial effects are 25% more powerful.",
    )
    perk_poisoner: bool = Field(
        default=False,
        description="Poisoner perk: potions with only harmful effects (poisons) "
                    "are 25% more powerful.",
    )
    perk_purity: bool = Field(
        default=False,
        description="Purity perk: removes harmful effects from potions, and "
                    "beneficial effects from poisons.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define settings source priority: init > config.toml (env/.env intentionally excluded)."""
        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls),
        )


@lru_cache
def get_settings() -> Settings:
    """
    Get the cached application settings instance.

    Returns
    -------
    Settings
        The application settings, loaded once and cached.
    """
    return Settings()  # type: ignore[call-arg]
