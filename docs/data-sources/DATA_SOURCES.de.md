# Zutaten- und Effektdaten (binäres Lesen der Plugins)

Dieses Dokument beschreibt, woher die Zutaten- und Effektdaten des Projekts
stammen: **die eigenen binären Daten jedes aktiven Skyrim-Plugins**
(`.esm`/`.esp`/`.esl`), direkt gelesen — kein Wiki, kein Scraping, keine
HTTP-Anfragen. Die Referenzimplementierung befindet sich in
`app/game_data/` (`_scan.py`, `_load_order.py`, `_plugin_records.py`,
`_bsa.py`, `_strings.py`).

Nur die CLI (`cli.py`) scannt die Spielinstallation und schreibt den Cache
— sie ist der einzige Prozess mit einem lokalen `game_directory`. Der
`AlchemyOptimizer` (`app/optimizer/_engine.py`) und die API lesen nur den
Cache (`load_cached_game_data`, `app/game_data/__init__.py`) — siehe
[Abschnitt 3](#3-cache) für das, was passiert, wenn dieser Cache fehlt.

## 0. Warum nicht das Wiki

Frühere Versionen dieses Projekts scrapten [UESP](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects)
für Zutaten-/Effektdaten, einschließlich einer "Basisstärke"/"Basisdauer"
pro Effekt. Das eigene binäre Format des Spiels direkt zu lesen zeigte, dass
dieses Konzept gar nicht existiert: Ein Effekt (`MGEF`) hat nur `cost` und
eine `harmful`-Flag als echte, vom Spiel definierte Eigenschaften. Stärke
und Dauer sind überhaupt keine Eigenschaft des *Effekts* — sie gehören zu
jeder einzelnen *Zutat*, pro Zutat in den `EFIT`-Einträgen ihres
`INGR`-Datensatzes gespeichert. UESPs "Basis"-Werte sind eine redaktionelle
Konvention (die Werte, die die meisten "Standard"-Zutaten zufällig teilen),
kein Feld, das der Spiel-Engine irgendwo ausliest — und diese Konvention
hat echte Lücken (z. B. Effekte wie *Fortify Alchemy*, die im Spiel
existieren, aber überhaupt nicht in UESPs Effekttabelle stehen). Das binäre
Lesen umgeht beide Probleme: Jeder Wert stammt aus genau denselben Daten,
die die Spiel-Engine selbst verwendet, und jeder Effekt, den irgendeine
aktive Zutat tatsächlich erzeugt, ist enthalten — ob Vanilla, DLC, Creation
Club oder Drittanbieter-Mod.

### 0.1 Bestätigter Fall: der alte `cost_factor` zählte die Dauer doppelt (Giant's Toe)

Die `Effect`/`IngredientEffect`-Modelle vor dieser Refaktorierung hatten
einen `cost_factor` (gescrapt vom "Value"-Modifikator-Icon der UESP für das
Zutat-Effekt-Paar), der direkt in die Kosten eines Effekts multiplizierte,
zusätzlich zu separaten `magnitude`/`duration`-Faktoren. Der Plan für diese
Refaktorierung entfernte `cost_factor` vollständig und markierte das als
angenommenes Risiko, da es keine bekannte binäre Entsprechung in
`EFIT`/`MGEF` hatte und während der Entwicklung kein Fall aufgetreten war,
der ihn gebraucht hätte.

Ein echter Fall trat danach auf, beim Vergleich der Ausgabe des alten und
neuen Systems am selben echten Inventar: **Giant's Toe**, kombiniert mit
*Blisterwort* und *Wheat*, wurde im alten, wiki-gescrapten System mit
**544,239** Gold bewertet, im neuen, `.esm`-basierten mit **119,654** — ein
Unterschied von ~4,5x, vollständig auf einen einzigen geteilten Effekt
zurückzuführen: *Fortify Health*. Giant's Toes echtes `EFIT` gibt ihm
`magnitude=4, duration=300` für *Fortify Health* (`Wheat`s eigenes
`Fortify Health`-`EFIT` ist `magnitude=4, duration=60` — der unmodifizierte
Fall), was das neue System direkt liest und verwendet. Das alte System
hatte *zusätzlich* ein `Value: 5.9`-Modifikator-Icon aus UESPs
Zutatentabelle für genau dieses Paar gescrapt und es als **zusätzlichen**
multiplikativen `cost_factor` angewendet — obendrauf auf den
Dauerunterschied, der bereits in `duration=300` eingebacken war.

Diese `5.9` war von Anfang an nie ein eigenständiger Multiplikator — es ist
UESPs eigene Prosa-Erklärung der *Konsequenz* der 5-fachen Dauererhöhung,
kein separater Spielmechanismus:

$$
\left(\frac{300}{10}\right)^{1.1} \Big/ \left(\frac{60}{10}\right)^{1.1}
= 5^{1.1} \approx 5{,}874 \approx 5{,}9
$$

also genau der eigene Dauerterm der Wertformel selbst (Abschnitt 1.1 von
[docs/calculation/CALCULATION.de.md](../calculation/CALCULATION.de.md#11-effektkosten)),
hoch zum selben Exponenten 1.1, der bereits auf jeden Effekt angewendet
wird. Der alte Scraper hielt dieses beschreibende Verhältnis fälschlich für
einen eigenständigen `Value`-Modifikator und multiplizierte ihn als
`cost_factor` hinein — und zählte damit dieselbe Dauererhöhung doppelt, die
`duration=300` bereits berücksichtigte. Das neue System, das `duration=300`
direkt aus `EFIT` liest, ganz ohne `cost_factor`-Konzept, berechnet den
korrekten Wert nur einmal.

Am selben echten Inventar stimmten 88 von 89 Rezepten ohne Mod-Zutat exakt
zwischen dem alten und neuen System überein (bit-genau beim endgültigen
Goldwert); dieser Giant's-Toe-Fall war der einzige Ausreißer, und er löste
sich zugunsten des neuen Systems auf — was bestätigt, dass die Entfernung
von `cost_factor` eine Fehlerbehebung war, keine Regression, zumindest für
jeden bisher getesteten Fall.

## 1. Zutaten

Jede Zutat in der aktiven Ladereihenfolge wird zu einer `Ingredient`,
aufgebaut aus ihrem `INGR`-Datensatz:

- **Name** — die `FULL`-Subrecord des Datensatzes, aufgelöst über
  `resolve_full` (`app/game_data/_strings.py`): entweder literaler Text
  oder eine lokalisierte String-ID, aufgelöst gegen das `.strings`-BSA des
  definierenden Plugins (siehe
  [Abschnitt 1.2](#12-lokalisierte-strings-und-der-dlc-bsa-fallback)).
- **Effekte** — bis zu 4 `IngredientEffect`s, eine pro `EFID`+`EFIT`-Paar
  des Datensatzes. `EFIT` (12 Bytes) enthält die Magnitude (float32), Area
  (uint32, von diesem Projekt ungenutzt) und Duration (uint32) des Effekts
  **genau so, wie diese Zutat ihn erzeugt** — es gibt keine gemeinsame
  "Basis", relativ zu der das irgendetwas wäre (siehe
  [CALCULATION.de.md §1](../calculation/CALCULATION.de.md#1-effektkosten-und-die-absolute-stärkedauer-einer-zutat)).
- **`source_file`/`form_id`** — der Plugin-Dateiname und die Hex-FormID des
  *autoritativen* (nach Overrides) Datensatzes der Zutat — siehe
  [Abschnitt 1.1](#11-override-auflösung).

Zum Zeitpunkt dieses Schreibens erzeugt ein vollständiger Scan einer echten
modifizierten Installation **218 Zutaten**. Das ist nirgendwo fest codiert
— es ist das, was die aktive Ladereihenfolge tatsächlich enthält —, aber es
ist die praktische Obergrenze dafür, wie viele unterschiedliche
Zutatenarten der Optimierer jemals sehen kann, was für dessen
Worst-Case-Kombinationszahl relevant ist (siehe
[Abschnitt 6.1 des Berechnungsdokuments](../calculation/CALCULATION.de.md#61-anzahl-der-kombinationen)).

### 1.1 Override-Auflösung

Skyrims Plugin-Format erlaubt es einem späteren Plugin (in der
Ladereihenfolge), den Datensatz eines früheren Plugins neu zu definieren,
indem es dessen FormID wiederverwendet — ein echter Override, kein neuer
Gegenstand. Die eigenen `INGR`/`MGEF`-Datensätze jedes Plugins werden
zuerst isoliert zu einem Snapshot pro Plugin geparst (`_scan_plugin`,
`app/game_data/_scan.py` — siehe
[Abschnitt 3.1](#31-inkrementelles-scannen), warum das pro Plugin
cachebar ist); `_merge_snapshots` baut dann die Ladereihenfolge einmal auf
— Vanilla-Master, dann in `Skyrim.ccc` gelisteter Creation-Club-Inhalt
(siehe [Abschnitt 1.3](#13-creation-club-und-skyrimccc)), dann
`Plugins.txt`s aktive Plugins, in dieser Reihenfolge — und indiziert jeden
`INGR`/`MGEF`-Datensatz nach seiner kanonischen Identität
`(defining_file, local_id)`, aufgelöst über `resolve_form_id`. Ein späteres
Plugin in der Ladereihenfolge überschreibt einfach den Indexeintrag für
eine FormID, die ein früheres Plugin bereits definiert hat, sodass der
Index am Ende nur die endgültige, autoritative Version jedes Datensatzes
enthält — genau so, wie die Spiel-Engine selbst Overrides auflöst. Siehe
[docs/game_data/GAME_DATA.de.md](../game_data/GAME_DATA.de.md) für die
vollständige Mechanik, einschließlich des daraus folgenden
Namenskollisionsrisikos.

`source_file`/`form_id` bei `Ingredient`/`Effect` spiegeln diese
autoritative Version wider, nicht unbedingt das Plugin, das das Objekt
ursprünglich eingeführt hat — z. B. meldet eine Zutat, die ursprünglich von
einem Creation-Club-Plugin hinzugefügt, aber seither vom Unofficial Skyrim
Special Edition Patch (USSEP) gepatcht wurde, USSEP als ihre `source_file`.

### 1.2 Lokalisierte Strings und der DLC-BSA-Fallback

Die `FULL`-Subrecord eines Datensatzes kann entweder literalen Text oder
eine numerische lokalisierte String-ID enthalten; in letzterem Fall lebt
der eigentliche Text in einer `.strings`-Datei innerhalb eines der eigenen
BSAs des definierenden Plugins
(`strings/<plugin_stamm>_<sprache>.strings`, geparst von
`parse_strings_file`). Eine echte Lücke, die während der Validierung
gefunden wurde: Skyrim SE liefert `Dawnguard.esm`, `HearthFires.esm`,
`Dragonborn.esm` und `Update.esm` **ganz ohne eigenes BSA** aus — ihre
Strings sind stattdessen im eigenen `Skyrim - Interface.bsa` von
`Skyrim.esm` gebündelt, unter dem eigenen Stamm jeder DLC.
`_load_strings_table` (`app/game_data/_strings.py`) weicht auf die BSAs
von `Skyrim.esm` aus, wann immer die stammbasierte Suche eines Plugins
nichts findet — das deckt diesen Fall ab, ohne einen bestimmten
DLC-Dateinamen fest zu codieren.

### 1.3 Creation Club und `Skyrim.ccc`

Creation-Club-Inhalt wird **nicht** so in `Plugins.txt` gelistet wie ein
gewöhnlicher Mod — Bethesdas Engine lädt automatisch alles, was in
`Skyrim.ccc` steht (eine reine Textdatei, ein Plugin pro Zeile, im
Installations-Root des Spiels, nicht in irgendeinem Mod-Manager-Profil),
völlig unabhängig von `Plugins.txt`. Das wurde empirisch bestätigt: Das
In-Game-Creations-Menü zeigte ein Creation-Club-Paket als aktiv, obwohl
`plugins.txt` von Mod Organizer 2 überhaupt keinen Eintrag dafür hatte —
MO2 listet Creation-Club-Inhalt nur als "Not managed by MO2"-Mod-
Prioritätseintrag (ein Artefakt der Dateikonflikt-Reihenfolge, unabhängig
davon, ob das Plugin tatsächlich lädt). `_resolve_load_order`
(`app/game_data/_scan.py`) liest `Skyrim.ccc` über `parse_ccc`
(`app/game_data/_load_order.py`) und fügt jedes dort gelistete Plugin in
die Ladereihenfolge ein, zwischen den Vanilla-Mastern und `Plugins.txt`s
eigenem Inhalt, sodass Creation-Club-Zutaten/-Effekte genauso gescannt
werden wie alles andere.

`Skyrim.ccc` (und die Vanilla-Masterliste) benennt Plugins mit Bethesdas
eigener gemischter Groß-/Kleinschreibung (z. B. `ccBGSSSE037-Curios.esl`),
was nicht unbedingt mit dem tatsächlichen Dateinamen auf der Festplatte
übereinstimmt, wenn das Dateisystem Groß-/Kleinschreibung unterscheidet —
eine mit Windows geteilte Steam-Bibliothek, unter Linux eingebunden, ist
üblicherweise ext4, anders als NTFS' eigener, standardmäßig
groß-/kleinschreibungsunabhängiger Modus. Eine naive `.exists()`-Prüfung
gegen die Schreibweise der `.ccc` lässt das Plugin still und leise aus dem
gesamten Scan fallen, wenn beide voneinander abweichen; empirisch an einer
echten Installation bestätigt, wo 74 von 75 `Skyrim.ccc`-Einträgen eine
exakte Schreibweisenprüfung auf diese Weise nicht bestanden, und jede ihrer
Zutaten, die nicht von einem anderen aktiven Plugin überschrieben wurde
(also nie indirekt über die eigene, korrekt geschriebene Masterliste eines
anderen Plugins gelesen wurde), im Zutatendatenbestand komplett fehlte.
`_index_data_dir_case_insensitively` (`app/game_data/_scan.py`) baut
einmal pro Scan eine Zuordnung kleingeschriebener Name → tatsächlicher
Name auf der Festplatte auf, und jeder Plugin-Name aus
`Skyrim.ccc`/der Vanilla-Masterliste/`Plugins.txt` wird darüber aufgelöst,
bevor er zur Ladereihenfolge hinzugefügt wird, sodass der Rest des Scans
Dateien immer mit ihrer echten, exakten Schreibweise öffnet, unabhängig
davon, welche Schreibweise die Quellliste verwendet hat.

### 1.4 Risiko von Namenskollisionen

Zwei **unabhängige** Datensätze (unterschiedliche FormIDs, keine
Override-Beziehung) können immer noch zufällig auf denselben
Anzeigenamen aufgelöst werden — das ist ein echtes, wenn auch seltenes
Risiko, das dem Indizieren der endgültigen Dictionaries nach Namen statt
nach FormID inhärent ist. Siehe
[docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) für die
vollständige Erklärung, einschließlich eines echten Falls, auf den dieses
Projekt während der Entwicklung gestoßen ist (ein reiner Quest-Effekt aus
Dragonborn.esm, der zufällig auf denselben Text auflöste wie der echte
Alchemie-Effekt "Damage Health").

## 2. Effekte

Ein `Effect` wird nur für ein `MGEF` erzeugt, das tatsächlich von der
`EFID` einer Zutat referenziert wird — das Spiel definiert viele tausend
`MGEF`-Datensätze ohne Bezug zur Alchemie (Verzauberungen,
Quest-/Skript-Fähigkeiten usw.), und die Effekttabelle bedingungslos aus
*jedem* `MGEF` aufzubauen ließ einen solchen irrelevanten Datensatz still
einen echten Alchemie-Effekt überschreiben, der zufällig denselben
Anzeigetext teilte (siehe
[docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) für diesen
konkreten Fall). Jeder `Effect` liest zwei Felder direkt aus `MGEF.DATA`
(`get_mgef_base_cost`/`get_mgef_harmful`, `app/game_data/_plugin_records.py`):

- **`cost`** — der Base-Cost-float32 bei Offset 4.
- **`harmful`** — ob das Hostile-Flag-Bit (`0x01`) oder das
  Detrimental-Flag-Bit (`0x04`) bei Offset 0 gesetzt ist. Während der
  Entwicklung gegen 205 von UESP dokumentierte Effekte validiert, ohne
  Abweichungen.

`cost` (und jeder andere aus einem Plugin gelesene Float, einschließlich
`magnitude`/`duration` jeder Zutat) wird exakt so gespeichert, wie der
float32-Wert des Spiels selbst dekodiert — absichtlich nicht gerundet. Ein
Wert wie `0.30000001192092896` für ein `cost`, das UESP selbst als `0.3`
dokumentiert, ist keine Beschädigung: `0.3` hat keine exakte binäre
Gleitkommadarstellung, sodass die eigenen float32-Bytes des Spiels auf
denselben, nächstliegenden darstellbaren Wert dekodieren; die Umwandlung
in Pythons float64 zur JSON-Serialisierung macht die bereits vorhandene
Ungenauigkeit nur sichtbar, statt sie zu verstecken. Das Ziel ist, exakt
den Wert zu behalten, den das `.esm` selbst speichert, nicht eine
hübschere, gerundete Annäherung davon.

Es gibt überhaupt kein `magnitude`/`duration`-Feld bei `MGEF` — bestätigt
durch das Lesen von xEdits eigenen Datensatzdefinitionen
(`Core/wbDefinitionsTES5.pas`) zusätzlich zu den rohen Bytes. Siehe
[CALCULATION.de.md §1](../calculation/CALCULATION.de.md#1-effektkosten-und-die-absolute-stärkedauer-einer-zutat)
dafür, wie sich `cost`/`harmful` mit den eigenen `EFIT`-Werten jeder Zutat
kombinieren.

## 3. Cache

`scan_game_data` (`app/game_data/_scan.py`) schreibt unter `cache/game_data/`:

```
cache/game_data/
├── plugins/             Eine kleine JSON-Datei pro rohem Plugin-Scan-Ergebnis (<Plugin-Dateiname>.json)
├── ingredients.json    Die endgültige, zusammengeführte Ingredient-Datenbank
└── effects.json         Die endgültige, zusammengeführte Effect-Datenbank
```

### 3.1 Inkrementelles Scannen

Das Scannen erfolgt inkrementell **pro Plugin**, nicht alles-oder-nichts.
Die eigenen `INGR`/`MGEF`-Datensätze jedes aktiven Plugins werden zu einem
`PluginGameDataSnapshot` (Name, aufgelöster Anzeigetext, kanonische
FormIDs — siehe `app.models`) verarbeitet, der nur von den eigenen Bytes
dieses Plugins und seinen eigenen BSA(s) abhängt, nie von irgendeinem
anderen Plugin in der Ladereihenfolge. Dieser Snapshot wird unter seiner
eigenen Cache-Invalidierungssignatur (Größe + mtime) in seiner eigenen
Datei gespeichert, `cache/game_data/plugins/<Plugin-Dateiname>.json` — eine
kleine Datei pro Plugin statt einer großen Datei für alle zusammen, sodass
der eigene Beitrag eines Plugins sich isoliert einsehen lässt und ein
erneuter Scan nur die Dateien der Plugins neu schreibt, die sich
tatsächlich geändert haben (siehe unten). Bei einem späteren Scan verwendet
ein Plugin, dessen Signatur noch übereinstimmt, seinen zwischengespeicherten
Snapshot unverändert weiter — das eigentliche Binär-/BSA-Parsen wird für
dieses Plugin komplett übersprungen — und nur tatsächlich geänderte Plugins
werden erneut geparst. Der (günstige, rein im Speicher ablaufende) Schritt,
der `FormID`-Overrides und plugin-übergreifende Effektnamens-Referenzen
über die gesamte Ladereihenfolge auflöst, läuft trotzdem bei jedem Scan,
über welche Mischung aus zwischengespeicherten und frisch geparsten
Snapshots die aktuelle Ladereihenfolge auch braucht, und erzeugt
`ingredients.json`/`effects.json`.

Das macht in der Praxis einen Unterschied: Bei einer echten Installation
mit ~100 aktiven Plugins dauerte ein vollständiger Scan (jedes Plugin neu
geparst, z. B. nach der Installation vieler Mods auf einmal, oder über
`force=True` von `--refresh`) **~30 Sekunden**; das Anfassen der mtime
eines einzigen Plugins und ein erneuter Scan (jeder andere Snapshot aus
dem Cache wiederverwendet, seine Datei auf der Festplatte unangetastet)
dauerte **~0,2 Sekunden** — ein Unterschied von ~150x, genau für den
häufigen Fall, ein oder zwei Mods auf einmal hinzuzufügen/zu
aktualisieren/zu entfernen.

Ein Plugin, das seit dem letzten Scan aus der Ladereihenfolge entfernt
wurde (Mod deinstalliert, oder `Plugins.txt`/`Skyrim.ccc` listet es nicht
mehr), bekommt seine `cache/game_data/plugins/<Name>.json` beim nächsten
Speichern der Snapshots gelöscht, statt für immer im Cache-Verzeichnis zu
verbleiben.

Nur die CLI ruft jemals `scan_game_data` auf — sie ist der einzige Prozess
mit einem lokalen `game_directory`, um `.esm`/`.esp`/`.esl`/`.bsa`-Dateien
zu lesen.

### 3.2 Den Cache lesen

`AlchemyOptimizer.__init__` ruft `load_cached_game_data`
(`app/game_data/__init__.py`) auf, das immer nur
`ingredients.json`/`effects.json` liest — nie scannt, und
`cache/game_data/plugins/` überhaupt nie anfasst (dieses Verzeichnis
existiert nur, um `scan_game_data` selbst schneller zu machen; nichts
außerhalb von `app/game_data/_scan.py` liest es). Existiert
`cache/game_data/ingredients.json` noch nicht, wirft
`load_cached_game_data` `GameDataNotCachedError`; die API (`app/api.py`)
lässt das zu einem `RuntimeError` beim Import propagieren, sodass der
Prozess beim Start laut und mit einer klaren Meldung fehlschlägt, statt
Anfragen gegen eine leere Datenbank zu bedienen. Zuerst die CLI mit
`--refresh` gegen eine lokale Skyrim-Installation ausführen, um den Cache
zu befüllen:

```bash
uv run python cli.py --refresh
```

Um Änderungen nach dem Installieren/Entfernen/Neuordnen von Plugins zu
übernehmen, erneut mit `--refresh` ausführen — es gibt keinen separaten
Endpunkt oder keine Flag zum Leeren des Caches; laut
[Abschnitt 3.1](#31-inkrementelles-scannen) wird ein unverändertes Plugin
nie erneut geparst, sodass ein Refresh selbst bei vielen installierten
Plugins günstig ist. `force=True` (die tatsächliche Wirkung von
`--refresh`) parst trotzdem jedes Plugin von Grund auf neu und schreibt
jede Datei unter `cache/game_data/plugins/` neu, unter Ignorieren jedes
zwischengespeicherten Snapshots — nützlich, falls der Cache selbst im
Verdacht steht, veraltet oder beschädigt zu sein, obwohl die fehlerhafte
Cache-Datei eines einzelnen Plugins bereits für sich sauber behandelt wird
(als fehlend betrachtet, was nur dieses eine Plugin zu einem erneuten Scan
zwingt, ohne dass `--refresh` explizit nötig wäre).
