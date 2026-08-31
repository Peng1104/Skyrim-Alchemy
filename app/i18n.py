"""
Console log message translation (en/pt/de), with placeholder support.

Every log line printed by the application goes through `translate()` instead
of being hardcoded in a single language, so `Settings.log_language` controls
the whole application's console output consistently.
"""
from app.config import Language, get_settings

_MESSAGES: dict[str, dict[Language, str]] = {
    "inventory_initial_header": {
        "en": "📦 INITIAL INVENTORY:",
        "pt": "📦 INVENTÁRIO INICIAL:",
        "de": "📦 ANFANGSINVENTAR:",
    },
    "ingredient_line": {
        "en": "   • {name}: {amount}",
        "pt": "   • {name}: {amount}",
        "de": "   • {name}: {amount}",
    },
    "no_ingredients_found": {
        "en": "❌ No ingredients found in the inventory.",
        "pt": "❌ Nenhum ingrediente encontrado no inventário.",
        "de": "❌ Keine Zutaten im Inventar gefunden.",
    },
    "starting_effects_analysis": {
        "en": "🔍 STARTING EFFECTS ANALYSIS...",
        "pt": "🔍 INICIANDO ANÁLISE DE EFEITOS...",
        "de": "🔍 EFFEKTANALYSE WIRD GESTARTET...",
    },
    "no_potions_fabricated": {
        "en": "❌ No potion was fabricated. Check the inventory and the ingredient/effect data.",
        "pt": "❌ Nenhuma poção foi fabricada. Verifique o inventário e os "
              "dados de ingredientes/efeitos.",
        "de": "❌ Es wurde kein Trank hergestellt. Überprüfe das Inventar und "
              "die Zutaten-/Effektdaten.",
    },
    "fabrication_stats_header": {
        "en": "📊 FABRICATION STATISTICS:",
        "pt": "📊 ESTATÍSTICAS DE FABRICAÇÃO:",
        "de": "📊 HERSTELLUNGSSTATISTIK:",
    },
    "total_recipes": {
        "en": "   • Total Recipes: {count}",
        "pt": "   • Total de Receitas: {count}",
        "de": "   • Rezepte insgesamt: {count}",
    },
    "total_potions": {
        "en": "   • Total Potions: {count}",
        "pt": "   • Total de poções: {count}",
        "de": "   • Tränke insgesamt: {count}",
    },
    "fabrication_sequence_header": {
        "en": "📋 Fabrication sequence details:",
        "pt": "📋 Detalhes da sequência de fabricação:",
        "de": "📋 Details zur Herstellungsreihenfolge:",
    },
    "recipe_line": {
        "en": "   {order}. {count}x {ingredients}",
        "pt": "   {order}. {count}x {ingredients}",
        "de": "   {order}. {count}x {ingredients}",
    },
    "remaining_ingredients_header": {
        "en": "\n📦 Remaining ingredients:",
        "pt": "\n📦 Ingredientes restantes:",
        "de": "\n📦 Übrige Zutaten:",
    },
    "all_ingredients_used": {
        "en": "   ✅ All ingredients were used!",
        "pt": "   ✅ Todos os ingredientes foram utilizados!",
        "de": "   ✅ Alle Zutaten wurden verwendet!",
    },
    "missing_ingredients_warning": {
        "en": "\n⚠️  WARNING: {count} inventory ingredient(s) not found in the data:",
        "pt": "\n⚠️  AVISO: {count} ingrediente(s) do inventário não encontrado(s) nos dados:",
        "de": "\n⚠️  WARNUNG: {count} Zutat(en) aus dem Inventar wurden in den "
              "Daten nicht gefunden:",
    },
    "missing_ingredient_line": {
        "en": "   • {name} - This ingredient was ignored",
        "pt": "   • {name} - Este ingrediente foi ignorado",
        "de": "   • {name} - Diese Zutat wurde ignoriert",
    },
    "reading_screenshot": {
        "en": "📸 Reading screenshot {id}...",
        "pt": "📸 Lendo captura de tela {id}...",
        "de": "📸 Screenshot {id} wird gelesen...",
    },
    "error_loading_image": {
        "en": "ERROR while loading {filename}: {error}",
        "pt": "ERRO ao carregar {filename}: {error}",
        "de": "FEHLER beim Laden von {filename}: {error}",
    },
    "screenshot_processed": {
        "en": "📸 Screenshot {id} processed.",
        "pt": "📸 Captura de tela {id} processada.",
        "de": "📸 Screenshot {id} verarbeitet.",
    },
    "no_screenshots_found": {
        "en": "🗂️ No screenshots found in the game directory.",
        "pt": "🗂️ Nenhuma captura de tela encontrada no diretório do jogo.",
        "de": "🗂️ Keine Screenshots im Spielverzeichnis gefunden.",
    },
    "ingredients_combined_range": {
        "en": "🗂️ Using {count} ingredient(s) (based on screenshots {min_id} to {max_id}, "
              "{new_count} freshly OCR'd).",
        "pt": "🗂️ Usando {count} ingrediente(s) (baseado nas capturas {min_id} a {max_id}, "
              "{new_count} processada(s) agora).",
        "de": "🗂️ Verwende {count} Zutat(en) (basierend auf Screenshots {min_id} bis "
              "{max_id}, {new_count} neu erkannt).",
    },
    "ingredients_combined_empty": {
        "en": "🗂️ No ingredients combined (no screenshots in the selected range).",
        "pt": "🗂️ Nenhum ingrediente combinado (nenhuma captura no range selecionado).",
        "de": "🗂️ Keine Zutaten kombiniert (keine Screenshots im ausgewählten Bereich).",
    },
    "active_perks": {
        "en": "🧪 Active perks: {perks}",
        "pt": "🧪 Perks ativos: {perks}",
        "de": "🧪 Aktive Perks: {perks}",
    },
    "no_active_perks": {
        "en": "🧪 No alchemy perks active (Physician/Benefactor/Poisoner/Purity).",
        "pt": "🧪 Nenhum perk de alquimia ativo (Physician/Benefactor/Poisoner/Purity).",
        "de": "🧪 Keine Alchemie-Perks aktiv (Physician/Benefactor/Poisoner/Purity).",
    },
    "game_directory_not_found": {
        "en": "Unable to find the game directory: {path}",
        "pt": "Não foi possível encontrar o diretório do jogo: {path}",
        "de": "Spielverzeichnis konnte nicht gefunden werden: {path}",
    },
    "analyzing_inventory": {
        "en": "🔍 Analyzing Skyrim inventory...",
        "pt": "🔍 Analisando o inventário do Skyrim...",
        "de": "🔍 Skyrim-Inventar wird analysiert...",
    },
    "screenshots_deleted": {
        "en": "🗑️ {count} screenshot(s) deleted (already processed).",
        "pt": "🗑️ {count} captura(s) de tela apagada(s) (já processada(s)).",
        "de": "🗑️ {count} Screenshot(s) gelöscht (bereits verarbeitet).",
    },
}


def translate(key: str, /, **placeholders: object) -> str:
    """
    Translate a log message key into the configured language, filling in placeholders.

    Parameters
    ----------
    key : str
        Message catalog key (see `_MESSAGES`).
    **placeholders : object
        Values to interpolate into the message template (e.g. `id=3`).

    Returns
    -------
    str
        The translated, formatted message.

    Raises
    ------
    KeyError
        If `key` is not a known message.
    """
    language = get_settings().log_language
    template = _MESSAGES[key][language]

    return template.format(**placeholders)
