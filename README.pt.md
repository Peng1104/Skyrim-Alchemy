# Skyrim Alchemy Optimizer

🌐 [English](README.md) · [Português](README.pt.md) · [Deutsch](README.de.md)

Lê seu inventário do Skyrim a partir de screenshots do jogo (via OCR local), lê dados de ingredientes/efeitos diretamente dos plugins do seu próprio jogo, e usa programação linear inteira (PuLP) para calcular as poções mais valiosas que você pode fabricar — e quantas de cada.

## Como funciona

1. **Screenshots**: pressione `Print Screen` com a lista de ingredientes aberta no jogo. O Skyrim salva `ScreenShot<N>.png` diretamente na pasta de instalação do jogo — ou, no Mod Organizer 2, na pasta `overwrite/Root` daquela instância (o MO2 virtualiza as gravações do jogo); ambos os locais são escaneados automaticamente.
2. **OCR**: cada screenshot é lido com Tesseract, e o texto reconhecido é comparado (fuzzy match) com a lista real de ingredientes lida dos seus plugins ativos (corrige erros de OCR, filtra ruído de UI).
3. **Otimização**: dadas as quantidades do seu inventário, um solver ILP encontra a combinação de poções de 2–3 ingredientes que maximiza o valor total em ouro.

Para a matemática exata por trás do cálculo de valor/ouro e do otimizador, veja [docs/calculation/CALCULATION.pt.md](docs/calculation/CALCULATION.pt.md).

Para saber de onde vêm os dados de ingredientes/efeitos e como são lidos e armazenados em cache, veja [docs/data-sources/DATA_SOURCES.pt.md](docs/data-sources/DATA_SOURCES.pt.md).

## Requisitos

- [uv](https://docs.astral.sh/uv/) (gerencia o Python 3.14 e as dependências)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) instalado e no `PATH` (`tesseract-ocr` + `tesseract-ocr-eng` no Debian/Ubuntu) — **não é necessário** se você rodar o container Docker somente-OCR (veja [Somente OCR](#somente-ocr-cli-sem-instalar-tesseract) abaixo); útil no Windows, onde instalar o Tesseract é mais trabalhoso do que no Linux
- Uma instalação do Skyrim Special Edition via Steam (para detecção automática da pasta do jogo)

## Instalação

```bash
uv sync
cp config.example.toml config.toml   # opcional - veja Configuração abaixo
```

## Uso

### CLI

```bash
uv run cli.py                    # combina todo o histórico de screenshots
uv run cli.py --min 2 --max 5    # combina apenas os screenshots 2 a 5
uv run cli.py -r                 # (--refresh) ignora o cache de OCR e relê todo screenshot encontrado
uv run cli.py -p                 # (--delete-png) apaga todo PNG de screenshot que já tem um resultado de OCR em cache, e sai
uv run cli.py -p 0-5             # ...ou apenas os screenshots 0 a 5
uv run cli.py -c                 # (--delete-cache) apaga todo resultado de OCR em cache (mantém os PNGs), e sai
uv run cli.py -L                 # (--delete-logs) apaga todo log de execução salvo em logs/ (exceto o deste run), e sai
uv run cli.py -l                 # (--list) lista todo ID de screenshot conhecido (disponibilidade de imagem/cache) e sai
uv run cli.py -i                 # (--info) mostra os ingredientes em cache de todo screenshot e sai
uv run cli.py -i 2,4-6           # ...ou apenas os screenshots 2, 4, 5 e 6
```

`--delete-png`, `--delete-cache` e `--info` aceitam um seletor de IDs de
screenshot opcional: um ID único (`2`), um intervalo inclusivo (`0-5`), ou
uma combinação separada por vírgulas (`0-2,4,6-8`). Sem valor, aplicam-se a
todo ID de screenshot conhecido.

A saída é impressa no console e salva em `logs/<timestamp>.log`.

### API

```bash
uv run python -m app   # inicia o uvicorn na porta :8001
```

O OCR em si roda num serviço `ocr` isolado (veja Docker abaixo), não no
processo da API — a API nunca processa os bytes da imagem enviada diretamente.

Para o formato de entrada/saída de cada endpoint, veja [docs/api/API.pt.md](docs/api/API.pt.md).

### Docker

```bash
export OCR_SERVICE_TOKEN=$(openssl rand -hex 32)
docker compose up -d --build
```

Isso sobe dois containers: `app` (a API, publicada em `:8001`) e `ocr`
(Tesseract, alcançável só pelo `app` via uma rede Docker interna — sem porta
publicada no host). `OCR_SERVICE_TOKEN` é um segredo compartilhado entre os
dois, checado em toda requisição interna de OCR; gere um novo por deploy,
nunca reutilize ou comite esse valor.

### Somente OCR (CLI sem instalar Tesseract)

Se você preferir não instalar o Tesseract localmente para rodar o CLI —
o caso comum no Windows — suba só o container `ocr`, dessa vez publicado
no host:

```bash
export OCR_SERVICE_TOKEN=$(openssl rand -hex 32)
docker compose -f docker-compose.ocr.yml up -d --build
uv run cli.py
```

No Windows PowerShell, `export` não se aplica — defina a variável e gere o
token assim:

```powershell
$env:OCR_SERVICE_TOKEN = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Minimum 0 -Maximum 256) })
docker compose -f docker-compose.ocr.yml up -d --build
uv run cli.py
```

O caminho de OCR do CLI (`app/ocr_client.py`) escolhe um backend
automaticamente, nesta ordem:

1. **O container `ocr`**, se ele responder a uma checagem de saúde em
   `OCR_SERVICE_URL` (padrão `http://localhost:9000`, mesma porta acima).
2. **Uma instalação local do Tesseract**, se o container não estiver
   alcançável.
3. Caso contrário, imprime um erro claro e para — nunca quebra com um
   traceback bruto.

Essa escolha é feita uma vez por execução do CLI e reaproveitada para
todo screenshot, sem overhead por screenshot. O `OCR_SERVICE_TOKEN` deve
ser o mesmo entre esse container e o que seu shell tiver exportado ao
rodar o CLI — mesma regra da stack completa acima.

## Configuração

As configurações do `config.toml` (`game_directory`, `plugins_txt_path`,
`log_language`, os perks) só são usadas pelo CLI — a API não lê nada disso,
então elas não têm efeito nenhum sobre `docker compose up`. Ordem de
resolução: init > `config.toml` > padrão.

| Chave em `config.toml` | Padrão | Descrição |
| :--- | :--- | :--- |
| `game_directory` | detectado automaticamente via Steam | Caminho da instalação do Skyrim (onde os screenshots são salvos) |
| `plugins_txt_path` | detectado automaticamente | Caminho explícito da lista de plugins ativos (o `plugins.txt` de um perfil do MO2, ou o `Plugins.txt` nativo) |
| `log_language` | `en` | Idioma do log no console: `en`, `pt`, ou `de` |
| `perk_physician` | `false` | +25% de magnitude em Restaurar Vida/Magicka/Vigor |
| `perk_benefactor` | `false` | +25% em efeitos benéficos, em poções dominadas por um efeito benéfico |
| `perk_poisoner` | `false` | +25% em efeitos nocivos, em poções dominadas por um efeito nocivo (venenos) |
| `perk_purity` | `false` | Zera os efeitos de polaridade oposta em uma poção mista |

`game_directory` é detectado automaticamente lendo o `libraryfolders.vdf` do cliente Steam (cobre bibliotecas extras em outros discos), no Windows, Linux e macOS. Defina-o explicitamente em `config.toml` se você não usa Steam, ou se a detecção automática escolher a instalação errada.

`plugins_txt_path` é detectado automaticamente testando todo perfil do Mod Organizer 2 sob o prefixo Proton compatdata deste jogo em qualquer biblioteca Steam, depois o local nativo (sem MO2) do `Plugins.txt` pro sistema operacional atual. Defina-o explicitamente se você roda múltiplas instâncias/perfis do MO2 e a detecção automática escolher o errado.

A perícia de Alquimia, o perk Alchemist, equipamentos com Fortify Alchemy, e Seeker of Shadows **não são modelados** — eles escalam todo efeito uniformemente, então não mudam qual receita é favorecida, apenas os números absolutos de ouro.

## Cache

Tudo que é lido dos plugins ou processado por OCR fica em cache sob `cache/`, então execuções repetidas nunca refazem um scan de plugin ou OCR:

```
cache/
├── game_data/     Banco de ingredientes/efeitos lido dos seus plugins ativos (veja docs/data-sources/DATA_SOURCES.pt.md)
├── screenshots/   Um arquivo JSON por resultado de OCR de screenshot (<id>.json)
└── inventory/     marker.json - controle do último intervalo de screenshots combinado
```

Rode o CLI com `--refresh` (`-r`) para forçar um novo scan de plugins depois de instalar/remover/reordenar mods — `cache/game_data/` não é tocado de outra forma. Apague `cache/screenshots/<id>.json` (ou rode com `--refresh`) para forçar um novo OCR de um screenshot específico.

## Desenvolvimento

```bash
make lint          # ruff + pyright (modo strict)
```

As docstrings seguem o estilo NumPy; a checagem de tipos roda em modo `strict` do pyright, sem nenhuma supressão inline (veja `typings/pytesseract/` para o stub local da única dependência sem tipos).
