# HTTP API reference

This document describes every HTTP endpoint exposed by the project: the
public **app** service (`app/api.py`, `FastAPI(title="Skyrim Alchemy
Optimizer")`) and the internal-only **ocr** service (`ocr_service/main.py`,
`FastAPI(title="Skyrim OCR Service")`). Interactive Swagger UI is also
available at each service's `/docs` while it's running.

```
Client ──HTTP──▶ app (published port) ──internal Docker network──▶ ocr (no published port)
```

The `ocr` service has no host-published port in `docker-compose.yml` — it is
reachable only from `app` over the internal network, and additionally
requires a shared-secret header (see [2.3](#23-internal-authentication)).
Nothing outside the Compose network can call it directly.

## 1. `app` service (public)

### 1.1 `GET /health`

Liveness/readiness check.

**Request**: no parameters.

**Response** `200 OK`

```json
{ "status": "ok" }
```

### 1.2 `DELETE /cache/pages`

Deletes every cached UESP HTML page under `cache/pages/` and drops the
in-memory `AlchemyOptimizer` instance (`get_optimizer.cache_clear()`). The
next `/optimize/screenshots` call re-scrapes ingredients, effects, and
per-effect priority data from scratch — see
[docs/data-sources/DATA_SOURCES.en.md §3](../data-sources/DATA_SOURCES.en.md#3-caching).

**Request**: no parameters.

**Response** `200 OK`

```json
{ "deleted": 3 }
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `deleted` | `int` | Number of cached HTML files removed. |

### 1.3 `POST /optimize/screenshots`

The main endpoint: OCRs one or more uploaded inventory screenshots and
returns the optimal potion fabrication sequence for the resulting
ingredients.

Tesseract never runs in this process — each uploaded file is validated here
(magic bytes, size, count), then its raw bytes are forwarded to the isolated
`ocr` service (§2.2) over the internal Docker network. Perks are taken
strictly from the request body, never from global/CLI settings, so
concurrent requests with different perk selections never interfere with
each other.

**Request**: `multipart/form-data`

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `files` | `file[]` | Yes | — | One or more PNG screenshots. When an inventory spans multiple scrolled screenshots, a later file's reading for a given ingredient name overwrites an earlier one — each screenshot shows the ingredient's *current total*, not a delta (mirrors `Inventory.retrieve`'s merge rule). |
| `perk_physician` | `bool` (form field) | No | `false` | Physician perk active. |
| `perk_benefactor` | `bool` (form field) | No | `false` | Benefactor perk active. |
| `perk_poisoner` | `bool` (form field) | No | `false` | Poisoner perk active. |
| `perk_purity` | `bool` (form field) | No | `false` | Purity perk active. |

Upload constraints, enforced in order by `app/upload_validation.py`
(`validate_upload_batch`) before anything is sent to `ocr`:

| Check | Limit | Failure |
| :--- | :--- | :--- |
| File count | ≤ 20 (`MAX_FILE_COUNT`) | `400`, `reason: "too_many_files"` |
| Magic bytes | Must be PNG (`\x89PNG\r\n\x1a\n`) | `400`, `reason: "invalid_type"` |
| File size | ≤ 15 MiB per file (`MAX_FILE_SIZE_BYTES`) | `413`, `reason: "too_large"` |

Validation stops at the first failing file in the batch — the whole request
is rejected, none of the files are processed.

**Response** `200 OK` — `OptimizationResult`

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

| Field | Type | Description |
| :--- | :--- | :--- |
| `fabrication_sequence` | `RecipeDetails[]` | Potions to fabricate, in order. |
| `fabrication_sequence[].order` | `int` | 1-based position in the fabrication sequence. |
| `fabrication_sequence[].count` | `int` | How many potions of this recipe to make. |
| `fabrication_sequence[].ingredients` | `string[]` | Ingredient names used per potion of this recipe. |
| `fabrication_sequence[].effects` | `string[]` | Shared effect(s) this recipe produces. |
| `fabrication_sequence[].value` | `float` | Gold value of one potion of this recipe. |
| `remaining_ingredients` | `object<string, int>` | Ingredient name → quantity left over after fabrication. |

See [docs/calculation/CALCULATION.en.md](../calculation/CALCULATION.en.md)
for exactly how `value` and the chosen recipes are derived.

**Error responses**

| Status | Body | Cause |
| :--- | :--- | :--- |
| `400` | `{"detail": "No files uploaded."}` | `files` was empty. |
| `400` | `{"detail": {"filename": "...", "reason": "too_many_files" \| "invalid_type"}}` | Upload batch failed validation (§1.3 table). |
| `413` | `{"detail": {"filename": "...", "reason": "too_large"}}` | A file exceeded 15 MiB. |
| `502` | `{"detail": "<message from the ocr service>"}` | The internal `ocr` service call failed (`OcrServiceError`) — e.g. unreachable, timed out, or itself returned an error. |

## 2. `ocr` service (internal only)

Not reachable from outside the Docker Compose network — no host port is
published for it. Documented here because `app`'s `/optimize/screenshots`
depends on it, and because it independently validates its own input as
defense in depth (it must not assume its only caller is the trusted `app`
container).

### 2.1 `GET /health`

Liveness/readiness check, used by the Docker `HEALTHCHECK`. Deliberately
unauthenticated — the healthcheck command has no easy way to supply the
internal auth token.

**Request**: no parameters.

**Response** `200 OK`

```json
{ "status": "ok" }
```

### 2.2 `POST /ocr`

Decodes an uploaded PNG and returns Tesseract's structured OCR output
(`pytesseract.image_to_data(..., output_type=Output.DICT)`).

**Request**: `multipart/form-data`

| Field | Location | Required | Description |
| :--- | :--- | :--- | :--- |
| `image` | form field (file) | Yes | The screenshot to OCR (PNG only). |
| `X-Internal-Auth` | header | Yes | Shared secret; see §2.3. |

**Response** `200 OK` — Tesseract's raw `image_to_data` dict, one array per
column, all arrays the same length (one entry per detected text box):

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

| Field | Type | Description |
| :--- | :--- | :--- |
| `level` | `int[]` | Tesseract hierarchy level (1 = page … 5 = word). |
| `page_num` / `block_num` / `par_num` / `line_num` / `word_num` | `int[]` | Position of each detected element within Tesseract's page/block/paragraph/line/word hierarchy. |
| `left` / `top` / `width` / `height` | `int[]` | Bounding box of the detected element, in pixels. |
| `conf` | `float[]` | Detection confidence (`-1` for non-word levels). |
| `text` | `string[]` | Recognized text (empty for non-word levels). |

`app/inventory/_ocr.py` / `app/ocr_client.py` consume this shape to
reconstruct ingredient names and quantities; see
[docs/calculation/CALCULATION.en.md](../calculation/CALCULATION.en.md) for
how OCR output is turned into `InventoryIngredient`s.

**Error responses**

| Status | Body | Cause |
| :--- | :--- | :--- |
| `401` | `{"detail": "Invalid or missing internal auth token."}` | Missing/incorrect `X-Internal-Auth` header. |
| `413` | `{"detail": "Image exceeds maximum allowed size."}` | Image over 15 MiB (kept in sync with `app`'s own limit). |
| `400` | `{"detail": "Only PNG images are accepted."}` | First 8 bytes aren't the PNG magic number. |
| `400` | `{"detail": "Could not decode image."}` | PNG magic number present but Pillow couldn't decode the file (`UnidentifiedImageError`), e.g. a truncated/corrupt image. |

### 2.3 Internal authentication

Every `/ocr` call must carry an `X-Internal-Auth` header matching the
`OCR_SERVICE_TOKEN` environment variable, compared in constant time
(`hmac.compare_digest`) to avoid timing attacks. `app` reads the same
`OCR_SERVICE_TOKEN` value and attaches the header automatically
(`app/ocr_client.py`) — this token never needs to be supplied by an
end user of the public API. `/health` is exempt (§2.1).

## 3. cURL examples

```bash
# Health check
curl http://localhost:8001/health

# Optimize a single screenshot, no perks
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png"

# Optimize multiple screenshots with perks active
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png" \
  -F "files=@ScreenShot1.png" \
  -F "perk_physician=true" \
  -F "perk_benefactor=true"

# Clear the UESP scraping cache
curl -X DELETE http://localhost:8001/cache/pages
```

(Port `8001` assumes the default `docker-compose.yml`/`run.py` mapping for
`app` — adjust to your actual deployment.)
