# Spieldaten-Scan: Override-Auflösung und Namenskollisionsrisiko

Dieses Dokument beschreibt, wie `app/game_data/` Overrides zwischen Plugins
auflöst, und eine spezifische, bekannte Einschränkung, die sich daraus
ergibt: Zwei **unabhängige** Datensätze, die zufällig auf denselben
Anzeigenamen auflösen, werden nicht beide behalten — die Dictionaries, die
dieses Projekt aufbaut, sind nach Namen indiziert, sodass einer von ihnen
stillschweigend verworfen wird. Die Referenzimplementierung ist
`app/game_data/_scan.py` (`_scan_plugin`, `_merge_snapshots`).

## 1. Wie Overrides aufgelöst werden

Das Scannen geschieht in zwei Stufen (siehe
[DATA_SOURCES.de.md §3.1](../data-sources/DATA_SOURCES.de.md#31-inkrementelles-scannen)
für das vollständige Bild des inkrementellen Cachings). `_scan_plugin`
parst die eigenen `INGR`/`MGEF`-Datensätze eines Plugins isoliert und
berechnet die kanonische Identität `(owner_file, local_id)` jedes
Datensatzes über `resolve_form_id` (`app/game_data/_plugin_records.py`),
angewendet gegen die eigene Masterliste dieses Plugins — dieser Schritt
schaut nie auf ein anderes Plugin, was genau das ist, was sein Ergebnis
(einen `PluginGameDataSnapshot`) sicher pro Plugin cachebar macht.

`_merge_snapshots(load_order, snapshots)` durchläuft dann die gesamte
aktive Ladereihenfolge **einmal** — Vanilla-Master, dann in `Skyrim.ccc`
gelisteter Creation-Club-Inhalt, dann `Plugins.txt`s aktive Plugins, in
genau dieser Reihenfolge (siehe
[DATA_SOURCES.de.md §1.3](../data-sources/DATA_SOURCES.de.md#13-creation-club-und-skyrimccc))
— und indiziert jeden Datensatz eines Typs nach derselben kanonischen
Identität. Wenn ein späteres Plugin in der Ladereihenfolge einen Datensatz
mit derselben kanonischen Identität wie einer, den ein früheres Plugin
bereits indiziert hat, definiert (ein echter Override — das spätere Plugin
listet das frühere als Master und verwendet dessen FormID wieder), **ersetzt**
der spätere Eintrag den früheren im Index. Wenn die gesamte Ladereihenfolge
durchlaufen wurde, enthält jeder Schlüssel im Index nur seine endgültige,
autoritative Version — genau so, wie die Spiel-Engine selbst Overrides
auflöst, und genau deshalb meldet `Ingredient`/`Effect.source_file` das
Plugin, das aktuell für diese FormID *gewinnt*, nicht unbedingt das, das sie
ursprünglich eingeführt hat (siehe
[DATA_SOURCES.de.md §1.1](../data-sources/DATA_SOURCES.de.md#11-override-auflösung)).

Dieser Teil ist FormID-genau: Es ist nicht möglich, einen echten Override
mit einem unabhängigen neuen Datensatz zu verwechseln, oder umgekehrt, weil
die kanonische Identität aus der tatsächlichen, master-listen-relativen
FormID-Mathematik abgeleitet wird, die das Spiel selbst verwendet — und
bleibt genau, egal wie viele Plugins aus dem Cache wiederverwendet vs. in
`_scan_plugin` frisch geparst wurden, da die eigenen kanonischen
Identitäten eines zwischengespeicherten Snapshots genau auf dieselbe Weise
berechnet wurden, als die Bytes dieses Plugins zuletzt tatsächlich gelesen
wurden.

## 2. Wo die FormID-Genauigkeit endet: die endgültigen Dictionaries sind nach Namen indiziert

Die zweite Hälfte von `_merge_snapshots` verwandelt den nach FormID
indizierten Index in die `dict[str, Ingredient]`/`dict[str, Effect]`, die
der Rest des Projekts verwendet, indiziert nach dem **aufgelösten
Anzeigenamen** jedes Datensatzes — hier gilt FormID-Genauigkeit nicht mehr.
Wenn zwei Datensätze mit echt unterschiedlichen, unabhängigen kanonischen
Identitäten (überhaupt keine Override-Beziehung zwischeneinander) zufällig
auf denselben Anzeige-String auflösen, überlebt nur einer von ihnen im
endgültigen Dictionary; Pythons eigene `dict`-Zuweisung überschreibt den
anderen stillschweigend. Die Iterationsreihenfolge über den Index folgt der
Einfügereihenfolge während des Merges (Position in der Ladereihenfolge,
nach Master-Datei gruppiert), sodass in der Praxis **wer auch immer bei
diesem Durchlauf zuletzt verarbeitet wird, gewinnt** — nicht unbedingt der,
der semantisch "richtig" oder der zuletzt überschriebene ist; es ist rein
eine Namenskollision, unabhängig vom Override-Mechanismus aus Abschnitt 1.

## 3. Ein echter Fall während der Entwicklung

Effekte sind der Fall, den dieses Projekt tatsächlich beobachtet hat, keine
Hypothese. Anfangs wurde `effects` bedingungslos aus **jedem** `MGEF` im
Index aufgebaut (spiegelbildlich dazu, wie `ingredients` aus jedem `INGR`
aufgebaut wird). Das ergab 1525 Effekte — weit mehr, als die Alchemie hat
— und eine Stichprobe von "Damage Health" zeigte `cost=5.0,
source_file='Dragonborn.esm'` statt des korrekten `cost=3.0,
source_file='Skyrim.esm'`. Die Ursache: `Dragonborn.esm` definiert ein
echt unabhängiges, reines Quest-`MGEF` (`DLC2TTR4aAbDamageHealth`, verwendet
von einer geskripteten Quest-Fähigkeit, ohne jeden Bezug zur Alchemie),
dessen `FULL`-Text *ebenfalls* zufällig auf "Damage Health" auflöst —
derselbe String, komplett andere FormID, keine Override-Beziehung. Da
`Dragonborn.esm` in der Ladereihenfolge nach `Skyrim.esm` verarbeitet wird,
überschrieb sein unabhängiges `MGEF` stillschweigend den Eintrag des
echten Alchemie-Effekts.

Die Behebung war **kein** Namenskollisions-Detektor — es war die
Einschränkung dessen, was überhaupt erst zu einem `Effect` wird:
`_merge_snapshots` fügt ein `MGEF` nur dann zum `effects`-Dictionary hinzu,
wenn die `EFID` einer Zutat es tatsächlich referenziert, was die
überwiegende Mehrheit der `MGEF`-Datensätze (Verzauberungen,
Quest-Fähigkeiten usw.) ausschließt, bevor sie überhaupt das nach Namen
indizierte Dictionary erreichen. Das senkte die Effektanzahl von 1525 auf
63 und behob den Damage-Health-Fall. Es beseitigt **nicht** das allgemeine
Risiko aus Abschnitt 2 — es entfernt nur die spezifische, große Quelle von
Fehlalarmen, die durch das Einbeziehen irrelevanter `MGEF`-Datensätze
entstand. Zwei *unterschiedliche*, von Zutaten referenzierte Effekte (oder
zwei unterschiedliche Zutaten), die zufällig einen Namen teilen, sind
immer noch möglich, nur viel seltener.

## 4. Aktuelle Abhilfe: keine automatische — `form_id` manuell abgleichen

Es gibt keinen Code, der erkennt "zwei unterschiedliche, unabhängige
FormIDs lösten auf denselben Namen auf" und das markiert — ein verworfenes
Duplikat bleibt stillschweigend, genau wie vor dieser Refaktorierung. Da
`Ingredient`/`Effect` jetzt `source_file` und `form_id` tragen (siehe
[DATA_SOURCES.de.md §1](../data-sources/DATA_SOURCES.de.md#1-zutaten)), hat
sich die praktische Vorgehensweise geändert, um eine vermutete Kollision zu
untersuchen: die `form_id` des Eintrags in
`cache/game_data/ingredients.json`/`effects.json` nachschlagen und mit
xEdit oder der eigenen Dokumentation des Mods abgleichen — stimmt die
FormID nicht mit dem überein, was für diesen Namen erwartet wurde, hat der
Datensatz eines anderen Plugins die Namenskollision gewonnen. Die
betroffenen Plugins in Mod Organizer 2 (oder in der nativen `Plugins.txt`)
neu zu ordnen und mit `--refresh` neu auszuführen, ändert, welcher
Datensatz den Namen gewinnt, als Workaround — dasselbe wie zuvor, aber jetzt
über `form_id` überprüfbar statt nur aus fehlenden Einträgen erschlossen.
