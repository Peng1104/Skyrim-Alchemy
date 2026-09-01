# Skyrim Alchemy Optimizer

🌐 [English](README.md) · [Português](README.pt.md) · [Deutsch](README.de.md)

Liest dein Skyrim-Inventar aus In-Game-Screenshots (per lokalem OCR), scrapt Zutaten-/Effektdaten von UESP und nutzt ganzzahlige lineare Programmierung (PuLP), um die wertvollsten Tränke zu berechnen, die du brauen kannst — und wie viele von jedem.

## So funktioniert es

1. **Screenshots**: `Druck`/`Print Screen` drücken, während die Zutatenliste im Spiel geöffnet ist. Skyrim speichert `ScreenShot<N>.png` direkt im Installationsordner des Spiels.
2. **OCR**: jeder Screenshot wird mit Tesseract gelesen, und der erkannte Text wird per Fuzzy-Matching mit der echten, von UESP gescrapten Zutatenliste abgeglichen (korrigiert OCR-Tippfehler, filtert UI-Rauschen).
3. **Optimierung**: anhand deiner Inventarmengen findet ein ILP-Solver die Kombination aus 2–3-Zutaten-Tränken, die den Gesamtgoldwert maximiert.

Die genaue Mathematik hinter der Gold-/Wertberechnung und dem Optimierer steht in [docs/calculation/CALCULATION.de.md](docs/calculation/CALCULATION.de.md).

Woher die Zutaten-/Effektdaten stammen und wie sie gescrapt und zwischengespeichert werden, steht in [docs/data-sources/DATA_SOURCES.de.md](docs/data-sources/DATA_SOURCES.de.md).

## Voraussetzungen

- [uv](https://docs.astral.sh/uv/) (verwaltet Python 3.14 und die Abhängigkeiten)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installiert und im `PATH` (`tesseract-ocr` + `tesseract-ocr-eng` unter Debian/Ubuntu) — nur außerhalb von Docker nötig
- Eine Skyrim-Special-Edition-Installation über Steam (für die automatische Erkennung des Spielverzeichnisses)

## Einrichtung

```bash
uv sync
cp config.example.toml config.toml   # optional - siehe Konfiguration unten
```

## Verwendung

### CLI

```bash
uv run run.py                    # kombiniert die gesamte Screenshot-Historie
uv run run.py --min 2 --max 5    # kombiniert nur die Screenshots 2 bis 5
uv run run.py --refresh          # ignoriert den OCR-Cache und liest jeden gefundenen Screenshot neu ein
uv run run.py --delete-old       # löscht nach dem Kombinieren jeden Screenshot, der bereits ein zwischengespeichertes OCR-Ergebnis hat
uv run run.py --delete-old 0-5   # ...oder nur die Screenshots 0 bis 5
uv run run.py --delete-cache     # löscht nach dem Kombinieren jedes zwischengespeicherte OCR-Ergebnis (behält die Screenshot-Bilder)
uv run run.py --list             # listet jede bekannte Screenshot-ID (Bild-/Cache-Verfügbarkeit) auf und beendet sich
uv run run.py --info             # zeigt die zwischengespeicherten Zutaten jedes Screenshots an und beendet sich
uv run run.py --info 2,4-6       # ...oder nur die Screenshots 2, 4, 5 und 6
```

`--delete-old`, `--delete-cache` und `--info` akzeptieren einen optionalen
Screenshot-ID-Selektor: eine einzelne ID (`2`), einen einschließenden
Bereich (`0-5`), oder eine durch Kommas getrennte Kombination (`0-2,4,6-8`).
Ohne Wert gelten sie für jede bekannte Screenshot-ID.

Die Ausgabe wird in der Konsole angezeigt und in `logs/<timestamp>.log` gespeichert.

### API

```bash
uv run python -m app   # startet uvicorn auf Port :8001
```

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| `GET` | `/health` | Verfügbarkeitsprüfung |
| `POST` | `/optimize/screenshots` | Lädt ein oder mehrere Inventar-Screenshots (PNG) plus Perk-Umschalter hoch und gibt die optimale Herstellungsreihenfolge zurück |
| `DELETE` | `/cache/pages` | Löscht alle zwischengespeicherten UESP-HTML-Seiten und erzwingt bei der nächsten Anfrage ein frisches Scraping |

`POST /optimize/screenshots` akzeptiert eine `multipart/form-data`-Anfrage:
ein oder mehrere `files`-Teile (nur PNG), plus die optionalen booleschen
Formularfelder `perk_physician`/`perk_benefactor`/`perk_poisoner`/
`perk_purity` (jeweils standardmäßig `false`). Erstreckt sich ein Inventar
über mehrere gescrollte Screenshots, lade sie alle in derselben Anfrage hoch
— die Werte aus späteren Dateien überschreiben für eine gegebene Zutat die
aus früheren, da jeder Screenshot die aktuelle Gesamtmenge zeigt, kein Delta.

Das OCR selbst läuft in einem isolierten `ocr`-Dienst (siehe Docker unten),
nicht im API-Prozess — die API verarbeitet hochgeladene Bilddaten nie selbst.

### Docker

```bash
export OCR_SERVICE_TOKEN=$(openssl rand -hex 32)
docker compose up -d --build
```

Das startet zwei Container: `app` (die API, veröffentlicht auf `:8001`) und
`ocr` (Tesseract, nur von `app` über ein rein internes Docker-Netzwerk
erreichbar — kein veröffentlichter Host-Port). `OCR_SERVICE_TOKEN` ist ein
gemeinsames Geheimnis zwischen den beiden, geprüft bei jeder internen
OCR-Anfrage; erzeuge pro Deployment ein neues, nie wiederverwenden oder
committen.

## Konfiguration

`config.toml`-Einstellungen (`game_directory`, `log_language`, die Perks)
werden nur vom CLI verwendet — die API liest sie überhaupt nicht, sie haben
also keine Auswirkung auf `docker compose up`. Auflösungsreihenfolge: Init >
`config.toml` > Standardwert.

| `config.toml`-Schlüssel | Standard | Beschreibung |
| :--- | :--- | :--- |
| `game_directory` | automatisch über Steam erkannt | Pfad zur Skyrim-Installation (wo Screenshots gespeichert werden) |
| `log_language` | `en` | Konsolen-Log-Sprache: `en`, `pt` oder `de` |
| `perk_physician` | `false` | +25% Stärke bei Heilung/Magicka/Ausdauer wiederherstellen |
| `perk_benefactor` | `false` | +25% auf wohltätige Effekte, bei Tränken, die von einem wohltätigen Effekt dominiert werden |
| `perk_poisoner` | `false` | +25% auf schädliche Effekte, bei Tränken, die von einem schädlichen Effekt dominiert werden (Gifte) |
| `perk_purity` | `false` | Setzt die Effekte entgegengesetzter Polarität in einem gemischten Trank auf null |

`game_directory` wird automatisch erkannt, indem die `libraryfolders.vdf` des Steam-Clients gelesen wird (deckt zusätzliche Bibliotheken auf anderen Laufwerken ab), unter Windows, Linux und macOS. Setze es explizit in `config.toml`, wenn du kein Steam nutzt oder die automatische Erkennung die falsche Installation wählt.

Die Alchemie-Fertigkeit, der Alchemist-Perk, Fortify-Alchemy-Ausrüstung und Seeker of Shadows werden **nicht modelliert** — sie skalieren jeden Effekt gleichmäßig, ändern also nicht, welches Rezept bevorzugt wird, sondern nur die absoluten Goldwerte.

## Cache

Alles, was gescrapt oder per OCR verarbeitet wird, wird unter `cache/` zwischengespeichert, sodass wiederholte Läufe nie Netzwerkaufrufe oder OCR wiederholen:

```
cache/
├── pages/         UESP-HTML-Seiten (Zutaten, Effekte, Prioritätsdaten pro Effekt)
├── screenshots/   Eine JSON-Datei pro OCR-Ergebnis eines Screenshots (<id>.json)
└── inventory/     marker.json - Buchführung über den zuletzt kombinierten Screenshot-Bereich
```

Lösche `cache/pages/` (oder rufe `DELETE /cache/pages` auf), um nach Änderungen der UESP-Daten ein frisches Scraping zu erzwingen. Lösche `cache/screenshots/<id>.json` (oder führe mit `--refresh` aus), um für einen bestimmten Screenshot ein erneutes OCR zu erzwingen.

## Entwicklung

```bash
make lint          # ruff + pyright (strict-Modus)
```

Docstrings folgen dem NumPy-Stil; die Typprüfung läuft im `strict`-Modus von pyright ohne inline-Unterdrückungen (siehe `typings/pytesseract/` für den lokalen Stub der einzigen ungetypten Abhängigkeit).
