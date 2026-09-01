# Skyrim Alchemy Optimizer

🌐 [English](README.md) · [Português](README.pt.md) · [Deutsch](README.de.md)

Lê seu inventário do Skyrim a partir de screenshots do jogo (via OCR local), raspa dados de ingredientes/efeitos da UESP, e usa programação linear inteira (PuLP) para calcular as poções mais valiosas que você pode fabricar — e quantas de cada.

## Como funciona

1. **Screenshots**: pressione `Print Screen` com a lista de ingredientes aberta no jogo. O Skyrim salva `ScreenShot<N>.png` diretamente na pasta de instalação do jogo.
2. **OCR**: cada screenshot é lido com Tesseract, e o texto reconhecido é comparado (fuzzy match) com a lista real de ingredientes raspada da UESP (corrige erros de OCR, filtra ruído de UI).
3. **Otimização**: dadas as quantidades do seu inventário, um solver ILP encontra a combinação de poções de 2–3 ingredientes que maximiza o valor total em ouro.

Para a matemática exata por trás do cálculo de valor/ouro e do otimizador, veja [docs/calculation/CALCULATION.pt.md](docs/calculation/CALCULATION.pt.md).

Para saber de onde vêm os dados de ingredientes/efeitos e como são raspados e armazenados em cache, veja [docs/data-sources/DATA_SOURCES.pt.md](docs/data-sources/DATA_SOURCES.pt.md).

## Requisitos

- [uv](https://docs.astral.sh/uv/) (gerencia o Python 3.14 e as dependências)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) instalado e no `PATH` (`tesseract-ocr` + `tesseract-ocr-eng` no Debian/Ubuntu) — necessário apenas para rodar fora do Docker
- Uma instalação do Skyrim Special Edition via Steam (para detecção automática da pasta do jogo)

## Instalação

```bash
uv sync
cp config.example.toml config.toml   # opcional - veja Configuração abaixo
```

## Uso

### CLI

```bash
uv run run.py                    # combina todo o histórico de screenshots
uv run run.py --min 2 --max 5    # combina apenas os screenshots 2 a 5
uv run run.py --refresh          # ignora o cache de OCR e relê todo screenshot encontrado
uv run run.py --delete-old       # após combinar, apaga todo screenshot que já tem um resultado de OCR em cache
uv run run.py --delete-old 0-5   # ...ou apenas os screenshots 0 a 5
uv run run.py --delete-cache     # após combinar, apaga todo resultado de OCR em cache (mantém as imagens)
uv run run.py --list             # lista todo ID de screenshot conhecido (disponibilidade de imagem/cache) e sai
uv run run.py --info             # mostra os ingredientes em cache de todo screenshot e sai
uv run run.py --info 2,4-6       # ...ou apenas os screenshots 2, 4, 5 e 6
```

`--delete-old`, `--delete-cache` e `--info` aceitam um seletor de IDs de
screenshot opcional: um ID único (`2`), um intervalo inclusivo (`0-5`), ou
uma combinação separada por vírgulas (`0-2,4,6-8`). Sem valor, aplicam-se a
todo ID de screenshot conhecido.

A saída é impressa no console e salva em `logs/<timestamp>.log`.

### API

```bash
uv run python -m app   # inicia o uvicorn na porta :8001
```

| Método | Rota | Descrição |
| :--- | :--- | :--- |
| `GET` | `/health` | Verificação de disponibilidade |
| `POST` | `/optimize` | Lê o inventário atual e retorna a sequência de fabricação ótima |
| `DELETE` | `/cache/pages` | Apaga todas as páginas HTML da UESP em cache, forçando uma nova raspagem na próxima `/optimize` |

### Docker

```bash
export SKYRIM_SCREENSHOTS_DIR="/path/to/Skyrim Special Edition"
docker compose up -d --build
```

## Configuração

As configurações são resolvidas nesta ordem: init > variável de ambiente > `.env` > `config.toml` > padrão.

| Chave em `config.toml` | Variável de ambiente | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `game_directory` | `GAME_DIRECTORY` | detectado automaticamente via Steam | Caminho da instalação do Skyrim (onde os screenshots são salvos) |
| `log_language` | `LOG_LANGUAGE` | `en` | Idioma do log no console: `en`, `pt`, ou `de` |
| `perk_physician` | `PERK_PHYSICIAN` | `false` | +25% de magnitude em Restaurar Vida/Magicka/Vigor |
| `perk_benefactor` | `PERK_BENEFACTOR` | `false` | +25% em efeitos benéficos, em poções dominadas por um efeito benéfico |
| `perk_poisoner` | `PERK_POISONER` | `false` | +25% em efeitos nocivos, em poções dominadas por um efeito nocivo (venenos) |
| `perk_purity` | `PERK_PURITY` | `false` | Zera os efeitos de polaridade oposta em uma poção mista |

`game_directory` é detectado automaticamente lendo o `libraryfolders.vdf` do cliente Steam (cobre bibliotecas extras em outros discos), no Windows, Linux e macOS. Defina-o explicitamente em `config.toml` se você não usa Steam, ou se a detecção automática escolher a instalação errada.

A perícia de Alquimia, o perk Alchemist, equipamentos com Fortify Alchemy, e Seeker of Shadows **não são modelados** — eles escalam todo efeito uniformemente, então não mudam qual receita é favorecida, apenas os números absolutos de ouro.

## Cache

Tudo que é raspado ou processado por OCR fica em cache sob `cache/`, então execuções repetidas nunca refazem chamadas de rede ou OCR:

```
cache/
├── pages/         Páginas HTML da UESP (ingredientes, efeitos, dados de prioridade por efeito)
├── screenshots/   Um arquivo JSON por resultado de OCR de screenshot (<id>.json)
└── inventory/     marker.json - controle do último intervalo de screenshots combinado
```

Apague `cache/pages/` (ou chame `DELETE /cache/pages`) para forçar uma nova raspagem depois que os dados da UESP mudarem. Apague `cache/screenshots/<id>.json` (ou rode com `--refresh`) para forçar um novo OCR de um screenshot específico.

## Desenvolvimento

```bash
make lint          # ruff + pyright (modo strict)
```

As docstrings seguem o estilo NumPy; a checagem de tipos roda em modo `strict` do pyright, sem nenhuma supressão inline (veja `typings/pytesseract/` para o stub local da única dependência sem tipos).
