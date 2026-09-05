# Spieldaten-Scan: Override-Auflösung und Namenskollisionsrisiko

Dieses Dokument beschreibt, wie der Spieldaten-Scan Overrides zwischen
Plugins auflöst, und eine spezifische, bekannte Einschränkung, die
daraus folgt. Zwei nicht verwandte Datensätze, die zufällig zum
selben Anzeigenamen auflösen, werden nicht beide behalten: die
endgültigen Wörterbücher, die dieses Projekt aufbaut, sind nach Name
indiziert, sodass eines von ihnen stillschweigend fallen gelassen wird.

## 1. Wie Overrides aufgelöst werden

Das Scannen erfolgt in zwei Phasen, vollständig beschrieben in den
Dokumenten [Plugin-Cache](../cache/plugin/PLUGIN_CACHE.md) und
[Zutaten-Cache](../cache/ingredients/INGREDIENTS_CACHE.md).

1. Die eigenen Zutaten- und Magieeffekt-Datensätze jedes Plugins werden
   zuerst isoliert geparst, wobei die kanonische Identität jedes
   Datensatzes berechnet wird: welches Plugin ihn tatsächlich
   definiert, und eine numerische Id, die stabil bleibt, unabhängig
   davon, welches andere Plugin darauf verweist. Dieser Schritt schaut
   nie auf ein anderes Plugin, was sein Ergebnis pro Plugin
   cachefähig macht.
2. Die gesamte aktive Ladereihenfolge wird dann einmal durchlaufen,
   zuerst die Vanilla-Master, dann Creation-Club-Inhalte, dann die
   eigene aktive Plugin-Liste des Benutzers, in genau dieser
   Reihenfolge, und jeder Datensatz eines Typs wird nach derselben
   kanonischen Identität indiziert. Wenn ein späteres Plugin in der
   Ladereihenfolge einen Datensatz mit derselben kanonischen Identität
   definiert wie einer, den ein früheres Plugin bereits indiziert hat,
   ein echter Override, bei dem das spätere Plugin das frühere als
   Master listet und dessen Datensatz wiederverwendet, ersetzt der
   spätere Eintrag den früheren im Index.

Sobald die gesamte Ladereihenfolge durchlaufen wurde, enthält jeder
Eintrag im Index nur seine endgültige, maßgebliche Version, genau wie
die Spiel-Engine selbst Overrides auflöst, und genau deshalb ist das
erfasste Quell-Plugin einer Zutat oder eines Effekts dasjenige, das
gerade gewinnt, nicht notwendigerweise dasjenige, das es ursprünglich
eingeführt hat.

Dieser Teil des Prozesses ist exakt. Es ist nicht möglich, dass ein
echter Override mit einem nicht verwandten neuen Datensatz verwechselt
wird, oder umgekehrt, weil die kanonische Identität aus derselben,
master-listen-relativen Nummerierung abgeleitet wird, die das Spiel
selbst verwendet, und sie bleibt exakt, egal wie viele Plugins aus dem
Cache wiederverwendet statt frisch geparst wurden, da die eigenen
kanonischen Identitäten eines zwischengespeicherten Plugins auf
dieselbe Weise berechnet wurden, als dessen Bytes zuletzt tatsächlich
gelesen wurden.

## 2. Wo Exaktheit endet: die endgültigen Wörterbücher sind nach Name indiziert

| Phase | Indiziert nach | Kollisionsfrei? |
| :--- | :--- | :--- |
| Der in Abschnitt 1 aufgebaute Index | Kanonische Identität | Ja |
| Die endgültigen Zutaten- und Effektdatenbanken | Aufgelöster Anzeigename | Nein |

Wenn zwei Datensätze mit echt unterschiedlichen, nicht verwandten
kanonischen Identitäten, ohne jede Override-Beziehung zwischeneinander,
zufällig zum identischen Anzeige-String auflösen, überlebt nur einer
von ihnen im Endergebnis. Der andere wird stillschweigend überschrieben.

Welcher gewinnt, wird rein durch die Verarbeitungsreihenfolge während
dieses Durchlaufs bestimmt, in der Praxis wer auch immer zuletzt
verarbeitet wird, nicht notwendigerweise wer semantisch korrekt oder
zuletzt überschrieben wurde. Es ist rein eine Namenskollision,
unabhängig vom in Abschnitt 1 beschriebenen Override-Mechanismus.

Die Effektdatenbank enthält nur jemals Magieeffekte, die tatsächlich von
irgendeiner Zutat referenziert werden, wodurch die große Mehrheit der
Magieeffekt-Datensätze im Spiel ausgeschlossen wird, Verzauberungen,
Quest-Fähigkeiten und so weiter, bevor sie je das nach Namen indizierte
Wörterbuch erreichen. Das reduziert die Anfälligkeit für das obige
Risiko erheblich, da die meisten Magieeffekte überhaupt nie zu
Kollisionskandidaten werden, beseitigt es aber nicht: zwei
unterschiedliche, von Zutaten referenzierte Effekte, oder zwei
unterschiedliche Zutaten, können immer noch zufällig einen Namen teilen.

## 3. Aktuelle Abhilfe: die FormID manuell querverweisen

Es gibt keine automatische Erkennung für zwei unterschiedliche, nicht
verwandte Identitäten, die zum selben Namen auflösen. Ein fallen
gelassenes Duplikat ist stillschweigend. Eine vermutete Kollision zu
untersuchen ist ein manueller, dreistufiger Prozess:

1. Die FormID des Eintrags im Zutaten- oder Effekt-Cache nachschlagen.
   Jede Zutat und jeder Effekt trägt sein gewinnendes Plugin und seine
   FormID; siehe Abschnitt 1 des
   [Datenquellen](../data-sources/DATA_SOURCES.md)-Dokuments.
2. Diese FormID gegen [xEdit](https://github.com/TES5Edit/TES5Edit)
   querverweisen, das Community-Tool zum Lesen und Bearbeiten von
   Plugins, das auch das tatsächliche Struct-Layout jedes
   Datensatztyps dokumentiert, oder gegen die eigene Dokumentation des
   Mods. Stimmt sie nicht mit dem überein, was für diesen Namen
   erwartet wurde, hat der Datensatz eines anderen Plugins die
   Namenskollision gewonnen.
3. Die betroffenen Plugins in der Ladereihenfolge neu ordnen und neu
   scannen. Das ändert, welcher Datensatz den Namen gewinnt, als
   Workaround, wie zuvor, aber jetzt über die FormID verifizierbar,
   statt nur aus einem fehlenden Eintrag abgeleitet zu werden.
