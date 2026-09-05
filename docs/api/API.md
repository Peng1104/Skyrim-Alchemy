# HTTP API reference

This document describes every HTTP endpoint exposed by the project: the
public app service, and the internal-only OCR service. Interactive
Swagger UI is also available at each service's `/docs` path while it is
running.

```
Client --HTTP--> app (published port) --internal network--> ocr (no published port)
```

The OCR service has no port published to the host. It is reachable only
from the app service over the internal network, and additionally
requires a shared-secret header, described in section 2.3. Nothing
outside that internal network can call it directly.

The app service builds its optimizer, and loads the ingredient and
effect database, once at process startup. It never scans plugin or
archive files itself. If the game-data cache has not been populated yet,
the app service fails to start at all, with a clear error, rather than
serving requests against an empty database. See the
[data sources](../data-sources/DATA_SOURCES.md) document's section 3.

## 1. App service (public)

### 1.1 GET /health

Liveness and readiness check.

Request: no parameters.

Response `200 OK`

```json
{ "status": "ok" }
```

### 1.2 POST /optimize/screenshots

The main endpoint. It runs OCR on one or more uploaded inventory
screenshots and returns the optimal potion fabrication sequence for the
resulting ingredients.

OCR itself never runs in this process. Each uploaded file is validated
here, by magic bytes, size, and count, then its raw bytes are forwarded
to the isolated OCR service, section 2.2, over the internal network.
Perks are taken strictly from the request body, never from any shared
configuration, so concurrent requests with different perk selections
never interfere with each other.

Request: `multipart/form-data`

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `files` | file array | Yes | none | One or more PNG screenshots. When an inventory spans multiple scrolled screenshots, a later file's reading for a given ingredient name overwrites an earlier one: each screenshot shows the ingredient's current total, not a delta. |
| `perk_physician` | boolean form field | No | `false` | Physician perk active. |
| `perk_benefactor` | boolean form field | No | `false` | Benefactor perk active. |
| `perk_poisoner` | boolean form field | No | `false` | Poisoner perk active. |
| `perk_purity` | boolean form field | No | `false` | Purity perk active. |

Upload constraints, enforced in order before anything is sent to the OCR
service:

| Check | Limit | Failure |
| :--- | :--- | :--- |
| File count | 20 or fewer | `400`, reason `too_many_files` |
| Magic bytes | Must be PNG | `400`, reason `invalid_type` |
| File size | 15 MiB or less per file | `413`, reason `too_large` |

Validation stops at the first failing file in the batch. The whole
request is rejected, none of the files are processed.

Response `200 OK`

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
| `fabrication_sequence` | array | Potions to fabricate, in order. |
| `fabrication_sequence[].order` | integer | 1-based position in the fabrication sequence. |
| `fabrication_sequence[].count` | integer | How many potions of this recipe to make. |
| `fabrication_sequence[].ingredients` | string array | Ingredient names used per potion of this recipe. |
| `fabrication_sequence[].effects` | string array | Shared effects this recipe produces. |
| `fabrication_sequence[].value` | number | Gold value of one potion of this recipe. |
| `remaining_ingredients` | object | Ingredient name mapped to quantity left over after fabrication. |

See the [calculation](../calculation/CALCULATION.md) document for
exactly how value and the chosen recipes are derived.

Error responses:

| Status | Body | Cause |
| :--- | :--- | :--- |
| `400` | `{"detail": "No files uploaded."}` | The `files` field was empty. |
| `400` | `{"detail": {"filename": "...", "reason": "too_many_files or invalid_type"}}` | Upload batch failed validation, section 1.2 table. |
| `413` | `{"detail": {"filename": "...", "reason": "too_large"}}` | A file exceeded 15 MiB. |
| `502` | `{"detail": "<message from the ocr service>"}` | The internal OCR service call failed: unreachable, timed out, or returned an error itself. |

## 2. OCR service (internal only)

Not reachable from outside the internal network, since no host port is
published for it. Documented here because the app service's screenshot
endpoint depends on it, and because it independently validates its own
input as defense in depth: it must not assume its only caller is the
trusted app service.

### 2.1 GET /health

Liveness and readiness check, used by the container healthcheck.
Deliberately unauthenticated, since the healthcheck itself has no easy
way to supply the internal auth token.

Request: no parameters.

Response `200 OK`

```json
{ "status": "ok" }
```

### 2.2 POST /ocr

Decodes an uploaded PNG and returns the OCR engine's structured output.

Request: `multipart/form-data`

| Field | Location | Required | Description |
| :--- | :--- | :--- | :--- |
| `image` | form field (file) | Yes | The screenshot to OCR, PNG only. |
| `X-Internal-Auth` | header | Yes | Shared secret, see section 2.3. |

Response `200 OK`, one array per column, all arrays the same length, one
entry per detected text box:

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
| `level` | integer array | Hierarchy level: 1 is page, 5 is word. |
| `page_num`, `block_num`, `par_num`, `line_num`, `word_num` | integer arrays | Position of each detected element within the page, block, paragraph, line, and word hierarchy. |
| `left`, `top`, `width`, `height` | integer arrays | Bounding box of the detected element, in pixels. |
| `conf` | number array | Detection confidence, `-1` for non-word levels. |
| `text` | string array | Recognized text, empty for non-word levels. |

This output is what the inventory reader consumes to reconstruct
ingredient names and quantities. See the
[calculation](../calculation/CALCULATION.md) document for how OCR output
becomes an ingredient inventory.

Error responses:

| Status | Body | Cause |
| :--- | :--- | :--- |
| `401` | `{"detail": "Invalid or missing internal auth token."}` | Missing or incorrect internal auth header. |
| `413` | `{"detail": "Image exceeds maximum allowed size."}` | Image over 15 MiB, kept in sync with the app service's own limit. |
| `400` | `{"detail": "Only PNG images are accepted."}` | The first 8 bytes are not the PNG magic number. |
| `400` | `{"detail": "Could not decode image."}` | The PNG magic number is present but the file could not be decoded, for example a truncated or corrupt image. |

### 2.3 Internal authentication

Every call to `/ocr` must carry an internal auth header matching a
shared secret value, compared in constant time to avoid timing attacks.
The app service reads the same secret and attaches the header
automatically, so this token never needs to be supplied by an end user
of the public API. The health check, section 2.1, is exempt.

## 3. Command-line examples

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
```

Port 8001 assumes the default deployment mapping for the app service.
Adjust to your actual deployment.
