# HTTP-API-Referenz

Dieses Dokument beschreibt jeden HTTP-Endpunkt des Projekts: den
öffentlichen **app**-Service (`app/api.py`, `FastAPI(title="Skyrim Alchemy
Optimizer")`) und den rein internen **ocr**-Service (`ocr_service/main.py`,
`FastAPI(title="Skyrim OCR Service")`). Eine interaktive Swagger-UI ist
außerdem unter `/docs` jedes Services verfügbar, solange er läuft.

```
Client ──HTTP──▶ app (veröffentlichter Port) ──internes Docker-Netzwerk──▶ ocr (kein veröffentlichter Port)
```

Der `ocr`-Service hat in `docker-compose.yml` keinen auf dem Host
veröffentlichten Port — er ist nur vom `app`-Service über das interne
Netzwerk erreichbar und verlangt zusätzlich einen Shared-Secret-Header
(siehe [2.3](#23-interne-authentifizierung)). Nichts außerhalb des
Compose-Netzwerks kann ihn direkt aufrufen.

## 1. `app`-Service (öffentlich)

### 1.1 `GET /health`

Liveness-/Readiness-Check.

**Anfrage**: keine Parameter.

**Antwort** `200 OK`

```json
{ "status": "ok" }
```

### 1.2 `DELETE /cache/pages`

Löscht jede zwischengespeicherte UESP-HTML-Seite unter `cache/pages/` und
verwirft die im Speicher gehaltene `AlchemyOptimizer`-Instanz
(`get_optimizer.cache_clear()`). Der nächste Aufruf von
`/optimize/screenshots` scrapt Zutaten-, Effekt- und
Effekt-Prioritätsdaten wieder von Grund auf — siehe
[docs/data-sources/DATA_SOURCES.de.md §3](../data-sources/DATA_SOURCES.de.md#3-caching).

**Anfrage**: keine Parameter.

**Antwort** `200 OK`

```json
{ "deleted": 3 }
```

| Feld | Typ | Beschreibung |
| :--- | :--- | :--- |
| `deleted` | `int` | Anzahl der gelöschten zwischengespeicherten HTML-Dateien. |

### 1.3 `POST /optimize/screenshots`

Der Haupt-Endpunkt: führt OCR auf einem oder mehreren hochgeladenen
Inventar-Screenshots aus und liefert die optimale
Tränke-Fabrikationsreihenfolge für die resultierenden Zutaten.

Tesseract läuft nie in diesem Prozess — jede hochgeladene Datei wird hier
validiert (Magic Bytes, Größe, Anzahl), dann werden ihre Rohbytes an den
isolierten `ocr`-Service (§2.2) über das interne Docker-Netzwerk
weitergeleitet. Perks werden ausschließlich aus dem Request-Body gelesen,
nie aus globalen/CLI-Einstellungen — dadurch beeinflussen sich
gleichzeitige Anfragen mit unterschiedlichen Perk-Auswahlen nie
gegenseitig.

**Anfrage**: `multipart/form-data`

| Feld | Typ | Erforderlich | Standard | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `files` | `file[]` | Ja | — | Ein oder mehrere PNG-Screenshots. Erstreckt sich ein Inventar über mehrere gescrollte Screenshots, überschreibt der Wert einer späteren Datei für einen gegebenen Zutatennamen den einer früheren — jeder Screenshot zeigt die *aktuelle Gesamtmenge* der Zutat, kein Delta (entspricht der Merge-Regel von `Inventory.retrieve`). |
| `perk_physician` | `bool` (Formularfeld) | Nein | `false` | Perk Physician aktiv. |
| `perk_benefactor` | `bool` (Formularfeld) | Nein | `false` | Perk Benefactor aktiv. |
| `perk_poisoner` | `bool` (Formularfeld) | Nein | `false` | Perk Poisoner aktiv. |
| `perk_purity` | `bool` (Formularfeld) | Nein | `false` | Perk Purity aktiv. |

Upload-Beschränkungen, in dieser Reihenfolge durchgesetzt von
`app/upload_validation.py` (`validate_upload_batch`), bevor überhaupt
etwas an `ocr` gesendet wird:

| Prüfung | Grenze | Fehler |
| :--- | :--- | :--- |
| Dateianzahl | ≤ 20 (`MAX_FILE_COUNT`) | `400`, `reason: "too_many_files"` |
| Magic Bytes | Muss PNG sein (`\x89PNG\r\n\x1a\n`) | `400`, `reason: "invalid_type"` |
| Dateigröße | ≤ 15 MiB pro Datei (`MAX_FILE_SIZE_BYTES`) | `413`, `reason: "too_large"` |

Die Validierung stoppt bei der ersten fehlschlagenden Datei im Batch — die
gesamte Anfrage wird abgelehnt, keine der Dateien wird verarbeitet.

**Antwort** `200 OK` — `OptimizationResult`

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

| Feld | Typ | Beschreibung |
| :--- | :--- | :--- |
| `fabrication_sequence` | `RecipeDetails[]` | Herzustellende Tränke, in Reihenfolge. |
| `fabrication_sequence[].order` | `int` | 1-basierte Position in der Fabrikationsreihenfolge. |
| `fabrication_sequence[].count` | `int` | Wie viele Tränke dieses Rezepts hergestellt werden sollen. |
| `fabrication_sequence[].ingredients` | `string[]` | Verwendete Zutatennamen pro Trank dieses Rezepts. |
| `fabrication_sequence[].effects` | `string[]` | Von diesem Rezept erzeugte(r) gemeinsame(r) Effekt(e). |
| `fabrication_sequence[].value` | `float` | Goldwert eines Trankes dieses Rezepts. |
| `remaining_ingredients` | `object<string, int>` | Zutatenname → verbleibende Menge nach der Fabrikation. |

Siehe [docs/calculation/CALCULATION.de.md](../calculation/CALCULATION.de.md)
für die genaue Herleitung von `value` und der gewählten Rezepte.

**Fehlerantworten**

| Status | Body | Ursache |
| :--- | :--- | :--- |
| `400` | `{"detail": "No files uploaded."}` | `files` war leer. |
| `400` | `{"detail": {"filename": "...", "reason": "too_many_files" \| "invalid_type"}}` | Der Upload-Batch hat die Validierung nicht bestanden (Tabelle in §1.3). |
| `413` | `{"detail": {"filename": "...", "reason": "too_large"}}` | Eine Datei überschritt 15 MiB. |
| `502` | `{"detail": "<Nachricht vom ocr-Service>"}` | Der interne `ocr`-Aufruf ist fehlgeschlagen (`OcrServiceError`) — z. B. nicht erreichbar, Timeout, oder er selbst hat einen Fehler zurückgegeben. |

## 2. `ocr`-Service (nur intern)

Von außerhalb des Docker-Compose-Netzwerks nicht erreichbar — es gibt
keinen auf dem Host veröffentlichten Port dafür. Hier dokumentiert, weil
`/optimize/screenshots` des `app`-Services davon abhängt, und weil er
seine eigenen Eingaben unabhängig validiert, als Verteidigung in der
Tiefe (er darf nicht annehmen, dass sein einziger Aufrufer der
vertrauenswürdige `app`-Container ist).

### 2.1 `GET /health`

Liveness-/Readiness-Check, verwendet vom Docker-`HEALTHCHECK`. Absichtlich
ohne Authentifizierung — der Healthcheck-Befehl hat keine einfache
Möglichkeit, das interne Auth-Token bereitzustellen.

**Anfrage**: keine Parameter.

**Antwort** `200 OK`

```json
{ "status": "ok" }
```

### 2.2 `POST /ocr`

Dekodiert ein hochgeladenes PNG und liefert Tesseracts strukturierte
OCR-Ausgabe (`pytesseract.image_to_data(..., output_type=Output.DICT)`).

**Anfrage**: `multipart/form-data`

| Feld | Ort | Erforderlich | Beschreibung |
| :--- | :--- | :--- | :--- |
| `image` | Formularfeld (Datei) | Ja | Der zu OCR-ende Screenshot (nur PNG). |
| `X-Internal-Auth` | Header | Ja | Shared Secret; siehe §2.3. |

**Antwort** `200 OK` — Tesseracts rohes `image_to_data`-Dict, ein Array
pro Spalte, alle Arrays gleich lang (ein Eintrag pro erkannter
Textbox):

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

| Feld | Typ | Beschreibung |
| :--- | :--- | :--- |
| `level` | `int[]` | Tesseract-Hierarchieebene (1 = Seite … 5 = Wort). |
| `page_num` / `block_num` / `par_num` / `line_num` / `word_num` | `int[]` | Position jedes erkannten Elements in Tesseracts Seite/Block/Absatz/Zeile/Wort-Hierarchie. |
| `left` / `top` / `width` / `height` | `int[]` | Begrenzungsrahmen des erkannten Elements, in Pixeln. |
| `conf` | `float[]` | Erkennungssicherheit (`-1` für Nicht-Wort-Ebenen). |
| `text` | `string[]` | Erkannter Text (leer bei Nicht-Wort-Ebenen). |

`app/inventory/_ocr.py` / `app/ocr_client.py` verarbeiten dieses Format,
um Zutatennamen und -mengen zu rekonstruieren; siehe
[docs/calculation/CALCULATION.de.md](../calculation/CALCULATION.de.md)
dazu, wie die OCR-Ausgabe in `InventoryIngredient`s umgewandelt wird.

**Fehlerantworten**

| Status | Body | Ursache |
| :--- | :--- | :--- |
| `401` | `{"detail": "Invalid or missing internal auth token."}` | Fehlender/falscher `X-Internal-Auth`-Header. |
| `413` | `{"detail": "Image exceeds maximum allowed size."}` | Bild über 15 MiB (synchron gehalten mit dem eigenen Limit von `app`). |
| `400` | `{"detail": "Only PNG images are accepted."}` | Die ersten 8 Bytes sind nicht die PNG-Magic-Number. |
| `400` | `{"detail": "Could not decode image."}` | PNG-Magic-Number vorhanden, aber Pillow konnte die Datei nicht dekodieren (`UnidentifiedImageError`), z. B. ein abgeschnittenes/beschädigtes Bild. |

### 2.3 Interne Authentifizierung

Jeder `/ocr`-Aufruf muss einen `X-Internal-Auth`-Header tragen, der mit
der Umgebungsvariable `OCR_SERVICE_TOKEN` übereinstimmt, verglichen in
konstanter Zeit (`hmac.compare_digest`), um Timing-Angriffe zu vermeiden.
`app` liest denselben `OCR_SERVICE_TOKEN`-Wert und fügt den Header
automatisch hinzu (`app/ocr_client.py`) — dieses Token muss nie von einem
Endnutzer der öffentlichen API bereitgestellt werden. `/health` ist davon
ausgenommen (§2.1).

## 3. cURL-Beispiele

```bash
# Health-Check
curl http://localhost:8001/health

# Einen einzelnen Screenshot ohne Perks optimieren
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png"

# Mehrere Screenshots mit aktiven Perks optimieren
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png" \
  -F "files=@ScreenShot1.png" \
  -F "perk_physician=true" \
  -F "perk_benefactor=true"

# UESP-Scraping-Cache leeren
curl -X DELETE http://localhost:8001/cache/pages
```

(Port `8001` entspricht dem Standard-Mapping von
`docker-compose.yml`/`run.py` für `app` — an das tatsächliche Deployment
anpassen.)
