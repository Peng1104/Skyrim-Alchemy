# Binäre Lese-Abhängigkeiten: `sse-plugin-interface` und `sse-bsa`

Dieses Dokument beschreibt ein Risiko, das dieses Projekt bewusst
eingegangen ist: Die beiden Drittanbieter-Bibliotheken, auf die sich
`app/game_data/` beim Lesen der eigenen binären Formate von Skyrim
verlässt, sind beide relativ neu und wenig genutzt. Dieses Dokument hält
genau fest, was über sie verifiziert wurde und was passiert, wenn ein
Plugin oder BSA auf eine Formatvariante trifft, die sie nicht abdecken.

## 1. Was jede Bibliothek macht, und warum das Risiko besteht

- **`sse-plugin-interface`** (`app/game_data/_plugin_records.py`) parst
  `.esp`/`.esm`/`.esl`-Plugin-Dateien: Datensatz-/Subrecord-Struktur,
  `TES4`-Header, Masterlisten, `FormID`s.
- **`sse-bsa`** (`app/game_data/_bsa.py`) parst `.bsa`-Archive, verwendet
  zum Extrahieren von `.strings`-Dateien für lokalisierten Text (siehe
  [DATA_SOURCES.de.md §1.2](../data-sources/DATA_SOURCES.de.md#12-lokalisierte-strings-und-der-dlc-bsa-fallback)).

Beide sind reine Python-Implementierungen von Bethesdas undokumentierten,
per Reverse Engineering erschlossenen Binärformaten, gepflegt von kleinen
Open-Source-Projekten mit vergleichsweise wenigen Commits/Stars auf GitHub
im Vergleich zu z. B. `pydantic` oder `requests`. Das ist ein echtes
Risiko für ein Projekt, das jetzt von ihnen als **einziger** Quelle für
Zutaten-/Effektdaten abhängt (siehe
[DATA_SOURCES.de.md §0](../data-sources/DATA_SOURCES.de.md#0-warum-nicht-das-wiki))
— eine Formatvariante, die keine der beiden Bibliotheken behandelt, könnte
still falsche oder fehlende Daten erzeugen statt eines sauberen Fehlers,
wenn nichts anderes dagegen absichert.

## 2. Was tatsächlich verifiziert wurde

Das wurde nicht einfach angenommen. Beide Bibliotheken wurden in dieser
Sitzung end-to-end gegen die zwei in der Praxis wichtigsten realen Fälle
getestet, an einer echten, stark modifizierten Installation (~170 aktive
Plugins):

- **Ein kleiner, inoffizieller, nicht lokalisierter Mod**: `whitewind
  player home.esp` (ein Hobby-Mod, kein offizielles Bethesda-/CC-Release).
  Die `FULL`-Subrecord seiner Zutat enthält **literalen Text**
  (`"Frozen Bee"`) direkt im Datensatz — überhaupt kein BSA beteiligt,
  was das Datensatz-/Subrecord-Parsing von `sse-plugin-interface` allein
  auf die Probe stellt, an einem Plugin, das mit einer völlig anderen,
  nicht-professionellen Pipeline gebaut wurde als Bethesdas eigene Tools.
- **Ein offizielles, lokalisiertes Creation-Club-Release**:
  `ccbgssse037-curios.esl` (Curios). Die `FULL`-Subrecords seiner Zutaten
  enthalten **numerische lokalisierte String-IDs** (z. B. `7`), was
  erfordert, dass `sse-bsa` `ccbgssse037-curios.bsa` öffnet,
  `strings/ccbgssse037-curios_english.strings` extrahiert, und
  `sse-plugin-interface`s eigene String-ID-Behandlung den Datensatz
  korrekt auflöst — was beide Bibliotheken zusammen auf die Probe stellt,
  an einem Plugin, das mit Bethesdas eigener offizieller Pipeline gebaut
  wurde.

Beide Fälle stimmten exakt mit den Erwartungen überein (verifiziert gegen
bekannte Zutatennamen, `EFIT`-Werte und — speziell für Curios — abgeglichen
mit der eigenen FormID-Ausgabe eines `help`-Konsolenbefehls im Spiel selbst,
siehe [DATA_SOURCES.de.md §1.3](../data-sources/DATA_SOURCES.de.md#13-creation-club-und-skyrimccc)).
Zusammen mit dem vollständigen Scan von 218 Zutaten/65 Effekten über jedes
Plugin einer echten Ladereihenfolge, der mit bekannten Referenzwerten
übereinstimmte (Vanilla, DLC und mehrere weitere CC-/Mod-Zutaten, die
während der Entwicklung dieser Sitzung einzeln stichprobenartig geprüft
wurden), deckt das die zwei strukturell unterschiedlichen Arten ab, wie
eine `FULL`-Subrecord kodiert sein kann — was die eigentliche Risikoachse
für diese Bibliotheken ist, nicht der Feinschliff oder die Größe irgendeines
bestimmten Plugins.

## 3. Was passiert, wenn eine Variante nicht abgedeckt ist

Es wurde nichts beobachtet, was diese Bibliotheken nicht parsen können.
Aber der Scanner ist absichtlich so gebaut, dass er, falls doch einmal
etwas auftaucht, **laut für genau diese eine Zutat** fehlschlägt, nie
stillschweigend:

- `resolve_full` (`app/game_data/_strings.py`) gibt `None` zurück, wann
  immer es einen `FULL`-Wert nicht auflösen kann — ein fehlender
  `.strings`-Eintrag, ein nicht parsbares BSA, oder jeder andere Fehler
  bricht auf dasselbe `None` zusammen, nie eine falsche Vermutung.
- `_scan_plugin` (`app/game_data/_scan.py`) prüft genau darauf: Eine Zutat,
  deren Name sich nicht auflösen lässt, gibt
  `game_data_ingredient_unresolved` aus (mit der `EDID` des Datensatzes
  und dem definierenden Plugin, also nachvollziehbar) und wird
  **übersprungen** — sie landet nie mit einem falschen oder leeren Namen
  in `ingredients.json`.
- Ein Plugin, das komplett nicht geladen werden kann (`load_plugin` wirft
  eine Exception, z. B. eine echt beschädigte oder nicht unterstützte
  Datei), gibt `game_data_scan_plugin_unreadable` aus, und dieses gesamte
  Plugin wird übersprungen — dasselbe Prinzip auf gröberer Ebene.

In beiden Fällen läuft der Scan für jedes andere Plugin/jede andere Zutat
weiter — ein nicht parsbarer Datensatz oder ein nicht parsbares Plugin
bricht nicht den gesamten Lauf ab, und der Fehler bleibt immer in der
Konsolen-/Log-Ausgabe sichtbar, wird nie verschluckt.

## 4. Versionsfixierung

`pyproject.toml` deklariert derzeit offene Untergrenzen:

```toml
"sse-plugin-interface>=1.0.1",
"sse-bsa>=1.1.0",
```

`uv.lock` löst das auf exakte Versionen auf (`1.0.1` und `1.1.0` zum
Zeitpunkt dieses Schreibens), und `uv sync` installiert genau das, was das
Lockfile vorgibt, sodass eine normale Installation bereits reproduzierbar
ist. Die `>=`-Grenze in `pyproject.toml` selbst verhindert jedoch nicht,
dass ein zukünftiges `uv lock --upgrade` stillschweigend eine neuere
Major-Version einer der beiden Bibliotheken zieht, ohne eine bewusste
Entscheidung dafür — für die meisten Abhängigkeiten ist das unproblematisch,
aber für zwei Bibliotheken, für die dieses Projekt keinen Fallback mehr hat
(es gibt kein Wiki mehr, auf das zurückgegriffen werden könnte) und die von
kleinen, wenig aktiven Projekten gepflegt werden, ist ein ungeprüfter
Major-Sprung genau die Art von Änderung, die eine bewusste Entscheidung
erfordern sollte, statt als Nebenwirkung der Aktualisierung eines
unabhängigen Pakets zu passieren. Beim nächsten Anfassen einer der beiden
mit `==` statt `>=` fixieren, damit ein Versionssprung für genau diese
beiden immer über eine explizite, überprüfte Bearbeitung der
`pyproject.toml` läuft.
