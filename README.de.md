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
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installiert und im `PATH` (`tesseract-ocr` + `tesseract-ocr-eng` unter Debian/Ubuntu) — **nicht nötig**, wenn du stattdessen den Docker-Container mit nur OCR nutzt (siehe [Nur OCR](#nur-ocr-cli-ohne-tesseract-installation) unten); praktisch unter Windows, wo die Installation von Tesseract aufwändiger ist als unter Linux
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
uv run run.py -r                 # (--refresh) ignoriert den OCR-Cache und liest jeden gefundenen Screenshot neu ein
uv run run.py -p                 # (--delete-png) löscht jedes Screenshot-PNG, das bereits ein zwischengespeichertes OCR-Ergebnis hat, und beendet sich
uv run run.py -p 0-5             # ...oder nur die Screenshots 0 bis 5
uv run run.py -c                 # (--delete-cache) löscht jedes zwischengespeicherte OCR-Ergebnis (behält die PNGs), und beendet sich
uv run run.py -L                 # (--delete-logs) löscht jedes gespeicherte Lauf-Protokoll unter logs/ (außer dem dieses Laufs), und beendet sich
uv run run.py -l                 # (--list) listet jede bekannte Screenshot-ID (Bild-/Cache-Verfügbarkeit) auf und beendet sich
uv run run.py -i                 # (--info) zeigt die zwischengespeicherten Zutaten jedes Screenshots an und beendet sich
uv run run.py -i 2,4-6           # ...oder nur die Screenshots 2, 4, 5 und 6
```

`--delete-png`, `--delete-cache` und `--info` akzeptieren einen optionalen
Screenshot-ID-Selektor: eine einzelne ID (`2`), einen einschließenden
Bereich (`0-5`), oder eine durch Kommas getrennte Kombination (`0-2,4,6-8`).
Ohne Wert gelten sie für jede bekannte Screenshot-ID.

Die Ausgabe wird in der Konsole angezeigt und in `logs/<timestamp>.log` gespeichert.

### API

```bash
uv run python -m app   # startet uvicorn auf Port :8001
```

Das OCR selbst läuft in einem isolierten `ocr`-Dienst (siehe Docker unten),
nicht im API-Prozess — die API verarbeitet hochgeladene Bilddaten nie selbst.

Für das Anfrage-/Antwortformat jedes Endpunkts siehe [docs/api/API.de.md](docs/api/API.de.md).

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

### Nur OCR (CLI ohne Tesseract-Installation)

Wenn du Tesseract nicht lokal installieren möchtest, um das CLI zu
nutzen - der übliche Fall unter Windows - starte nur den `ocr`-Container,
diesmal auf dem Host veröffentlicht:

```bash
export OCR_SERVICE_TOKEN=$(openssl rand -hex 32)
docker compose -f docker-compose.ocr.yml up -d --build
uv run run.py
```

Unter Windows PowerShell gilt `export` nicht - setze die Umgebungsvariable
und erzeuge das Token stattdessen so:

```powershell
$env:OCR_SERVICE_TOKEN = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Minimum 0 -Maximum 256) })
docker compose -f docker-compose.ocr.yml up -d --build
uv run run.py
```

Der OCR-Pfad des CLI (`app/ocr_client.py`) wählt automatisch ein Backend,
in dieser Reihenfolge:

1. **Den `ocr`-Container**, falls er auf einen Health-Check unter
   `OCR_SERVICE_URL` antwortet (Standard `http://localhost:9000`, derselbe
   Port wie oben).
2. **Eine lokale Tesseract-Installation**, falls der Container nicht
   erreichbar ist.
3. Andernfalls gibt es eine klare Fehlermeldung aus und stoppt - nie ein
   roher Traceback.

Diese Entscheidung wird einmal pro CLI-Lauf getroffen und für jeden
Screenshot wiederverwendet, also kein Overhead pro Screenshot.
`OCR_SERVICE_TOKEN` muss zwischen diesem Container und dem, was deine
Shell beim Ausführen des CLI exportiert hat, übereinstimmen - dieselbe
Regel wie beim vollständigen Stack oben.

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
