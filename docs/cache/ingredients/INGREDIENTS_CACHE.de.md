🌐 [English](INGREDIENTS_CACHE.md) · [Português](INGREDIENTS_CACHE.pt.md) · [Deutsch](INGREDIENTS_CACHE.de.md)

# Zutaten-Cache

Dieses Dokument beschreibt den Cache auf der Festplatte, der die
vollständige, endgültige Zutatendatenbank enthält, unter
`cache/game_data/ingredients.json`: jede Zutat aus jedem aktiven
Plugin, bereits auf die eine Version aufgelöst, die tatsächlich zählt
(Abschnitt 2 erklärt, was "aufgelöst" hier bedeutet). Das ist die
Datei, die der Rest der Anwendung liest. Der Optimierer, die API,
alles, was auf den Spieldaten-Scan folgt, geht über diese Datei, nie
über die rohen Pro-Plugin-Daten, aus denen sie aufgebaut ist (siehe das
[Plugin-Cache](../plugin/PLUGIN_CACHE.md)-Dokument).

Zum Zeitpunkt dieser Erstellung erzeugt ein vollständiger Scan einer
echten, modifizierten Installation 218 Zutaten, keine feste Zahl, nur
das, was die aktiven Plugins tatsächlich enthalten.

## 1. Struktur

Ein JSON-Objekt, das den Anzeigenamen jeder Zutat auf ihre Daten
abbildet.

```jsonc
{
  "Silverside Perch": {
    "name": "Silverside Perch",
    "effects": [
      {
        "name": "Restore Stamina",
        "magnitude": 5.0,
        "duration": 0.0
      },
      {
        "name": "Damage Stamina Regen",
        "magnitude": 100.0,
        "duration": 5.0
      }
      // bis zu 4 Effekte insgesamt
    ],
    "source_file": "Skyrim.esm",
    "form_id": "00106E1C"
  }
  // ein Eintrag pro Zutat
}
```

(Echter, gekürzter Auszug.)

| Feld | Bedeutung |
| :--- | :--- |
| `name` | Der Anzeigename der Zutat, auch der Schlüssel, unter dem sie gespeichert ist. |
| `effects` | Bis zu 4 Effekte, die diese Zutat erzeugt. `magnitude` und `duration` jedes einzelnen sind die eigene, echte Stärke dieser spezifischen Zutat für diesen Effekt, nie gerundet und nie relativ zu irgendeiner gemeinsamen Basis: keine solche Basis existiert in den eigenen Daten des Spiels, sodass zwei Zutaten für denselben Effekt völlig unterschiedliche Zahlen auflisten können. Der `name` hier ist der aufgelöste Anzeigename des Effekts, bereits gegen das Plugin abgeglichen, das diesen Effekt definiert. |
| `source_file` | Welche Version dieser Zutat tatsächlich in Kraft ist, nicht notwendigerweise das Plugin, das sie ursprünglich eingeführt hat. Überschreibt ein späterer Mod, oder ein Kompatibilitätspatch, die Zutat eines früheren Plugins, nennt dies stattdessen dieses spätere Plugin. Nur informativ: nichts in der Berechnung verwendet dieses Feld, es existiert, um nachzuvollziehen, woher die Zahlen einer Zutat kommen. |
| `form_id` | Die eigene Kennung des gewinnenden Plugins für die Zutat. Ebenfalls nur informativ. |

## 2. Identität hinter den Kulissen

Diese Datei selbst legt die zugrunde liegende Plugin-Identität der
Zutat nicht offen: sie indiziert stattdessen alles nach Anzeigename, da
das ist, wogegen der Rest der Anwendung abgleichen muss (eine aus
einem Screenshot erkannte Zutat wird zum Beispiel nach ihrem Namen
abgeglichen). Intern wird jede Zutat und jeder Effekt, bevor diese
Datei aufgebaut wird, durch eine präzisere Identität verfolgt: welches
Plugin sie tatsächlich definiert, plus eine numerische Id, die stabil
bleibt, unabhängig davon, welches andere Plugin gerade darauf verweist
(siehe Abschnitt 2.1 des
[Plugin-Cache](../plugin/PLUGIN_CACHE.md)-Dokuments). Diese präzise Identität ist
es, die es einer von fünf verschiedenen Mods überschriebenen Zutat
erlaubt, immer noch zu genau einem Eintrag hier aufzulösen, demjenigen,
der zu welchem dieser Mods auch immer zuletzt lädt, statt zu fünf
separaten, widersprüchlichen Einträgen.

Das Endergebnis nach Name statt nach dieser zugrunde liegenden
Identität zu indizieren, bringt einen echten, wenn auch seltenen,
Nachteil mit sich. Zwei echt nicht verwandte Zutaten oder Effekte, ohne
Override-Beziehung zwischen ihnen, könnten im Prinzip genau denselben
Anzeigetext teilen und hier kollidieren, wobei einer den anderen
stillschweigend überschreibt. Das ist kein hypothetischer Fall: es
wurde in der Praxis beobachtet, immer mit einem Effekt, der für etwas
völlig Alchemie-fremdes definiert war, zum Beispiel ein Quest-Skript,
das zufällig einen Namen wiederverwendete, der bereits von einem
echten Alchemie-Effekt verwendet wurde.

## 3. Wie sie befüllt wird

Aufgebaut, sobald die eigenen Pro-Plugin-Daten jedes aktiven Plugins
verfügbar sind, frisch gescannt oder von zuvor wiederverwendet. Zwei
Dinge passieren, rein durch das Kombinieren bereits vorhandener Daten
auf der Festplatte. Keine Plugin-Datei wird in dieser Phase erneut
geöffnet.

Zuerst wird für jede Zutat und jeden Effekt ein Gewinner bestimmt.
Plugins werden in Ladereihenfolge durchlaufen, und immer wenn zwei
Plugins dieselbe Zutat oder denselben Effekt definieren oder
überschreiben, gewinnt das später ladende, genau wie das Spiel selbst
solche Konflikte auflöst. Was danach übrig bleibt, ist genau eine
Version jeder Zutat und jedes Effekts, diejenige, die tatsächlich im
Spiel ist.

Zweitens werden die Effekte jeder Zutat nach Name angehängt. Jede
gewinnende Zutat verweist in dieser Phase noch nur per Kennung auf ihre
Effekte. Jeder dieser Verweise wird gegen die gewinnenden Effekte aus
dem ersten Schritt nachgeschlagen, um den tatsächlichen Anzeigenamen
des Effekts einzutragen. Ein Verweis, der zu keinem bekannten Effekt
auflöst, weil sein definierendes Plugin zum Beispiel nie gescannt
wurde, wird einfach aus dieser Zutat entfernt, statt den gesamten Scan
scheitern zu lassen.

Diese Datei und der [Effect-Cache](../effects/EFFECTS_CACHE.md) werden immer
zusammen erzeugt und geschrieben, im selben Durchlauf. Es gibt kein
Szenario, in dem eine ohne die andere aktualisiert wird.

### 3.1 Wann sie tatsächlich neu geschrieben wird

Wenn sich seit dem vorherigen Scan nichts geändert hat, kein Datensatz
irgendeines aktiven Plugins sich geändert hat und die aktive
Plugin-Liste selbst dieselbe ist, wird dieser Schritt vollständig
übersprungen und die vorhandene Datei unverändert wiederverwendet. Jede
echte Änderung irgendwo, die Daten eines Plugins haben sich geändert
oder ein Mod wurde hinzugefügt oder entfernt, führt dazu, dass die
gesamte Datei von Grund auf neu aufgebaut wird. Es gibt kein
Teil-Update. Anders als der Pro-Plugin-Cache verfolgt diese Datei
nicht, welche einzelnen Zutaten sich geändert haben: sie wird immer
vollständig neu erzeugt, ausgehend vom jeweils aktuellen,
vollständigen Gesamtbild.

## 4. Wer sie liest

Das ist die Datenbank, die der Rest der Anwendung tatsächlich
verwendet, einmalig geladen, wenn der Optimierer startet. Es ist ein
reiner Lesevorgang: nichts, was diese Datei konsumiert, löst je selbst
einen Scan aus, sodass es auch an einem Ort ohne Zugriff auf die
tatsächliche Spielinstallation problemlos funktioniert. Existiert diese
Datei überhaupt noch nicht, wird das als harter Fehler behandelt, da
nichts in der Anwendung ohne eine Zutatendatenbank funktionieren kann,
sodass der Start laut fehlschlägt, statt still mit einer leeren
weiterzulaufen. Der begleitende
[Effect-Cache](../effects/EFFECTS_CACHE.md) wird nachsichtiger behandelt, wenn er
derjenige ist, der fehlt; siehe dieses Dokument für den Grund.
