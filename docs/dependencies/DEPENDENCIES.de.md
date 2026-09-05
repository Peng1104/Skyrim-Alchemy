# Abhängigkeiten für das binäre Lesen

Dieses Dokument beschreibt ein von diesem Projekt wissentlich
eingegangenes Risiko. Die beiden Drittanbieter-Bibliotheken, auf die
sich der Spieldaten-Scan zum Lesen von Skyrims eigenen binären
Formaten stützt, sind beide relativ neu und wenig genutzt, und dieses
Dokument hält fest, was über sie verifiziert wurde, und was passiert,
wenn ein Plugin oder Archiv auf eine Formatvariante trifft, die sie
nicht abdecken.

## 1. Was jede Bibliothek tut, und warum das Risiko besteht

[`sse-plugin-interface`](https://github.com/cutleast/sse-plugin-interface)
parst die Plugin-Dateien selbst: Datensatz- und Sub-Datensatz-Struktur,
Header, Master-Listen, FormIDs.
[`sse-bsa`](https://github.com/cutleast/sse-bsa) parst die gepackten
Ressourcenarchive des Spiels, verwendet, um lokalisierte Textdateien zu
extrahieren (siehe Abschnitt 1.2 des
[Datenquellen](../data-sources/DATA_SOURCES.md)-Dokuments).

Beide sind reine Python-Implementierungen von Bethesdas eigenen,
undokumentierten, per Reverse Engineering erschlossenen binären
Formaten, gepflegt vom selben Autor,
[cutleast](https://github.com/cutleast), als kleine Open-Source-Projekte
mit relativ wenigen Beiträgen im Vergleich zu einer weit verbreiteten
Allzweckbibliothek. Das ist ein echtes Risiko für ein Projekt, das sich
jetzt für seine einzige Quelle von Zutaten- und Effektdaten auf sie
verlässt (siehe das
[Datenquellen](../data-sources/DATA_SOURCES.md)-Dokument). Eine
Formatvariante, die keine der beiden Bibliotheken behandelt, könnte
stillschweigend falsche oder fehlende Daten erzeugen statt eines
sauberen Fehlers, wenn nichts anderes dagegen absicherte.

## 2. Was tatsächlich verifiziert wurde

Das wurde nicht einfach geglaubt. Beide Bibliotheken wurden End-to-End
gegen die zwei in der Praxis wichtigsten realen Fälle getestet, auf
einer echten, stark modifizierten Installation mit rund 170 aktiven
Plugins.

| | Plugin-Typ | Kodierung des Anzeigetexts | Getestete Bibliothek |
| :--- | :--- | :--- | :--- |
| Fall 1 | Kleiner, inoffizieller, nicht lokalisierter Mod (eine Hobby-Kreation, keine offizielle Bethesda- oder Creation-Club-Veröffentlichung) | Literaler Text, direkt im Datensatz gespeichert, kein Archiv beteiligt | Nur die Plugin-Parsing-Bibliothek |
| Fall 2 | Offizielle, lokalisierte Creation-Club-Veröffentlichung | Numerische lokalisierte String-Id, aufgelöst über das eigene gepackte Archiv des Plugins | Plugin-Parsing- und Archiv-Parsing-Bibliothek zusammen |

Beide Fälle stimmten exakt mit den Erwartungen überein, verifiziert
gegen bekannte Zutatennamen und Effektwerte, und im
Creation-Club-Fall gegenkontrolliert gegen die eigene FormID-Ausgabe
eines Ingame-Konsolenbefehls. Zusammen mit einem vollständigen Scan von
218 Zutaten und 65 Effekten über jedes Plugin in einer echten
Ladereihenfolge, der bekannten Referenzwerten entspricht, Vanilla, DLC,
und mehreren weiteren einzeln stichprobenartig geprüften Creation-Club-
und Mod-Zutaten, deckt das die zwei strukturell unterschiedlichen
Arten ab, wie Anzeigetext kodiert sein kann, was die eigentliche
Risikoachse für diese Bibliotheken ist, nicht die Politur oder Größe
irgendeines bestimmten Plugins.

## 3. Was passiert, wenn eine Variante nicht abgedeckt ist

Es wurde nichts beobachtet, das diese Bibliotheken nicht parsen können.
Der Scanner ist absichtlich so gebaut, dass er, falls das je doch
vorkommt, für diese eine Zutat laut fehlschlägt, nie stillschweigend.

| Fehler | Verhalten |
| :--- | :--- |
| Der Anzeigename eines Datensatzes kann nicht aufgelöst werden (ein fehlender String-Eintrag, ein nicht parsebares Archiv, oder jede andere Ursache) | Fällt auf dasselbe leere Ergebnis zurück, nie eine falsche Vermutung. Die Zutat wird protokolliert, mit ihrer eigenen internen Kennung und dem definierenden Plugin, damit sie nachvollziehbar ist, und übersprungen. Sie gelangt nie mit einem falschen oder leeren Namen in die endgültige Zutatendatenbank. |
| Ein Plugin lässt sich überhaupt nicht laden (eine wirklich beschädigte oder nicht unterstützte Datei) | Protokolliert, und dieses gesamte Plugin wird übersprungen, dasselbe Prinzip auf gröberer Ebene. |

In beiden Fällen läuft der Scan für jedes andere Plugin und jede andere
Zutat weiter. Ein nicht parsebarer Datensatz oder ein nicht
parsebares Plugin bricht nicht den gesamten Lauf ab, und der Fehler ist
immer in der Konsolen- oder Log-Ausgabe sichtbar, nie verschluckt.

## 4. Versionsfixierung

Die Abhängigkeitsliste des Projekts deklariert derzeit offene
Untergrenzen für beide Bibliotheken, und die Lock-Datei löst diese auf
exakte Versionen auf, sodass eine normale Installation bereits
reproduzierbar ist. Die offene Grenze selbst verhindert jedoch nicht,
dass ein zukünftiges Abhängigkeits-Upgrade stillschweigend eine neuere
Hauptversion einer der beiden Bibliotheken zieht, ohne eine bewusste
Entscheidung dazu. Für die meisten Abhängigkeiten ist das unproblematisch,
aber für zwei Bibliotheken, für die dieses Projekt keinen Fallback hat,
es gibt kein Wiki mehr, auf das man zurückgreifen könnte, und die von
kleinen, wenig aktiven Projekten gepflegt werden, ist ein ungeprüfter
Hauptversionssprung genau die Art von Änderung, die eine bewusste
Entscheidung erfordern sollte, statt als Nebeneffekt der
Aktualisierung eines unabhängigen Pakets zu geschehen. Diese beiden
beim nächsten Anfassen auf eine exakte Version zu fixieren, würde
sicherstellen, dass ein Versionssprung für genau diese beiden immer
über eine explizite, geprüfte Änderung erfolgt.
