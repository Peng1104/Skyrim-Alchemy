# Zutaten- und Effektdaten (binäres Lesen der Plugins)

Dieses Dokument beschreibt, woher die Zutaten- und Effektdaten des
Projekts stammen: die eigenen binären Daten jedes aktiven
Skyrim-Plugins, direkt gelesen. Kein Wiki, kein Scraping, keine
HTTP-Anfragen.

Nur das Kommandozeilen-Tool scannt die Spielinstallation und schreibt
den Cache. Es ist der einzige Prozess mit einem lokalen Pfad zum Spiel.
Der Optimierer und die API lesen nur den Cache. Siehe Abschnitt 3 dafür,
was passiert, wenn dieser Cache fehlt.

## 1. Zutaten

Jede Zutat in der aktiven Ladereihenfolge wird Teil der Zutatendatenbank,
aufgebaut aus dem eigenen binären Datensatz.

| Eigenschaft | Kommt aus | Anmerkungen |
| :--- | :--- | :--- |
| Name | Dem Anzeigetext-Feld des Datensatzes | Entweder literaler Text, oder eine lokalisierte String-Id, aufgelöst gegen die eigenen gepackten String-Daten des definierenden Plugins; siehe Abschnitt 1.2 |
| Effekte | Bis zu 4 Eintragspaare im Datensatz, eines pro Effekt | Jedes Paar ist eine 12-Byte-Struktur mit der Magnitude des Effekts, einem ungenutzten Flächenwert und einer Duration, genau wie diese Zutat sie produziert. Es gibt keine gemeinsame Basis, auf die sich das bezieht; siehe Abschnitt 1 des [Berechnungsdokuments](../calculation/CALCULATION.md) |
| Quell-Plugin und FormID | Die eigene Identität des Datensatzes nach der Override-Auflösung | Identifiziert den maßgeblichen, nach Overrides aufgelösten Datensatz der Zutat; siehe Abschnitt 1.1 |

Zum Zeitpunkt dieser Erstellung erzeugt ein vollständiger Scan einer
echten, modifizierten Installation 218 Zutaten. Das ist nirgends fest
codiert: es ist das, was die aktive Ladereihenfolge tatsächlich enthält,
und es ist die praktische Obergrenze dafür, wie viele unterschiedliche
Zutatentypen der Optimierer je sehen könnte, was für dessen
Worst-Case-Kombinationsanzahl wichtig ist; siehe Abschnitt 8.1 des
[Berechnungsdokuments](../calculation/CALCULATION.md).

### 1.1 Override-Auflösung

Skyrims Plugin-Format lässt ein späteres Plugin in der Ladereihenfolge
den Datensatz eines früheren Plugins neu definieren, indem es dessen
FormID wiederverwendet: ein echter Override, kein neuer Gegenstand.

1. Die eigenen Zutaten- und Effektdatensätze jedes Plugins werden zuerst
   isoliert in einen Per-Plugin-Snapshot geparst; siehe das
   [Plugin-Cache](../cache/plugin/PLUGIN_CACHE.md)-Dokument dafür, warum das
   pro Plugin cachefähig ist.
2. Die gesamte Ladereihenfolge wird dann einmal durchlaufen, zuerst die
   Vanilla-Master, dann Creation-Club-Inhalte (siehe Abschnitt 1.3), dann
   die eigene aktive Plugin-Liste des Benutzers, in dieser Reihenfolge,
   und jeder Datensatz wird nach seiner kanonischen Identität indiziert.
3. Ein späteres Plugin in der Ladereihenfolge überschreibt einfach den
   Indexeintrag für eine FormID, die ein früheres Plugin bereits
   definiert hat, sodass der Index am Ende nur die endgültige,
   maßgebliche Version jedes Datensatzes enthält, genau wie die Spiel-
   Engine selbst Overrides auflöst.

Siehe das [Spieldaten](../game_data/GAME_DATA.md)-Dokument für die
vollständige Mechanik, einschließlich des Namenskollisionsrisikos, das
daraus folgt.

Das erfasste Quell-Plugin und die FormID einer Zutat oder eines Effekts
spiegeln diese maßgebliche Version wider, nicht notwendigerweise das
Plugin, das den Gegenstand ursprünglich eingeführt hat. Eine Zutat,
die ursprünglich von einem Creation-Club-Plugin hinzugefügt, seither
aber von einem weit verbreiteten Community-Kompatibilitätspatch
gepatcht wurde, meldet diesen Patch als ihre Quelle.

### 1.2 Lokalisierte Strings und der DLC-Archiv-Fallback

Das Anzeigetext-Feld eines Datensatzes kann eine von zwei Formen haben:

| Form | Wo der Text lebt |
| :--- | :--- |
| Literaler Text | Direkt im Datensatz |
| Numerische lokalisierte String-Id | Eine String-Datei innerhalb des eigenen gepackten Archivs des definierenden Plugins |

Mehrere der eigenen offiziellen Add-ons von Skyrim Special Edition
werden ohne eigenes Archiv ausgeliefert. Deren Strings sind stattdessen
im eigenen Interface-Archiv des Basisspiels gebündelt, unter dem eigenen
Datei-Stamm jedes Add-ons. Das Auflösen der Strings eines Plugins fällt
auf die eigenen Archive des Basisspiels zurück, wann immer die eigene
Stamm-basierte Suche eines Plugins nichts findet, was das abdeckt, ohne
den Dateinamen irgendeines bestimmten Add-ons fest zu codieren.

### 1.3 Creation Club und seine eigene Ladeliste

Creation-Club-Inhalte werden nicht in der eigenen aktiven Plugin-Liste
des Benutzers gelistet, wie es bei einem gewöhnlichen Mod der Fall ist.
Die Spiel-Engine lädt automatisch, was in einer separaten
Klartextdatei im eigenen Installationsstammverzeichnis des Spiels
gelistet ist, ein Plugin pro Zeile, kein Mod-Manager-Profil,
unabhängig von der eigenen aktiven Plugin-Liste des Benutzers. Ein
populärer Mod-Manager listet Creation-Club-Inhalte nur als
Prioritätsordnungs-Eintrag, unabhängig davon, ob das Plugin tatsächlich
lädt, sodass diese separate Datei die einzig verlässliche Quelle dafür
ist, welche Creation-Club-Inhalte tatsächlich aktiv sind.

Diese separate Datei, und die Vanilla-Masterliste, benennen Plugins mit
der eigenen gemischten Groß-/Kleinschreibung des Herausgebers, die
nicht notwendigerweise mit dem tatsächlichen Dateinamen auf der
Festplatte auf einem Groß-/Kleinschreibung-sensitiven Dateisystem
übereinstimmt; eine mit Windows geteilte und unter Linux eingehängte
Steam-Bibliothek ist häufig eines davon.

| | Verhalten |
| :--- | :--- |
| Naive Existenzprüfung gegen die veröffentlichte Schreibweise | Lässt das Plugin stillschweigend aus dem gesamten Scan fallen, wenn die beiden voneinander abweichen, zusammen mit allen seinen Zutaten, die nicht von einem anderen aktiven Plugin überschrieben wurden |
| Aktuelle Handhabung | Baut einmal pro Lauf eine Abbildung von kleingeschriebenem zu tatsächlichem Dateinamen auf der Festplatte auf, und löst jeden Plugin-Namen aus jeder dieser Listen dagegen auf, bevor er zur Ladereihenfolge hinzugefügt wird |

Das öffnet Dateien immer mit ihrer echten, exakten Schreibweise,
unabhängig davon, welche Schreibweise die Quellliste verwendet hat.

### 1.4 Namenskollisionsrisiko

Zwei nicht verwandte Datensätze, unterschiedliche FormIDs, keine
Override-Beziehung, können immer noch zufällig zum selben Anzeigenamen
auflösen. Das ist ein echtes, wenn auch seltenes Risiko, das dem
Indizieren der endgültigen Datenbank nach Name statt nach FormID
innewohnt. Siehe das
[Spieldaten](../game_data/GAME_DATA.md)-Dokument für die vollständige
Erklärung.

## 2. Effekte

Ein Effekt wird nur dann zur Effektdatenbank hinzugefügt, wenn er
tatsächlich von irgendeiner Zutat referenziert wird. Das Spiel definiert
viele Tausend Effektdatensätze ohne Bezug zur Alchemie, Verzauberungen,
Quest- und Skript-Fähigkeiten und so weiter, und jeden davon
bedingungslos einzuschließen würde riskieren, dass ein irrelevanter
Datensatz stillschweigend einen echten Alchemie-Effekt überschreibt, der
zufällig denselben Anzeigetext teilt; siehe Abschnitt 2 des
[Spieldaten](../game_data/GAME_DATA.md)-Dokuments.

| Eigenschaft | Kommt aus |
| :--- | :--- |
| Basiskosten | Ein 32-Bit-Float im Datensatz |
| Harmful | Ob die Harmful-Flag-Bits des Datensatzes gesetzt sind, eine Regel, die mit 205 bekannten Effekten ohne Abweichungen übereinstimmt |

Der Kostenwert, und jeder andere aus einem Plugin gelesene Float,
einschließlich der eigenen Magnitude und Duration jeder Zutat, wird
exakt so gespeichert, wie der eigene binäre Wert des Spiels dekodiert,
absichtlich nicht gerundet. Ein Wert wie `0.30000001192092896` für
Kosten, die ein Wiki selbst als `0.3` dokumentiert, ist keine
Beschädigung. `0.3` hat keine exakte binäre Gleitkommadarstellung, also
dekodieren die eigenen binären Bytes des Spiels auf denselben,
nächstliegenden darstellbaren Wert. Das Ziel ist, exakt den Wert zu
behalten, den das Plugin selbst speichert, nicht eine hübschere,
gerundete Annäherung davon.

Es gibt überhaupt kein Magnitude- oder Duration-Feld bei einem
Effekt-Datensatz. Siehe Abschnitt 2.1 des
[Berechnungsdokuments](../calculation/CALCULATION.md) dafür, wie sich
Kosten und die Harmful-Flag mit der eigenen Magnitude und Duration jeder
Zutat kombinieren.

## 3. Cache

Der Scan schreibt drei Arten von Dateien unter einem eigenen
Cache-Verzeichnis:

| Dateien | Inhalt | Dokument |
| :--- | :--- | :--- |
| Eine kleine Datei pro Plugin | Die eigenen rohen Scan-Ergebnisse dieses Plugins | [Plugin-Cache](../cache/plugin/PLUGIN_CACHE.md) |
| `ingredients.json` | Die zusammengeführte, override-aufgelöste Zutatendatenbank | [Zutaten-Cache](../cache/ingredients/INGREDIENTS_CACHE.md) |
| `effects.json` | Die zusammengeführte, override-aufgelöste Effektdatenbank | [Effekt-Cache](../cache/effects/EFFECTS_CACHE.md) |

Das Scannen ist inkrementell pro Plugin, nicht alles oder nichts. Ein
Plugin, dessen eigene Bytes sich seit dem letzten Scan nicht geändert
haben, verwendet seine zwischengespeicherten Daten unverändert weiter,
und nur tatsächlich geänderte Plugins werden erneut verarbeitet. Das
macht in der Praxis einen Unterschied, bei einer echten Installation
mit rund 100 aktiven Plugins:

| Scan | Zeit |
| :--- | :--- |
| Vollständig, jedes Plugin neu verarbeitet | Etwa 30 Sekunden |
| Erneuter Scan nach Berühren eines einzelnen Plugins | Etwa 0,2 Sekunden |

Ein Unterschied von etwa 150x, genau für den häufigen Fall, ein oder
zwei Mods auf einmal hinzuzufügen, zu aktualisieren oder zu entfernen.

Nur das Kommandozeilen-Tool löst je einen Scan aus. Wenn der Cache noch
nicht befüllt wurde, füllen Sie ihn zuerst, indem Sie dieses Tool mit
seiner Refresh-Option gegen eine lokale Skyrim-Installation ausführen:

```bash
uv run python cli.py --refresh
```

Um Änderungen nach dem Installieren, Entfernen oder Neuordnen von
Plugins zu übernehmen, erneut mit derselben Option ausführen. Es gibt
keinen separaten Befehl zum Leeren des Caches. Ein unverändertes Plugin
wird nie neu verarbeitet, also ist ein Refresh auch bei vielen
installierten Plugins günstig. Die eigentliche Wirkung der
Refresh-Option ist, jeden zwischengespeicherten Snapshot zu ignorieren
und jedes Plugin von Grund auf neu zu verarbeiten, nützlich, wenn der
Cache selbst je verdächtigt wird, veraltet oder beschädigt zu sein,
obwohl eine einzelne fehlerhafte zwischengespeicherte Datei eines
Plugins bereits von selbst elegant behandelt wird, ohne ein
vollständiges Refresh zu benötigen.
