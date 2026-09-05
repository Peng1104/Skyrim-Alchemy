# HTTP-API-Referenz

Dieses Dokument beschreibt jeden vom Projekt bereitgestellten
HTTP-Endpunkt: den öffentlichen App-Dienst und den nur-internen
OCR-Dienst. Eine interaktive Swagger-UI ist außerdem unter dem eigenen
`/docs`-Pfad jedes Dienstes verfügbar, während er läuft.

```
Client --HTTP--> app (veröffentlichter Port) --internes Netzwerk--> ocr (kein veröffentlichter Port)
```

Der OCR-Dienst hat keinen zum Host veröffentlichten Port. Er ist nur
vom App-Dienst über das interne Netzwerk erreichbar, und verlangt
zusätzlich einen Shared-Secret-Header, beschrieben in Abschnitt 2.3.
Nichts außerhalb dieses internen Netzwerks kann ihn direkt aufrufen.

Der App-Dienst baut seinen Optimierer auf und lädt die Zutaten- und
Effektdatenbank einmalig beim Prozessstart. Er scannt nie selbst
Plugin- oder Archivdateien. Wenn der Spieldaten-Cache noch nicht
befüllt wurde, startet der App-Dienst gar nicht erst, mit einem klaren
Fehler, statt Anfragen gegen eine leere Datenbank zu bedienen. Siehe
Abschnitt 3 des
[Datenquellen](../data-sources/DATA_SOURCES.md)-Dokuments.

## 1. App-Dienst (öffentlich)

### 1.1 GET /health

Liveness- und Readiness-Check.

Anfrage: keine Parameter.

Antwort `200 OK`

```json
{ "status": "ok" }
```

### 1.2 POST /optimize/screenshots

Der Haupt-Endpunkt. Er führt OCR auf einem oder mehreren hochgeladenen
Inventar-Screenshots aus und gibt die optimale
Trank-Fertigungsreihenfolge für die resultierenden Zutaten zurück.

OCR selbst läuft nie in diesem Prozess. Jede hochgeladene Datei wird
hier validiert, nach Magic Bytes, Größe und Anzahl, und dann werden
ihre rohen Bytes an den isolierten OCR-Dienst weitergeleitet, Abschnitt
2.2, über das interne Netzwerk. Perks werden strikt aus dem
Anfragekörper genommen, nie aus einer geteilten Konfiguration, sodass
gleichzeitige Anfragen mit unterschiedlichen Perk-Auswahlen sich nie
gegenseitig beeinflussen.

Anfrage: `multipart/form-data`

| Feld | Typ | Erforderlich | Standard | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `files` | Datei-Array | Ja | keiner | Ein oder mehrere PNG-Screenshots. Erstreckt sich ein Inventar über mehrere gescrollte Screenshots, überschreibt der Wert einer späteren Datei für einen gegebenen Zutatennamen einen früheren: jeder Screenshot zeigt die aktuelle Gesamtmenge der Zutat, kein Delta. |
| `perk_physician` | boolesches Formularfeld | Nein | `false` | Physician-Perk aktiv. |
| `perk_benefactor` | boolesches Formularfeld | Nein | `false` | Benefactor-Perk aktiv. |
| `perk_poisoner` | boolesches Formularfeld | Nein | `false` | Poisoner-Perk aktiv. |
| `perk_purity` | boolesches Formularfeld | Nein | `false` | Purity-Perk aktiv. |

Upload-Beschränkungen, in dieser Reihenfolge durchgesetzt, bevor
irgendetwas an den OCR-Dienst gesendet wird:

| Prüfung | Grenze | Fehler |
| :--- | :--- | :--- |
| Dateianzahl | 20 oder weniger | `400`, Grund `too_many_files` |
| Magic Bytes | Muss PNG sein | `400`, Grund `invalid_type` |
| Dateigröße | 15 MiB oder weniger pro Datei | `413`, Grund `too_large` |

Die Validierung stoppt bei der ersten fehlschlagenden Datei im Batch.
Die gesamte Anfrage wird abgelehnt, keine der Dateien wird verarbeitet.

Antwort `200 OK`

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
| `fabrication_sequence` | Array | Herzustellende Tränke, in Reihenfolge. |
| `fabrication_sequence[].order` | Ganzzahl | 1-basierte Position in der Fertigungsreihenfolge. |
| `fabrication_sequence[].count` | Ganzzahl | Wie viele Tränke dieses Rezepts herzustellen sind. |
| `fabrication_sequence[].ingredients` | String-Array | Verwendete Zutatennamen pro Trank dieses Rezepts. |
| `fabrication_sequence[].effects` | String-Array | Von diesem Rezept erzeugte, geteilte Effekte. |
| `fabrication_sequence[].value` | Zahl | Goldwert eines Tranks dieses Rezepts. |
| `remaining_ingredients` | Objekt | Zutatenname, abgebildet auf die nach der Fertigung übrige Menge. |

Siehe das [Berechnungs](../calculation/CALCULATION.md)-Dokument dafür,
wie genau `value` und die gewählten Rezepte hergeleitet werden.

Fehlerantworten:

| Status | Körper | Ursache |
| :--- | :--- | :--- |
| `400` | `{"detail": "No files uploaded."}` | Das Feld `files` war leer. |
| `400` | `{"detail": {"filename": "...", "reason": "too_many_files oder invalid_type"}}` | Upload-Batch hat die Validierung nicht bestanden, Tabelle in Abschnitt 1.2. |
| `413` | `{"detail": {"filename": "...", "reason": "too_large"}}` | Eine Datei überschritt 15 MiB. |
| `502` | `{"detail": "<Nachricht vom ocr-Dienst>"}` | Der Aufruf des internen OCR-Dienstes ist fehlgeschlagen: nicht erreichbar, Timeout, oder er hat selbst einen Fehler zurückgegeben. |

## 2. OCR-Dienst (nur intern)

Von außerhalb des internen Netzwerks nicht erreichbar, da dafür kein
Host-Port veröffentlicht ist. Hier dokumentiert, weil der
Screenshot-Endpunkt des App-Dienstes davon abhängt, und weil er seine
eigene Eingabe unabhängig als Defense in Depth validiert: er darf nicht
annehmen, dass sein einziger Aufrufer der vertrauenswürdige App-Dienst
ist.

### 2.1 GET /health

Liveness- und Readiness-Check, verwendet vom Container-Healthcheck.
Absichtlich unauthentifiziert, da der Healthcheck selbst keine
einfache Möglichkeit hat, das interne Auth-Token bereitzustellen.

Anfrage: keine Parameter.

Antwort `200 OK`

```json
{ "status": "ok" }
```

### 2.2 POST /ocr

Dekodiert ein hochgeladenes PNG und gibt die strukturierte Ausgabe der
OCR-Engine zurück.

Anfrage: `multipart/form-data`

| Feld | Ort | Erforderlich | Beschreibung |
| :--- | :--- | :--- | :--- |
| `image` | Formularfeld (Datei) | Ja | Der Screenshot für OCR, nur PNG. |
| `X-Internal-Auth` | Header | Ja | Shared Secret, siehe Abschnitt 2.3. |

Antwort `200 OK`, ein Array pro Spalte, alle Arrays gleich lang, ein
Eintrag pro erkannter Textbox:

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
| `level` | Ganzzahl-Array | Hierarchieebene: 1 ist Seite, 5 ist Wort. |
| `page_num`, `block_num`, `par_num`, `line_num`, `word_num` | Ganzzahl-Arrays | Position jedes erkannten Elements innerhalb der Seiten-, Block-, Absatz-, Zeilen- und Wort-Hierarchie. |
| `left`, `top`, `width`, `height` | Ganzzahl-Arrays | Begrenzungsrahmen des erkannten Elements, in Pixeln. |
| `conf` | Zahl-Array | Erkennungskonfidenz, `-1` für Nicht-Wort-Ebenen. |
| `text` | String-Array | Erkannter Text, leer für Nicht-Wort-Ebenen. |

Diese Ausgabe ist das, was der Inventar-Leser konsumiert, um
Zutatennamen und -mengen zu rekonstruieren. Siehe das
[Berechnungs](../calculation/CALCULATION.md)-Dokument dafür, wie die
OCR-Ausgabe zu einem Zutateninventar wird.

Fehlerantworten:

| Status | Körper | Ursache |
| :--- | :--- | :--- |
| `401` | `{"detail": "Invalid or missing internal auth token."}` | Interner Auth-Header fehlt oder ist falsch. |
| `413` | `{"detail": "Image exceeds maximum allowed size."}` | Bild über 15 MiB, synchron mit der eigenen Grenze des App-Dienstes gehalten. |
| `400` | `{"detail": "Only PNG images are accepted."}` | Die ersten 8 Bytes sind nicht die PNG-Magic-Number. |
| `400` | `{"detail": "Could not decode image."}` | Die PNG-Magic-Number ist vorhanden, aber die Datei konnte nicht dekodiert werden, zum Beispiel ein abgeschnittenes oder beschädigtes Bild. |

### 2.3 Interne Authentifizierung

Jeder Aufruf von `/ocr` muss einen internen Auth-Header tragen, der
mit einem Shared-Secret-Wert übereinstimmt, in konstanter Zeit
verglichen, um Timing-Angriffe zu vermeiden. Der App-Dienst liest
dasselbe Secret und hängt den Header automatisch an, sodass dieses
Token nie von einem Endnutzer der öffentlichen API bereitgestellt
werden muss. Der Health-Check, Abschnitt 2.1, ist davon ausgenommen.

## 3. Kommandozeilen-Beispiele

```bash
# Health-Check
curl http://localhost:8001/health

# Einen einzelnen Screenshot optimieren, keine Perks
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png"

# Mehrere Screenshots mit aktiven Perks optimieren
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png" \
  -F "files=@ScreenShot1.png" \
  -F "perk_physician=true" \
  -F "perk_benefactor=true"
```

Port 8001 setzt das Standard-Deployment-Mapping für den App-Dienst
voraus. An das eigene tatsächliche Deployment anpassen.
