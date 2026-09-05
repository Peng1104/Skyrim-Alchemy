# Skyrim Alchemy Optimizer

🌐 [English](README.md) · [Português](README.pt.md) · [Deutsch](README.de.md)

Reads your Skyrim inventory from in-game screenshots (via local OCR), reads ingredient/effect data directly from your own game's plugin files, and uses integer linear programming (PuLP) to compute the most valuable potions you can brew and how many of each.

## How it works

1. **Screenshots**: press `Print Screen` while your ingredients list is open in-game. Skyrim saves `ScreenShot<N>.png` directly into the game's install folder or, under Mod Organizer 2, into that instance's `overwrite/Root` folder instead (MO2 virtualizes the game's writes); both locations are scanned automatically.
2. **OCR**: each screenshot is read with Tesseract, and recognized text is fuzzy-matched against the real ingredient list read from your active plugins (corrects OCR typos, filters out UI noise).
3. **Optimization**: given your inventory quantities, an ILP solver finds the combination of 2–3 ingredient potions that maximizes total gold value. See [docs/calculation/CALCULATION.md](docs/calculation/CALCULATION.md) for the exact math, and [docs/data-sources/DATA_SOURCES.md](docs/data-sources/DATA_SOURCES.md) (plus [docs/game_data/GAME_DATA.md](docs/game_data/GAME_DATA.md) for override resolution) for where the ingredient/effect data itself comes from.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.14 and dependencies)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on `PATH` (`tesseract-ocr` + `tesseract-ocr-eng` on Debian/Ubuntu), **not needed** if you run the OCR-only Docker container instead (see [OCR only](#ocr-only-cli-without-installing-tesseract) below); handy on Windows, where installing Tesseract is more involved than on Linux
- A Skyrim Special Edition install via Steam (for game directory auto-detection)

## Setup

```bash
uv sync
cp config.example.toml config.toml   # optional - see Configuration below
```

## Usage

### CLI

```bash
uv run cli.py                    # combine the whole screenshot history
uv run cli.py --min 2 --max 5    # combine only screenshots 2 through 5
uv run cli.py -r                 # (--refresh) ignore the OCR cache and re-read every screenshot found
uv run cli.py -p                 # (--delete-png) delete every screenshot PNG that already has a cached OCR result, and exit
uv run cli.py -p 0-5             # ...or only screenshots 0 through 5
uv run cli.py -c                 # (--delete-cache) delete every cached OCR result (keeps the screenshot PNGs), and exit
uv run cli.py -L                 # (--delete-logs) delete every saved run log under logs/ (except this run's own), and exit
uv run cli.py -l                 # (--list) list every known screenshot ID (image/cache availability) and exit
uv run cli.py -i                 # (--info) show cached ingredients for every screenshot and exit
uv run cli.py -i 2,4-6           # ...or only screenshots 2, 4, 5, and 6
```

`--delete-png`, `--delete-cache`, and `--info` take an optional screenshot ID
selector: a single ID (`2`), an inclusive range (`0-5`), or a comma-separated
combination (`0-2,4,6-8`). Without a value, they apply to every known
screenshot ID.

Output is printed to the console and saved to `logs/<timestamp>.log`.

### API

```bash
uv run python -m app   # starts uvicorn on :8001
```

OCR itself runs in an isolated `ocr` service (see Docker below), not in the
API process, so that the API never parses uploaded image directly. See
[docs/api/API.md](docs/api/API.md) for every endpoint's full request/response
shape.

### Docker

```bash
export OCR_SERVICE_TOKEN=$(openssl rand -hex 32)
docker compose up -d --build
```

This starts two containers: `app` (the API, published on `:8001`) and `ocr`
(Tesseract, reachable only from `app` over an internal-only Docker network,
no published host port). `OCR_SERVICE_TOKEN` is a shared secret between the
two, checked on every internal OCR request; generate a fresh one per
deployment, never reuse or commit it.

### OCR only (CLI without installing Tesseract)

If you'd rather not install Tesseract locally to run the CLI - the common
case on Windows - run just the `ocr` container standalone, published on the
host this time:

```bash
export OCR_SERVICE_TOKEN=$(openssl rand -hex 32)
docker compose -f docker-compose.ocr.yml up -d --build
uv run cli.py
```

On Windows PowerShell, `export` doesn't apply - set the env var and generate
the token like this instead:

```powershell
$env:OCR_SERVICE_TOKEN = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Minimum 0 -Maximum 256) })
docker compose -f docker-compose.ocr.yml up -d --build
uv run cli.py
```

The CLI picks an OCR backend automatically, in this order:

1. **The `ocr` container**, if it answers a health check at `OCR_SERVICE_URL`
   (defaults to `http://localhost:9000`, matching the port above).
2. **A local Tesseract install**, if the container isn't reachable.
3. Otherwise, it prints a clear error and stops - it never crashes with a
   raw traceback.

This choice is made once per CLI run and reused for every screenshot, so
there's no per-screenshot overhead. `OCR_SERVICE_TOKEN` must match between
this container and whatever your shell has exported when you run the CLI -
same rule as the full stack above.

## Configuration

`config.toml` settings (`game_directory`, `plugins_txt_path`, `log_language`,
the perk flags) are only used by the CLI; the API doesn't read them at all,
so they have no effect on `docker compose up`. Resolution order: init >
`config.toml` > default.

| `config.toml` key | Default | Description |
| :--- | :--- | :--- |
| `game_directory` | auto-detected via Steam | Path to the Skyrim install (where screenshots are saved) |
| `plugins_txt_path` | auto-detected | Explicit path to the active-plugins list (an MO2 profile's `plugins.txt`, or the native `Plugins.txt`) |
| `log_language` | `en` | Console log language: `en`, `pt`, or `de` |
| `perk_physician` | `false` | +25% magnitude on Restore Health/Magicka/Stamina |
| `perk_benefactor` | `false` | +25% on beneficial effects, in potions dominated by a beneficial effect |
| `perk_poisoner` | `false` | +25% on harmful effects, in potions dominated by a harmful effect (poisons) |
| `perk_purity` | `false` | Zeroes out the opposite-polarity effects in a mixed potion |

`game_directory` is auto-detected by reading the Steam client's `libraryfolders.vdf` (covers extra libraries on other disks), on Windows, Linux, and macOS. Set it explicitly in `config.toml` if you don't use Steam, or if auto-detection picks the wrong install.

`plugins_txt_path` is auto-detected by trying every Mod Organizer 2 profile under any Steam library's Proton compatdata prefix for this game, then the native (non-MO2) `Plugins.txt` location for the current OS. Set it explicitly if you run multiple MO2 instances/profiles and auto-detection picks the wrong one.

## Cache

Everything read from plugins or OCR'd is cached under `cache/`, so repeated runs never redo a plugin scan or OCR:

```
cache/
├── game_data/
│   ├── plugins/
│   ├── ingredients.json
│   └── effects.json
├── screenshots/
└── inventory/
```

Run the CLI with `--refresh` (`-r`) to force a fresh plugin scan after installing/removing/reordering mods; `cache/game_data/` isn't touched otherwise. Delete `cache/screenshots/<id>.json` (or run with `--refresh`) to force re-OCR of a specific screenshot.

See [docs/cache/plugin/PLUGIN_CACHE.md](docs/cache/plugin/PLUGIN_CACHE.md), [docs/cache/ingredients/INGREDIENTS_CACHE.md](docs/cache/ingredients/INGREDIENTS_CACHE.md), and [docs/cache/effects/EFFECTS_CACHE.md](docs/cache/effects/EFFECTS_CACHE.md) for exactly what each file contains and how it's populated.

## Development

```bash
make lint          # ruff + pyright (strict mode)
```

Docstrings follow NumPy style; type checking runs in pyright `strict` mode with zero inline suppressions (see `typings/pytesseract/` for the one untyped dependency's local stub).

This project depends on two lightly-used third-party libraries to read Skyrim's own binary plugin/archive formats; see [docs/dependencies/DEPENDENCIES.md](docs/dependencies/DEPENDENCIES.md) for what was verified about them and the version-pinning risk that follows.
