"""
Application settings module.

`game_directory` and `log_language` are non-secret user preferences loaded from
`config.toml` (or GAME_DIRECTORY/LOG_LANGUAGE environment variables). `game_directory`
falls back to an auto-detected Skyrim Special Edition install path (see `app.steam`)
when unset; `log_language` defaults to `"en"`.

Note: the field is named `log_language`, not `language` - pydantic-settings maps
a field to the env var of the same name uppercased, and `LANGUAGE` is already a
common POSIX/gettext locale variable (e.g. `LANGUAGE=pt_BR:pt:en`) that many
systems set. Naming it `language` would silently pick that up and crash validation.
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
    """Application settings, merged from environment variables, `.env`, and `config.toml`."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
        """Define settings source priority: init > env > .env > config.toml > secrets file."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
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
