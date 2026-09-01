# Referência da API HTTP

Este documento descreve todos os endpoints HTTP expostos pelo projeto: o
serviço público **app** (`app/api.py`, `FastAPI(title="Skyrim Alchemy
Optimizer")`) e o serviço interno **ocr** (`ocr_service/main.py`,
`FastAPI(title="Skyrim OCR Service")`). Também há uma Swagger UI interativa
em `/docs` de cada serviço enquanto ele estiver rodando.

```
Cliente ──HTTP──▶ app (porta publicada) ──rede Docker interna──▶ ocr (sem porta publicada)
```

O serviço `ocr` não tem porta publicada no host em `docker-compose.yml` —
só é alcançável a partir do `app` pela rede interna, e ainda exige um
cabeçalho de segredo compartilhado (ver [2.3](#23-autenticacao-interna)).
Nada fora da rede do Compose consegue chamá-lo diretamente.

## 1. Serviço `app` (público)

### 1.1 `GET /health`

Checagem de liveness/readiness.

**Requisição**: sem parâmetros.

**Resposta** `200 OK`

```json
{ "status": "ok" }
```

### 1.2 `DELETE /cache/pages`

Apaga todas as páginas HTML da UESP em cache dentro de `cache/pages/` e
descarta a instância em memória do `AlchemyOptimizer`
(`get_optimizer.cache_clear()`). A próxima chamada a
`/optimize/screenshots` raspa novamente ingredientes, efeitos e dados de
prioridade por efeito do zero — ver
[docs/data-sources/DATA_SOURCES.pt.md §3](../data-sources/DATA_SOURCES.pt.md#3-caching).

**Requisição**: sem parâmetros.

**Resposta** `200 OK`

```json
{ "deleted": 3 }
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `deleted` | `int` | Número de arquivos HTML em cache removidos. |

### 1.3 `POST /optimize/screenshots`

O endpoint principal: faz OCR de um ou mais screenshots de inventário
enviados e retorna a sequência ótima de fabricação de poções para os
ingredientes resultantes.

O Tesseract nunca roda neste processo — cada arquivo enviado é validado
aqui (magic bytes, tamanho, quantidade) e depois seus bytes brutos são
encaminhados para o serviço isolado `ocr` (§2.2) pela rede Docker interna.
As perks vêm estritamente do corpo da requisição, nunca de configurações
globais/CLI, então requisições concorrentes com perks diferentes nunca
interferem entre si.

**Requisição**: `multipart/form-data`

| Campo | Tipo | Obrigatório | Padrão | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `files` | `file[]` | Sim | — | Um ou mais screenshots PNG. Quando um inventário se estende por vários screenshots com scroll, a leitura de um arquivo posterior para um ingrediente sobrescreve a de um anterior — cada screenshot mostra o total *atual* do ingrediente, não um delta (reflete a regra de merge de `Inventory.retrieve`). |
| `perk_physician` | `bool` (campo de form) | Não | `false` | Perk Physician ativa. |
| `perk_benefactor` | `bool` (campo de form) | Não | `false` | Perk Benefactor ativa. |
| `perk_poisoner` | `bool` (campo de form) | Não | `false` | Perk Poisoner ativa. |
| `perk_purity` | `bool` (campo de form) | Não | `false` | Perk Purity ativa. |

Restrições de upload, aplicadas nesta ordem por
`app/upload_validation.py` (`validate_upload_batch`) antes de qualquer
envio ao `ocr`:

| Checagem | Limite | Falha |
| :--- | :--- | :--- |
| Quantidade de arquivos | ≤ 20 (`MAX_FILE_COUNT`) | `400`, `reason: "too_many_files"` |
| Magic bytes | Deve ser PNG (`\x89PNG\r\n\x1a\n`) | `400`, `reason: "invalid_type"` |
| Tamanho do arquivo | ≤ 15 MiB por arquivo (`MAX_FILE_SIZE_BYTES`) | `413`, `reason: "too_large"` |

A validação para no primeiro arquivo que falhar no lote — a requisição
inteira é rejeitada, nenhum arquivo é processado.

**Resposta** `200 OK` — `OptimizationResult`

```json
{
  "fabrication_sequence": [
    {
      "order": 1,
      "count": 3,
      "ingredients": ["Blue Mountain Flower", "Wheat"],
      "effects": ["Restore Health"],
      "value": 12.5
    }
  ],
  "remaining_ingredients": {
    "Blue Mountain Flower": 0,
    "Wheat": 1
  }
}
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `fabrication_sequence` | `RecipeDetails[]` | Poções a fabricar, em ordem. |
| `fabrication_sequence[].order` | `int` | Posição (base 1) na sequência de fabricação. |
| `fabrication_sequence[].count` | `int` | Quantas poções dessa receita fazer. |
| `fabrication_sequence[].ingredients` | `string[]` | Nomes dos ingredientes usados em cada poção dessa receita. |
| `fabrication_sequence[].effects` | `string[]` | Efeito(s) compartilhado(s) produzido(s) por essa receita. |
| `fabrication_sequence[].value` | `float` | Valor em ouro de uma poção dessa receita. |
| `remaining_ingredients` | `object<string, int>` | Nome do ingrediente → quantidade restante após a fabricação. |

Veja [docs/calculation/CALCULATION.pt.md](../calculation/CALCULATION.pt.md)
para saber exatamente como `value` e as receitas escolhidas são derivados.

**Respostas de erro**

| Status | Corpo | Causa |
| :--- | :--- | :--- |
| `400` | `{"detail": "No files uploaded."}` | `files` veio vazio. |
| `400` | `{"detail": {"filename": "...", "reason": "too_many_files" \| "invalid_type"}}` | O lote de upload falhou na validação (tabela da §1.3). |
| `413` | `{"detail": {"filename": "...", "reason": "too_large"}}` | Um arquivo excedeu 15 MiB. |
| `502` | `{"detail": "<mensagem do serviço ocr>"}` | A chamada ao serviço interno `ocr` falhou (`OcrServiceError`) — ex: inacessível, timeout, ou ele mesmo retornou erro. |

## 2. Serviço `ocr` (somente interno)

Não é alcançável de fora da rede do Docker Compose — não há porta
publicada no host para ele. Documentado aqui porque
`/optimize/screenshots` do `app` depende dele, e porque ele valida seu
próprio input de forma independente como defesa em profundidade (não pode
assumir que seu único chamador é o container `app` confiável).

### 2.1 `GET /health`

Checagem de liveness/readiness, usada pelo `HEALTHCHECK` do Docker.
Propositalmente sem autenticação — o comando de healthcheck não tem uma
forma fácil de fornecer o token de autenticação interno.

**Requisição**: sem parâmetros.

**Resposta** `200 OK`

```json
{ "status": "ok" }
```

### 2.2 `POST /ocr`

Decodifica um PNG enviado e retorna a saída estruturada do Tesseract
(`pytesseract.image_to_data(..., output_type=Output.DICT)`).

**Requisição**: `multipart/form-data`

| Campo | Local | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `image` | campo de form (arquivo) | Sim | O screenshot para fazer OCR (somente PNG). |
| `X-Internal-Auth` | cabeçalho | Sim | Segredo compartilhado; ver §2.3. |

**Resposta** `200 OK` — dict bruto de `image_to_data` do Tesseract, um
array por coluna, todos os arrays com o mesmo tamanho (uma entrada por
caixa de texto detectada):

```json
{
  "level": [1, 2, 3, 4, 5],
  "page_num": [1, 1, 1, 1, 1],
  "block_num": [0, 1, 1, 1, 1],
  "par_num": [0, 0, 1, 1, 1],
  "line_num": [0, 0, 0, 1, 1],
  "word_num": [0, 0, 0, 0, 1],
  "left": [0, 34, 34, 34, 34],
  "top": [0, 19, 19, 19, 19],
  "width": [1920, 400, 400, 400, 120],
  "height": [1080, 30, 30, 30, 22],
  "conf": [-1, -1, -1, -1, 96.4],
  "text": ["", "", "", "", "Wheat"]
}
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `level` | `int[]` | Nível hierárquico do Tesseract (1 = página … 5 = palavra). |
| `page_num` / `block_num` / `par_num` / `line_num` / `word_num` | `int[]` | Posição de cada elemento detectado na hierarquia página/bloco/parágrafo/linha/palavra do Tesseract. |
| `left` / `top` / `width` / `height` | `int[]` | Caixa delimitadora do elemento detectado, em pixels. |
| `conf` | `float[]` | Confiança da detecção (`-1` para níveis que não são palavra). |
| `text` | `string[]` | Texto reconhecido (vazio para níveis que não são palavra). |

`app/inventory/_ocr.py` / `app/ocr_client.py` consomem esse formato para
reconstruir nomes e quantidades de ingredientes; veja
[docs/calculation/CALCULATION.pt.md](../calculation/CALCULATION.pt.md)
para saber como a saída do OCR vira `InventoryIngredient`s.

**Respostas de erro**

| Status | Corpo | Causa |
| :--- | :--- | :--- |
| `401` | `{"detail": "Invalid or missing internal auth token."}` | Cabeçalho `X-Internal-Auth` ausente/incorreto. |
| `413` | `{"detail": "Image exceeds maximum allowed size."}` | Imagem acima de 15 MiB (mantido sincronizado com o limite do próprio `app`). |
| `400` | `{"detail": "Only PNG images are accepted."}` | Os primeiros 8 bytes não são o magic number do PNG. |
| `400` | `{"detail": "Could not decode image."}` | Magic number do PNG presente, mas o Pillow não conseguiu decodificar o arquivo (`UnidentifiedImageError`), ex: imagem truncada/corrompida. |

### 2.3 Autenticação interna

Toda chamada a `/ocr` deve trazer um cabeçalho `X-Internal-Auth` que bata
com a variável de ambiente `OCR_SERVICE_TOKEN`, comparado em tempo
constante (`hmac.compare_digest`) para evitar ataques de timing. O `app`
lê o mesmo valor de `OCR_SERVICE_TOKEN` e anexa o cabeçalho
automaticamente (`app/ocr_client.py`) — esse token nunca precisa ser
fornecido por um usuário final da API pública. `/health` é isento (§2.1).

## 3. Exemplos com cURL

```bash
# Checagem de saúde
curl http://localhost:8001/health

# Otimizar um único screenshot, sem perks
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png"

# Otimizar múltiplos screenshots com perks ativas
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png" \
  -F "files=@ScreenShot1.png" \
  -F "perk_physician=true" \
  -F "perk_benefactor=true"

# Limpar o cache de scraping da UESP
curl -X DELETE http://localhost:8001/cache/pages
```

(A porta `8001` assume o mapeamento padrão do `docker-compose.yml`/`run.py`
para o `app` — ajuste conforme o seu deployment real.)
