🌐 [English](PLUGIN_CACHE.md) · [Português](PLUGIN_CACHE.pt.md) · [Deutsch](PLUGIN_CACHE.de.md)

# Plugin-Cache

Dieses Dokument beschreibt den rohen Scan-Cache auf der Festplatte für
die eigenen Zutaten- und Magieeffektdaten eines einzelnen Plugins: eine
kleine JSON-Datei pro aktivem Plugin, unter
`cache/game_data/plugins/<Plugin-Dateiname>.json`, benannt nach dem
Plugin selbst (zum Beispiel `Skyrim.esm.json`).

Jede Datei enthält genau das, was die eigenen binären Daten eines
Plugins enthalten: seine Zutaten-
([`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR))
und Magieeffekt-Datensätze
([`MGEF`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/MGEF)),
bereits geparst und mit aufgelösten Anzeigenamen. Sie existiert rein,
um erneutes Scannen schnell zu machen. Solange sich die eigenen Bytes
eines Plugins nicht geändert haben, kann seine Datei hier
wiederverwendet werden, ohne dieses Plugin je wieder zu öffnen oder neu
zu parsen.

## 1. Struktur

```jsonc
{
  "signature": {
    "size": 249752131,
    "mtime": 1787841633.526221
  },
  "ingredients": [
    {
      "owner_file": "Skyrim.esm",
      "local_id": 1076764,
      "form_id": "00106E1C",
      "name": "Silverside Perch",
      "effect_refs": [
        {
          "effect_owner_file": "Skyrim.esm",
          "effect_local_id": 256790,
          "magnitude": 5.0,
          "duration": 0.0
        }
        // bis zu 4 Einträge, einer pro Effekt der Zutat
      ]
    }
    // ein Eintrag pro Zutat, die dieses Plugin definiert oder überschreibt
  ],
  "effects": [
    {
      "owner_file": "Skyrim.esm",
      "local_id": 95196,
      "form_id": "000173DC",
      "name": "Banish - Damage Health",
      "cost": 0.0,
      "harmful": true
    }
    // ein Eintrag pro Magieeffekt, den dieses Plugin definiert oder überschreibt
  ]
}
```

(Echter, gekürzter Auszug aus einer `Skyrim.esm.json`-Cache-Datei.)

### 1.1 Signature

Die Signature ist kein Inhalts-Hash: sie ist die Dateigröße des
Plugins in Bytes und der Zeitpunkt der letzten Änderung, festgehalten
in dem Moment, in dem diese Datei gescannt wurde. Eine einfache
Dateisystemprüfung dieser beiden Zahlen, günstig genug, um bei jedem
Scan zu laufen, ohne das Plugin selbst zu öffnen, reicht aus, um zu
sagen, ob sich das Plugin seither geändert hat. Jede echte Änderung am
Plugin, ein Mod-Update oder ein in einem Bearbeitungstool angewendeter
Patch, ändert mindestens einen der beiden Werte.

Ein Plugin, das als aktiv gelistet, aber tatsächlich nicht auf der
Festplatte vorhanden ist (eine übliche Situation bei Mod-Managern, die
ein Plugin als aktiv listen, ohne dessen Datei physisch in den
Datenordner des Spiels zu kopieren), erhält stattdessen eine
`size: -1, mtime: -1.0`-Signature, zusammen mit leeren
`ingredients`- und `effects`-Listen. Dieser Sentinel-Wert verhindert,
dass jeder künftige Scan wiederholt versucht, ein Plugin zu lesen, das
einfach nie auf der Festplatte gefunden wird, und dabei scheitert.

### 1.2 Ingredients

Ein Eintrag pro Zutat, die dieses Plugin definiert oder überschreibt.

| Feld | Gelesen aus | Bedeutung |
| :--- | :--- | :--- |
| `owner_file` | Die eigene FormID des `INGR`-Datensatzes, Byte 3 (Master-Index), aufgelöst gegen die Masterliste dieses Plugins | Das Plugin, das diese Zutat tatsächlich definiert, nicht notwendigerweise das Plugin, zu dem diese Cache-Datei gehört. Überschreibt dieses Plugin nur eine Zutat, die ein Master ursprünglich erstellt hat, nennt `owner_file` stattdessen diesen Master. Hat dieses Plugin die Zutat ursprünglich erstellt, nennt es sich selbst. |
| `local_id` | Die eigene FormID des `INGR`-Datensatzes, Bytes 2-0 | Eine stabile numerische Kennung für die Zutat, eindeutig zusammen mit `owner_file`. Anders als eine rohe FormID ändert sich dieser Wert nicht danach, welches Plugin darauf verweist. Siehe Abschnitt 2.1 für den Grund. |
| `form_id` | Die eigene FormID des `INGR`-Datensatzes, alle 4 Bytes, unverändert | Die FormID der Zutat genau so, wie der eigene Datensatz dieses spezifischen Plugins sie speichert, nützlich zum Abgleich mit einem Plugin-Bearbeitungstool. |
| `name` | `FULL`-Sub-Datensatz (literaler Text, oder ein Nachschlagen in der String-Tabelle bei einem lokalisierten Plugin) | Der Anzeigename der Zutat, genau wie das Spiel ihn zeigt. |
| `effect_refs` | Ein `EFID`/`EFIT`-Sub-Datensatz-Paar pro Eintrag | Bis zu 4 Einträge, einer pro Effekt, den diese Zutat erzeugt. |

Jeder `effect_refs`-Eintrag beschreibt einen Effekt, den die Zutat
erzeugt, mit der eigenen Stärke dieser Zutat dafür.

| Feld | Gelesen aus | Bedeutung |
| :--- | :--- | :--- |
| `effect_owner_file` | `EFID`, Byte 3 (Master-Index), aufgelöst gegen die Masterliste dieses Plugins | Das Plugin, in dem der Magieeffekt definiert ist. |
| `effect_local_id` | `EFID`, Bytes 2-0 | Die stabile numerische Kennung für den Magieeffekt. |
| `magnitude` | `EFIT`-Sub-Datensatz, Bytes 0-3 (32-Bit-Float) | Wie stark die Version dieser Zutat für den Effekt ist. |
| `duration` | `EFIT`-Sub-Datensatz, Bytes 8-11 (32-Bit-Ganzzahl) | Wie lange die Version dieser Zutat für den Effekt anhält. |

### 1.3 Effects

Ein Eintrag pro Magieeffekt, den dieses Plugin definiert oder
überschreibt, jeder, der in diesem Plugin existiert, unabhängig davon,
ob ihn tatsächlich eine Zutat verwendet.

| Feld | Gelesen aus | Bedeutung |
| :--- | :--- | :--- |
| `owner_file` | Die eigene FormID des `MGEF`-Datensatzes, Byte 3 (Master-Index), aufgelöst gegen die Masterliste dieses Plugins | Das Plugin, das diesen Magieeffekt tatsächlich definiert, nicht notwendigerweise das Plugin, zu dem diese Cache-Datei gehört. Dieselbe Override-Regel wie bei `owner_file` einer Zutat. |
| `local_id` | Die eigene FormID des `MGEF`-Datensatzes, Bytes 2-0 | Eine stabile numerische Kennung für den Magieeffekt, eindeutig zusammen mit `owner_file`. |
| `form_id` | Die eigene FormID des `MGEF`-Datensatzes, alle 4 Bytes, unverändert | Die FormID des Effekts, wie aus diesem Plugin gelesen. |
| `name` | `FULL`-Sub-Datensatz | Der Anzeigename des Effekts. |
| `cost` | `DATA`-Sub-Datensatz, Bytes 4-7 (32-Bit-Float) | Die Basiskosten des Effekts, eine echte Eigenschaft des Effekts selbst, verwendet bei der Bewertung eines Tranks. |
| `harmful` | `DATA`-Sub-Datensatz, Bytes 0-3 (32-Bit-Flags), Bit `0x01` (Hostile) oder `0x04` (Detrimental) | Ob das Spiel dies als schädlichen, giftartigen Effekt einstuft. Wahr, wenn eines der beiden Bits gesetzt ist. |

## 2. Woher diese Werte tatsächlich kommen

Keines der obigen Felder ist ein Wert, den sich dieses Projekt
ausdenkt: alle stammen aus Bytes, die Bethesdas eigenes Plugin-Format
bereits definiert. Dieses Projekt wählt nicht, wie eine FormID
strukturiert ist oder wie Effektdaten aufgebaut sind; es liest, was
bereits da ist.

### 2.1 FormIDs und lokale Identität

Jeder Datensatz, eine Zutat, ein Magieeffekt, was auch immer, hat eine
4-Byte-FormID, aufgeteilt in zwei Teile: das höchste Byte ist ein
Master-Index, der die Position des definierenden Plugins in der
eigenen Masterliste des Plugins dieses Datensatzes angibt, und die
unteren 3 Bytes sind die tatsächliche numerische Id des Datensatzes.

Das Master-Index-Byte ist der Haken: es ist ein Index in eine Liste,
die für jedes Plugin unterschiedlich ist, da jedes Plugin seine eigenen
Master in seiner eigenen Reihenfolge deklariert. Derselbe Datensatz
kann daher eine völlig andere rohe FormID haben, je nachdem, welches
Plugin darauf zeigt. Das Master-Index-Byte ergibt nur zusammen mit der
eigenen Masterliste dieses spezifischen Plugins Sinn.

`owner_file` und `local_id` umgehen das. `local_id` sind nur die
unteren 3 Bytes, der Teil, der nie von der Masterliste eines
bestimmten Plugins abhängt, und `owner_file` ist der tatsächliche
Dateiname, auf den das Master-Index-Byte zeigte, einmal für diesen
Cache-Eintrag aufgelöst mit der eigenen Masterliste dieses Plugins.
Zusammen identifizieren `owner_file` und `local_id` einen Datensatz auf
dieselbe Weise, egal welches Plugin darauf verweist, was genau das ist,
was gebraucht wird, um zu erkennen, dass sich zwei verschiedene Plugins
auf dieselbe Zutat oder denselben Effekt beziehen. Das rohe
`form_id`-Feld wird daneben aufbewahrt, hauptsächlich damit die
exakten Bytes, die dieses Plugin selbst gespeichert hat, weiterhin
gegen ein Plugin-Bearbeitungstool abgeglichen werden können.

### 2.2 Die eigenen Effektdaten einer Zutat

Die bis zu 4 Effekte einer Zutat stammen aus bis zu 4 Eintragspaaren
innerhalb ihres eigenen Datensatzes: ein `EFID`-Eintrag (die FormID des
referenzierten Effekts, auf dieselbe Weise aufgeteilt wie oben),
unmittelbar gefolgt von einem `EFIT`-Eintrag (12 Bytes: eine 32-Bit-
Magnitude, eine 32-Bit-Fläche und eine 32-Bit-Duration, in dieser
Reihenfolge).

`magnitude` und `duration` werden direkt aus diesen Bytes gelesen,
genau so, wie das Spiel sie speichert, ohne jede Skalierung oder
Rundung; das ist die einzige Stelle, aus der einer der beiden Werte
stammt. Es gibt keine separate Basis-Magnitude oder -Duration irgendwo
im Plugin-Format, auf die sich das bezieht. Die eigenen `EFIT`-Bytes
jeder Zutat sind bereits der vollständige, absolute Wert. Das
Flächenfeld existiert in derselben Struktur, hat aber keine Wirkung auf
den Trankwert in den eigenen Berechnungen dieses Projekts, also wird es
gelesen und sofort verworfen.

Dieselbe zugrunde liegende `DATA`-Struktur ist auch, wie die eigenen
`cost`- und `harmful`-Felder eines Magieeffekts gelesen werden, am
`MGEF`-Datensatz selbst statt von irgendeiner Zutat. Siehe das
[Effect-Cache](../effects/EFFECTS_CACHE.md)-Dokument für dieses Layout.

## 3. Wie sie befüllt wird

Ein Scan durchläuft die vollständige Liste aktiver Plugins, in der
Reihenfolge, in der das Spiel selbst sie laden würde. Für jedes
berechnet er die aktuelle Signature dieses Plugins und vergleicht sie
mit dem, was bereits zwischengespeichert ist.

Ist die Signature seit dem letzten Mal unverändert, wird die
zwischengespeicherte Datei genau so wiederverwendet, wie sie ist: die
eigenen binären Daten des Plugins werden nie wieder geöffnet, und diese
Datei bleibt auf der Festplatte unangetastet. Hat sich die Signature
geändert, oder wurde vorher nichts zwischengespeichert, werden die
binären Daten des Plugins (und seine gepackten Ressourcenarchive, für
jeden Text, der außerhalb des Plugins selbst gespeichert ist) frisch
gelesen, und eine neue Version dieser Datei ersetzt die alte. Ist das
Plugin als aktiv gelistet, aber auf der Festplatte fehlend, wird
stattdessen ein leerer Snapshot geschrieben, mit der Sentinel-Signature
aus Abschnitt 1.1.

Sobald jedes aktive Plugin auf diese Weise einen aktuellen Snapshot
hat, wird bei einem Plugin, das überhaupt nicht mehr Teil der aktiven
Liste ist, ein Mod, der deinstalliert oder einfach deaktiviert wurde,
dessen übrig gebliebene Cache-Datei gelöscht, statt sie unbegrenzt
liegen zu lassen.

Da nur tatsächlich geänderte Plugins erneut verarbeitet werden, betrifft
ein erneuter Scan nach einer kleinen Änderung, ein Mod hinzugefügt oder
aktualisiert, nur die Datei dieses einen Mods und ist fast sofort
fertig, statt jedes Mal jedes aktive Plugin neu zu verarbeiten. Ein
vollständiger, von Grund auf neuer Scan von allem kann bei Bedarf immer
noch erzwungen werden, zum Beispiel wenn der Cache selbst je verdächtigt
wird, beschädigt oder nicht mehr synchron zu sein.
