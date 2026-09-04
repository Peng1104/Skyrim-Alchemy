"""
Console log message translation (en/pt/de), with placeholder support.

Every log line printed by the application goes through `translate()` instead
of being hardcoded in a single language, so `Settings.log_language` controls
the whole application's console output consistently.
"""
from typing import TypedDict

from app.config import get_settings


class Translations(TypedDict):
    """
    One message's translation into every supported language.

    Every field is required (no `NotRequired`) on purpose: adding a new
    language means adding a field here (plus to `Language` in
    `app/config.py`), and pyright's strict mode then flags every single
    `_MESSAGES` entry still missing that field - turning "forgot to
    translate a message" from a silent runtime `KeyError` (only when that
    specific message is actually printed in that language) into a
    type-check-time error covering the whole catalog at once.
    """

    en: str
    pt: str
    de: str


_MESSAGES: dict[str, Translations] = {
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
    "ocr_using_container": {
        "en": "🐳 ocr container detected - using it for OCR.",
        "pt": "🐳 Container ocr detectado - usando ele para o OCR.",
        "de": "🐳 ocr-Container erkannt - wird für OCR verwendet.",
    },
    "ocr_using_local_tesseract": {
        "en": "🖥️ ocr container not reachable - falling back to a local Tesseract install.",
        "pt": "🖥️ Container ocr não encontrado - usando instalação local do Tesseract.",
        "de": "🖥️ ocr-Container nicht erreichbar - Rückgriff auf lokale Tesseract-Installation.",
    },
    "ocr_container_failed_falling_back": {
        "en": "⚠️  ocr container request failed - falling back to local Tesseract "
              "for this screenshot.",
        "pt": "⚠️  Requisição ao container ocr falhou - usando Tesseract local "
              "para esta captura.",
        "de": "⚠️  Anfrage an den ocr-Container fehlgeschlagen - Rückgriff auf lokales "
              "Tesseract für diesen Screenshot.",
    },
    "ocr_unavailable": {
        "en": "Neither the ocr container nor a local Tesseract install is available. "
              "Start it with 'docker compose -f docker-compose.ocr.yml up -d', or "
              "install Tesseract locally (see README's Requirements section).",
        "pt": "Nem o container ocr nem uma instalação local do Tesseract estão "
              "disponíveis. Inicie-o com 'docker compose -f docker-compose.ocr.yml "
              "up -d', ou instale o Tesseract localmente (veja a seção de "
              "Requisitos do README).",
        "de": "Weder der ocr-Container noch eine lokale Tesseract-Installation sind "
              "verfügbar. Starte ihn mit 'docker compose -f docker-compose.ocr.yml "
              "up -d', oder installiere Tesseract lokal (siehe den "
              "Voraussetzungen-Abschnitt der README).",
    },
    "ocr_unavailable_error": {
        "en": "❌ {error}",
        "pt": "❌ {error}",
        "de": "❌ {error}",
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
    "cache_deleted": {
        "en": "🗑️ {count} cached OCR result(s) deleted.",
        "pt": "🗑️ {count} resultado(s) de OCR em cache apagado(s).",
        "de": "🗑️ {count} zwischengespeicherte(s) OCR-Ergebnis(se) gelöscht.",
    },
    "logs_deleted": {
        "en": "🗑️ {count} log file(s) deleted.",
        "pt": "🗑️ {count} arquivo(s) de log apagado(s).",
        "de": "🗑️ {count} Protokolldatei(en) gelöscht.",
    },
    "screenshot_list_header": {
        "en": "🗂️ Screenshots:",
        "pt": "🗂️ Capturas de tela:",
        "de": "🗂️ Screenshots:",
    },
    "screenshot_list_line": {
        "en": "   • {id}: image {image_mark}, cache {cache_mark}",
        "pt": "   • {id}: imagem {image_mark}, cache {cache_mark}",
        "de": "   • {id}: Bild {image_mark}, Cache {cache_mark}",
    },
    "screenshot_list_empty": {
        "en": "🗂️ No screenshots found (neither in the game directory nor cached).",
        "pt": "🗂️ Nenhuma captura de tela encontrada (nem no diretório do jogo, nem em cache).",
        "de": "🗂️ Keine Screenshots gefunden (weder im Spielverzeichnis noch im Cache).",
    },
    "marker_range_line": {
        "en": "📍 Last run: screenshots {min_id} to {max_id}.",
        "pt": "📍 Último run: capturas {min_id} a {max_id}.",
        "de": "📍 Letzter Lauf: Screenshots {min_id} bis {max_id}.",
    },
    "marker_range_empty": {
        "en": "📍 No run yet.",
        "pt": "📍 Nenhum run ainda.",
        "de": "📍 Noch kein Lauf.",
    },
    "next_range_line": {
        "en": "🆕 Next default run: screenshots {min_id} to {max_id}.",
        "pt": "🆕 Próximo run padrão: capturas {min_id} a {max_id}.",
        "de": "🆕 Nächster Standardlauf: Screenshots {min_id} bis {max_id}.",
    },
    "screenshot_info_header": {
        "en": "🖼️ Screenshot {id}:",
        "pt": "🖼️ Captura {id}:",
        "de": "🖼️ Screenshot {id}:",
    },
    "screenshot_info_image_line": {
        "en": "   image: {mark}",
        "pt": "   imagem: {mark}",
        "de": "   Bild: {mark}",
    },
    "screenshot_info_cache_line": {
        "en": "   cache: {mark}",
        "pt": "   cache: {mark}",
        "de": "   Cache: {mark}",
    },
    "screenshot_info_no_ingredients": {
        "en": "   ❌ No cached ingredients (not OCR'd yet).",
        "pt": "   ❌ Nenhum ingrediente em cache (ainda não processada).",
        "de": "   ❌ Keine zwischengespeicherten Zutaten (noch nicht per OCR erkannt).",
    },
    "cli_description": {
        "en": "Skyrim Alchemy Optimizer - CLI",
        "pt": "Skyrim Alchemy Optimizer - CLI",
        "de": "Skyrim Alchemy Optimizer - CLI",
    },
    "cli_help_min": {
        "en": "Lowest screenshot ID to combine. Requires --max. Without either, the "
              "range is resolved automatically: on the first ever run, from 0; when "
              "screenshots newer than the last run exist, from right after the last "
              "run's highest ID; otherwise, the same range as the last run "
              "(replaying it from cache).",
        "pt": "Menor ID de screenshot a combinar. Requer --max. Sem nenhum dos dois, o "
              "intervalo é resolvido automaticamente: na primeira execução, a partir "
              "de 0; quando há screenshots mais novos que o último run, a partir logo "
              "após o maior ID do último run; caso contrário, o mesmo intervalo do "
              "último run (reproduzido a partir do cache).",
        "de": "Niedrigste zu kombinierende Screenshot-ID. Erfordert --max. Ohne beide "
              "wird der Bereich automatisch aufgelöst: beim allerersten Lauf ab 0; "
              "wenn neuere Screenshots als der letzte Lauf existieren, direkt nach "
              "der höchsten ID des letzten Laufs; andernfalls derselbe Bereich wie "
              "beim letzten Lauf (aus dem Cache wiedergegeben).",
    },
    "cli_help_max": {
        "en": "Highest screenshot ID to combine. Requires --min. Without either, "
              "resolved automatically (see --min).",
        "pt": "Maior ID de screenshot a combinar. Requer --min. Sem nenhum dos dois, "
              "resolvido automaticamente (veja --min).",
        "de": "Höchste zu kombinierende Screenshot-ID. Erfordert --min. Ohne beide "
              "automatisch aufgelöst (siehe --min).",
    },
    "cli_help_refresh": {
        "en": "Ignore the per-screenshot cache within the selected range and re-run OCR.",
        "pt": "Ignora o cache por screenshot dentro do intervalo selecionado e "
              "reprocessa o OCR.",
        "de": "Ignoriert den Cache pro Screenshot innerhalb des gewählten Bereichs "
              "und führt das OCR erneut aus.",
    },
    "cli_help_delete_png": {
        "en": "Delete screenshot PNGs that already have a cached OCR result.",
        "pt": "Apaga os PNGs de screenshot que já têm um resultado de OCR em cache.",
        "de": "Löscht Screenshot-PNGs, die bereits ein zwischengespeichertes OCR-Ergebnis haben.",
    },
    "cli_help_delete_cache": {
        "en": "Delete cached OCR results (not the screenshot images themselves).",
        "pt": "Apaga resultados de OCR em cache (não as imagens dos screenshots).",
        "de": "Löscht zwischengespeicherte OCR-Ergebnisse (nicht die Screenshot-Bilder selbst).",
    },
    "cli_help_delete_logs": {
        "en": "Delete every saved run log under logs/, except this run's own.",
        "pt": "Apaga todo log de execução salvo em logs/, exceto o deste run.",
        "de": "Löscht jedes gespeicherte Lauf-Protokoll unter logs/, außer dem dieses Laufs.",
    },
    "cli_help_list": {
        "en": "List every known screenshot ID (image/cache availability), the last "
              "run's range, and the range the next default run would resolve to. "
              "Does not combine or optimize anything.",
        "pt": "Lista todo ID de screenshot conhecido (disponibilidade de "
              "imagem/cache), o intervalo do último run, e o intervalo que o "
              "próximo run padrão resolveria. Não combina nem otimiza nada.",
        "de": "Listet jede bekannte Screenshot-ID (Bild-/Cache-Verfügbarkeit), den "
              "Bereich des letzten Laufs und den Bereich auf, den der nächste "
              "Standardlauf auflösen würde. Kombiniert oder optimiert nichts.",
    },
    "cli_help_info": {
        "en": "Show image/cache availability and cached ingredients for one or more "
              "screenshots. Does not combine or optimize anything.",
        "pt": "Mostra disponibilidade de imagem/cache e os ingredientes em cache de "
              "um ou mais screenshots. Não combina nem otimiza nada.",
        "de": "Zeigt Bild-/Cache-Verfügbarkeit und zwischengespeicherte Zutaten für "
              "einen oder mehrere Screenshots. Kombiniert oder optimiert nichts.",
    },
    "cli_help_id_selector_suffix": {
        "en": "Without a value, applies to every known screenshot ID; with one, a "
              "single ID, a range like 0-5, or a comma-separated combination like "
              "0,2,4-6.",
        "pt": "Sem valor, aplica-se a todo ID de screenshot conhecido; com um valor, "
              "um ID único, um intervalo como 0-5, ou uma combinação separada por "
              "vírgulas como 0,2,4-6.",
        "de": "Ohne Wert gilt es für jede bekannte Screenshot-ID; mit Wert eine "
              "einzelne ID, ein Bereich wie 0-5, oder eine durch Kommas getrennte "
              "Kombination wie 0,2,4-6.",
    },
    "cli_error_min_max_together": {
        "en": "--min and --max must be given together.",
        "pt": "--min e --max devem ser passados juntos.",
        "de": "--min und --max müssen zusammen angegeben werden.",
    },
    "cli_error_invalid_range": {
        "en": "invalid range: '{part}'",
        "pt": "intervalo inválido: '{part}'",
        "de": "ungültiger Bereich: '{part}'",
    },
    "cli_error_invalid_range_order": {
        "en": "invalid range: '{part}' (start must be <= end)",
        "pt": "intervalo inválido: '{part}' (início deve ser <= fim)",
        "de": "ungültiger Bereich: '{part}' (Start muss <= Ende sein)",
    },
    "cli_error_invalid_screenshot_id": {
        "en": "invalid screenshot ID: '{part}'",
        "pt": "ID de screenshot inválido: '{part}'",
        "de": "ungültige Screenshot-ID: '{part}'",
    },
    "cli_error_no_ids_given": {
        "en": "no screenshot IDs given",
        "pt": "nenhum ID de screenshot informado",
        "de": "keine Screenshot-ID angegeben",
    },
    "cli_help_help": {
        "en": "Show this help message and exit.",
        "pt": "Mostra esta mensagem de ajuda e sai.",
        "de": "Zeigt diese Hilfemeldung an und beendet sich.",
    },
    "game_data_scan_no_plugins_txt": {
        "en": "🧩 No active-plugins list (Plugins.txt) found - the game-data "
              "cache could not be refreshed.",
        "pt": "🧩 Nenhuma lista de plugins ativos (Plugins.txt) encontrada - "
              "o cache de dados do jogo não pôde ser atualizado.",
        "de": "🧩 Keine Liste aktiver Plugins (Plugins.txt) gefunden - der "
              "Spieldaten-Cache konnte nicht aktualisiert werden.",
    },
    "game_data_scan_no_changes": {
        "en": "🧩 No plugin changes detected ({count} ingredient(s) cached).",
        "pt": "🧩 Nenhuma mudança de plugin detectada ({count} ingrediente(s) "
              "em cache).",
        "de": "🧩 Keine Plugin-Änderungen erkannt ({count} zwischengespeicherte "
              "Zutat(en)).",
    },
    "game_data_scan_complete": {
        "en": "🧩 Game data scanned: {ingredients} ingredient(s), {effects} effect(s).",
        "pt": "🧩 Dados do jogo escaneados: {ingredients} ingrediente(s), "
              "{effects} efeito(s).",
        "de": "🧩 Spieldaten gescannt: {ingredients} Zutat(en), {effects} Effekt(e).",
    },
    "game_data_scan_plugin_unreadable": {
        "en": "⚠️  Could not read plugin {filename} - skipped.",
        "pt": "⚠️  Não foi possível ler o plugin {filename} - ignorado.",
        "de": "⚠️  Plugin {filename} konnte nicht gelesen werden - übersprungen.",
    },
    "game_data_ingredient_unresolved": {
        "en": "⚠️  Could not resolve the display name of ingredient {edid} in "
              "{filename} - skipped.",
        "pt": "⚠️  Não foi possível resolver o nome de exibição do ingrediente "
              "{edid} em {filename} - ignorado.",
        "de": "⚠️  Der Anzeigename der Zutat {edid} in {filename} konnte nicht "
              "aufgelöst werden - übersprungen.",
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
