🌐 [English](EFFECTS_CACHE.md) · [Português](EFFECTS_CACHE.pt.md) · [Deutsch](EFFECTS_CACHE.de.md)

# Effekt-Cache

Dieses Dokument beschreibt den Cache auf der Festplatte, der die
endgültige Magieeffekt-Datenbank enthält, unter
`cache/game_data/effects.json`, aufgebaut im selben Durchlauf wie der
[Zutaten-Cache](../ingredients/INGREDIENTS_CACHE.md) und immer zusammen mit ihm
geschrieben. Sie ist kein vollständiger Abzug jedes Magieeffekts, der
in jedem aktiven Plugin existiert. Das Spiel definiert viele Tausend
Effekte ohne Bezug zur Alchemie: Zauber, Verzauberungen, reine
Quest-Fähigkeiten, und so weiter. Ein Eintrag landet nur dann hier,
wenn ihn mindestens eine Zutat im
[Zutaten-Cache](../ingredients/INGREDIENTS_CACHE.md) tatsächlich erzeugt. Abschnitt 3
erklärt, warum diese Filterung wichtig ist.

## 1. Struktur

Ein JSON-Objekt, das den Anzeigenamen jedes Effekts auf seine Daten
abbildet.

```jsonc
{
  "Restore Stamina": {
    "name": "Restore Stamina",
    "cost": 0.6000000238418579,
    "harmful": false,
    "source_file": "unofficial skyrim special edition patch.esp",
    "form_id": "0003EB16"
  }
  // ein Eintrag pro Effekt, der tatsächlich von einer Zutat erzeugt wird
}
```

(Echter Auszug.)

| Feld | Gelesen aus | Bedeutung |
| :--- | :--- | :--- |
| `name` | `FULL`-Sub-Datensatz | Der Anzeigename des Effekts, auch der Schlüssel, unter dem er gespeichert ist. Zwei echt nicht verwandte Effekte, ohne Override-Beziehung zwischen ihnen, könnten im Prinzip genau denselben Anzeigetext teilen und hier kollidieren, wobei einer den anderen stillschweigend überschreibt. Das ist selten, aber nicht hypothetisch: siehe Abschnitt 3 für einen echten Fall. |
| `cost` | `DATA`-Sub-Datensatz, Bytes 4-7 (32-Bit-Float) | Die eigenen Basiskosten des Effekts, eine echte Eigenschaft des Effekts, unabhängig von irgendeiner bestimmten Zutat, verwendet bei der Berechnung, wie viel ein Trank mit diesem Effekt wert ist. Genau so gehalten, wie diese 4 Bytes dekodieren, ohne Rundung. Siehe Abschnitt 2 dafür, warum das wie `0.6000000238418579` statt eines saubereren `0.6` aussieht. |
| `harmful` | `DATA`-Sub-Datensatz, Bytes 0-3 (32-Bit-Flags), Bit `0x01` (Hostile) oder `0x04` (Detrimental) | Ob das Spiel dies als schädlichen, giftartigen Effekt einstuft. Wahr, wenn eines der beiden Bits gesetzt ist. Siehe Abschnitt 2 für den Grund dieser spezifischen Bit-Kombination. |
| `source_file` | Welcher Magieeffekt-Datensatz die Override-Auflösung gewonnen hat | Welche Version dieses Effekts tatsächlich in Kraft ist, nach derselben Override-Regel wie das `source_file` einer Zutat: nicht notwendigerweise wer den Effekt zuerst hinzugefügt hat, sondern wessen Version gerade gewinnt. Nur informativ. |
| `form_id` | Die eigene FormID dieses gewinnenden Datensatzes, unverändert | Die eigene Kennung des gewinnenden Plugins für den Effekt. Nur informativ. |

Es gibt hier absichtlich kein Magnitude- oder Duration-Feld, und wird
es auch nie geben. Diese beschreiben, wie stark eine bestimmte Zutat
diesen Effekt erzeugt, und das variiert von Zutat zu Zutat, wie in der
`effects`-Liste des
[Zutaten-Cache](../ingredients/INGREDIENTS_CACHE.md)-Dokuments beschrieben. Keine
gemeinsame Basis-Magnitude oder -Duration pro Effekt existiert
irgendwo in den eigenen Daten des Spiels.

## 2. Woher cost und harmful tatsächlich kommen

Keines von beiden ist etwas, das dieses Projekt entscheidet oder
berechnet. Beide werden so gelesen, wie sie sind, aus Bytes, die
Bethesdas eigenes Plugin-Format bereits definiert, innerhalb des
`DATA`-Blocks jedes Magieeffekt-Datensatzes: ein 32-Bit-Flags-Feld bei
Byte-Offset 0, und Basiskosten als 32-Bit-Float bei Byte-Offset 4.

`harmful` wird aus zwei einzelnen Bits dieses Flags-Werts abgeleitet:
Bit `0x01` (Hostile) und Bit `0x04` (Detrimental). Es ist wahr, wenn
eines der beiden Bits gesetzt ist. Diese spezifische Regel, Hostile
oder Detrimental statt nur Detrimental allein, wurde gewählt, indem sie
gegen jeden der 205 Alchemie-Effekte geprüft wurde, die ein Wiki
unabhängig als schädlich oder wohltätig dokumentiert. Detrimental
allein widersprach dieser Referenz bei 2 davon, Paralysis und Fear, die
das Spiel selbst als Hostile, aber nicht als Detrimental markiert,
während Hostile oder Detrimental bei allen 205 ohne Abweichungen
übereinstimmte. Beide Bit-Positionen, und die obigen Byte-Offsets,
stammen aus Bethesdas eigenem Datensatz-Layout, nicht aus irgendetwas,
das dieses Projekt erfunden hat.

Jeder andere Float, den dieses Projekt aus einem Plugin liest, dieses
`cost` eingeschlossen, und die eigene Magnitude und Duration jeder
Zutat, wird genau so gehalten, wie dieser 4-Byte-Float dekodiert, ohne
angewendete Rundung. Das ist, warum ein Wert wie
`0.6000000238418579` erscheint statt eines saubereren `0.6`. Das ist
keine Beschädigung: es ist das, was diese 4 Bytes tatsächlich
dekodieren, da `0.3` keine exakte binäre Gleitkommadarstellung hat,
sodass die eigenen Daten des Spiels von vornherein nie ein perfekt
sauberes `0.6` gespeichert haben. Es für die Serialisierung in einen
breiteren Float umzuwandeln, macht diese bereits vorhandene Ungenauigkeit
nur sichtbar, statt sie hinter einem gerundeten Anzeigewert zu
verstecken.

## 3. Wie sie befüllt wird

Aufgebaut im selben Schritt, der den
[Zutaten-Cache](../ingredients/INGREDIENTS_CACHE.md) aufbaut. Beim Auflösen der
Effekte jeder Zutat nach Name, beim Abgleichen des Verweises jeder
Zutat gegen den Effekt, auf den sie sich tatsächlich bezieht, wird auch
jeder Effekt, der auf diese Weise erfolgreich abgeglichen wird, hier
erfasst. Diese Datei enthält am Ende genau die Effekte, die
tatsächlich von mindestens einer Zutat aus erreichbar sind, und sonst
nichts.

Diese Filterung ist beabsichtigt, nicht beiläufig. Jeden Magieeffekt,
den ein Plugin definiert, bedingungslos einzuschließen, würde auch
Effekte hereinziehen, die völlig ohne Bezug zur Alchemie sind, von
denen manche zufällig Anzeigetext mit einem echten Alchemie-Effekt
teilen können. Das ist in der Praxis vorgekommen: ein reiner
Quest-Effekt aus einer DLC löste einmal zum exakt gleichen Namen auf
wie ein echter Alchemie-Effekt, aber mit anderen Kosten, was die Daten
dieses Alchemie-Effekts stillschweigend beschädigt hätte, wenn jeder
Effekt bedingungslos eingeschlossen worden wäre. Diese Datei auf das zu
beschränken, was Zutaten tatsächlich verwenden, vermeidet diese
spezifische Kollisionsklasse, wobei der engere Fall aus Abschnitt 1,
zwei Effekte, die beide tatsächlich von irgendeiner Zutat verwendet
werden und trotzdem einen Namen teilen, weiterhin möglich bleibt.

Diese Datei und der [Zutaten-Cache](../ingredients/INGREDIENTS_CACHE.md) werden immer
zusammen geschrieben, im selben Durchlauf. Siehe Abschnitt 3.1 dieses
Dokuments dafür, wann genau ein Neuschreiben passiert, im Gegensatz
dazu, wann das Ergebnis eines vorherigen Scans unverändert
wiederverwendet wird.

## 4. Wer sie liest

Zusammen mit dem [Zutaten-Cache](../ingredients/INGREDIENTS_CACHE.md) beim Start
geladen, aber nachsichtiger behandelt, wenn sie fehlt. Eine fehlende
Zutatendatenbank ist ein harter Fehler, da nichts in der Anwendung ohne
eine funktionieren kann, während eine fehlende Effektdatenbank einfach
als "noch keine Effekte bekannt" behandelt wird, und die Anwendung
weiter startet. In der Praxis werden die beiden Dateien immer
zusammen geschrieben, sodass das hauptsächlich für einen teilweise
eingerichteten oder manuell veränderten Cache-Ordner relevant ist,
nicht für den normalen Gebrauch.
