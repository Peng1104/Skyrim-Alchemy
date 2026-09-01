# Skyrim Alchemy Optimizer

Reads your Skyrim inventory from in-game screenshots (via local OCR), scrapes ingredient/effect data from UESP, and uses integer linear programming (PuLP) to compute the most valuable potions you can brew — and how many of each.

## How it works

1. **Screenshots**: press `Print Screen` while your ingredients list is open in-game. Skyrim saves `ScreenShot<N>.png` directly into the game's install folder.
2. **OCR**: each screenshot is read with Tesseract, and recognized text is fuzzy-matched against the real ingredient list scraped from UESP (corrects OCR typos, filters out UI noise).
3. **Optimization**: given your inventory quantities, an ILP solver finds the combination of 2–3 ingredient potions that maximizes total gold value.

For the exact math behind the gold/value calculation and the optimizer, see `docs/calculation/`:
[English](docs/calculation/CALCULATION.en.md) · [Português](docs/calculation/CALCULATION.pt.md) · [Deutsch](docs/calculation/CALCULATION.de.md)

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.14 and dependencies)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on `PATH` (`tesseract-ocr` + `tesseract-ocr-eng` on Debian/Ubuntu) — only needed to run outside Docker
- A Skyrim Special Edition install via Steam (for game directory auto-detection)

## Setup

```bash
uv sync
cp config.example.toml config.toml   # optional - see Configuration below
```

## Usage

### CLI

```bash
uv run run.py                  # combine the whole screenshot history
uv run run.py --min 2 --max 5  # combine only screenshots 2 through 5
uv run run.py --refresh        # ignore the OCR cache and re-read every screenshot found
uv run run.py --delete-old     # delete screenshots that already have a cached OCR result
```

Output is printed to the console and saved to `logs/<timestamp>.log`.

### API

```bash
uv run python -m app   # starts uvicorn on :8001
```

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness check |
| `POST` | `/optimize` | Read the current inventory and return the optimal fabrication sequence |
| `DELETE` | `/cache/pages` | Delete all cached UESP HTML pages, forcing a fresh scrape on the next `/optimize` |

### Docker

```bash
export SKYRIM_SCREENSHOTS_DIR="/path/to/Skyrim Special Edition"
docker compose up -d --build
```

## Configuration

Settings are resolved in this order: init > environment variable > `.env` > `config.toml` > default.

| `config.toml` key | Env var | Default | Description |
| :--- | :--- | :--- | :--- |
| `game_directory` | `GAME_DIRECTORY` | auto-detected via Steam | Path to the Skyrim install (where screenshots are saved) |
| `log_language` | `LOG_LANGUAGE` | `en` | Console log language: `en`, `pt`, or `de` |
| `perk_physician` | `PERK_PHYSICIAN` | `false` | +25% magnitude on Restore Health/Magicka/Stamina |
| `perk_benefactor` | `PERK_BENEFACTOR` | `false` | +25% on beneficial effects, in potions dominated by a beneficial effect |
| `perk_poisoner` | `PERK_POISONER` | `false` | +25% on harmful effects, in potions dominated by a harmful effect (poisons) |
| `perk_purity` | `PERK_PURITY` | `false` | Zeroes out the opposite-polarity effects in a mixed potion |

`game_directory` is auto-detected by reading the Steam client's `libraryfolders.vdf` (covers extra libraries on other disks), on Windows, Linux, and macOS. Set it explicitly in `config.toml` if you don't use Steam, or if auto-detection picks the wrong install.

Alchemy skill, the Alchemist perk, Fortify Alchemy gear, and Seeker of Shadows are **not modeled** — they scale every effect uniformly, so they don't change which recipe is favored, only the absolute gold numbers.

## Cache

Everything scraped or OCR'd is cached under `cache/`, so repeated runs never redo network calls or OCR:

```
cache/
├── pages/         UESP HTML pages (ingredients, effects, per-effect priority data)
├── screenshots/   One JSON file per screenshot's OCR result (<id>.json)
└── inventory/     marker.json - bookkeeping for the last combined screenshot range
```

Delete `cache/pages/` (or call `DELETE /cache/pages`) to force a fresh scrape after UESP data changes. Delete `cache/screenshots/<id>.json` (or run with `--refresh`) to force re-OCR of a specific screenshot.

## Development

```bash
make lint          # ruff + pyright (strict mode)
```

Docstrings follow NumPy style; type checking runs in pyright `strict` mode with zero inline suppressions (see `typings/pytesseract/` for the one untyped dependency's local stub).
