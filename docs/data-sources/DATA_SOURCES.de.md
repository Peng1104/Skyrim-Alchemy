# Zutaten- und Effektdaten (UESP-Scraping)

Dieses Dokument beschreibt, woher die Zutaten- und Effektdaten des Projekts
stammen und wie sie gescrapt und zwischengespeichert werden. Die
Referenzimplementierung befindet sich in `app/scraping/` (`_ingredients.py`,
`_effects.py`, `_effect_priorities.py`, `_http_cache.py`).

Es gibt zwei Datensätze, beide von [UESP](https://en.uesp.net/) (Unofficial
Elder Scrolls Pages) gescrapt und beide einmal pro `AlchemyOptimizer`-Instanz
(`app/optimizer/_engine.py`) über `get_ingredients_data()` und
`get_effects_data()` (`app/scraping/__init__.py`) geladen.

## 1. Zutaten

Quelle: [Skyrim:Ingredients](https://en.uesp.net/wiki/Skyrim:Ingredients).

`app/scraping/_ingredients.py` durchläuft mit BeautifulSoup jede
`table.wikitable.striped2_1` auf der Seite. Jede Zutat belegt **zwei
aufeinanderfolgende Tabellenzeilen**:

- Die erste Zeile (erkannt am `id`-Attribut) enthält den Namen der Zutat,
  entnommen aus dem Linktext der zweiten Zelle.
- Die direkt folgende Zeile hat bis zu 4 Zellen, eine pro Effekt, den die
  Zutat erzeugen kann. Der Linktext jeder Zelle ist der Effektname; zeigt
  die Zelle zusätzlich ein `Value`/`Magnitude`/`Duration`-Modifikator-Icon
  (ein nicht standardmäßiger Multiplikator für genau diese Kombination aus
  Zutat und Effekt), wird der dem Icon vorangehende `<b>`-Wert als Faktor
  dieses Modifikators erfasst (`get_modifiers`).

Daraus entsteht ein `dict[str, Ingredient]` — jede `Ingredient` hat einen
Namen und eine Liste von bis zu 4 `IngredientEffect`s, jede mit einer
optionalen `{Modifier: Faktor}`-Zuordnung.

### 1.1 Abdeckung von DLCs und Creation Club

Der Scraper filtert **nicht** nach Herkunft — er erfasst bedingungslos
jede Zeile in den Tabellen der Seite, egal ob die Zutat aus dem Basisspiel,
einem offiziellen DLC (Dawnguard, Hearthfire, Dragonborn) oder irgendeinem
Creation-Club-/Anniversary-Edition-Inhalt (Rare Curios, Fishing, Saints &
Seducers, The Cause, Plague of the Dead usw.) stammt. Nichts davon wird
herausgefiltert, und es gibt keine Einstellung, um es auszuschließen — steht
eine Zeile auf UESPs `Skyrim:Ingredients`-Seite, landet sie in
`ingredients_data`.

Das bedeutet auch, dass sich die resultierenden Daten nicht sauber nach
Herkunft trennen lassen: UESP markiert einige Zeilen mit einem kleinen
hochgestellten Abzeichen, das auf den DLC/das Creation verlinkt (`DG`,
`HF`, `DB`, oder ein generisches `CC`), aber viele Zutaten mit
Creation-Club-Herkunft (z. B. Mort Flesh aus Plague of the Dead) tragen gar
kein Abzeichen und sind in der Tabelle optisch nicht von Basisspiel-Zutaten
zu unterscheiden. Es gibt also keine zuverlässige Möglichkeit, aus den
gescrapten Daten abzuleiten, ob eine Zutat aus einem besessenen DLC stammt.

In der Praxis ist das harmlos: Besitzt man einen bestimmten DLC/ein
bestimmtes Creation nicht, tauchen dessen Zutaten im eigenen In-Game-
Inventar schlicht nie auf, sodass das OCR sie nie erkennt — sie liegen
einfach ungenutzt in `ingredients_data`.

## 2. Effekte

Quelle: [Skyrim:Alchemy Effects](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects).

`app/scraping/_effects.py` durchläuft jede `table.wikitable.sortable` auf
der Seite. Für jede Zeile werden der Effektname, die Basis-`cost`, die
Basis-`magnitude` und die Basis-`duration` aus festen Spaltenpositionen
gelesen, und `harmful` wird aus der CSS-Klasse der Zeile abgeleitet: UESP
markiert Zeilen schädlicher (giftartiger) Effekte mit `EffectNeg` und
wohltätige mit `EffectPos`.

### 2.1 Prioritäten pro Effekt

Eine Handvoll Effekte (*Damage Health* als bekanntestes Beispiel) hat
Zutaten mit nicht standardmäßiger Stärke/Dauer speziell für diesen Effekt —
siehe
[Abschnitt 2 des Berechnungsdokuments](../calculation/CALCULATION.de.md#2-prioritätsauflösung-zwischen-zutaten),
warum das wichtig ist. `app/scraping/_effect_priorities.py` ruft die eigene
Wiki-Seite jedes Effekts ab
(`https://en.uesp.net/wiki/Skyrim:<Effektname_Mit_Unterstrichen>`) und sucht
nach einer Tabelle mit den Spalten `Priority`/`Base Mag`/`Base Dur`. Ist sie
vorhanden, erhält jede Zutat mit nicht leerer `Priority` einen Eintrag in
`Effect.priority_overrides`, der ihren Namen auf
`(magnitude_ratio, duration_ratio)` abbildet — ihre Basisstärke/-dauer
geteilt durch die des Standardeffekts. Die meisten Effekte haben keine
solche Tabelle und enden ganz ohne Overrides.

Das läuft einmal pro Effekt, nachdem die Haupttabelle der Effekte
verarbeitet wurde — das Laden der Effektdaten kostet also einen
Seitenabruf für die Effekttabelle plus einen Abruf pro Effekt (alles im
Cache — siehe unten).

## 3. Cache

`download_data()` in `app/scraping/_http_cache.py` umschließt jeden Abruf:
bei der ersten Anfrage für eine URL wird die Seite heruntergeladen und das
rohe HTML unter `cache/pages/<Pfad-nach-der-Domain>.html` gespeichert (z. B.
`Ingredients.html`, `Alchemy_Effects.html`, `Damage_Health.html`); jeder
weitere Aufruf für dieselbe URL liest direkt aus dieser Datei, ohne
Netzwerkanfrage. Es gibt keine Aktualitätsprüfung oder Ablaufzeit — einmal
zwischengespeichert, wird eine Seite nie von selbst erneut heruntergeladen.

Um Änderungen auf UESP zu übernehmen, den Cache löschen und den nächsten
Lauf alles neu abrufen lassen:

```bash
rm -rf cache/pages/            # CLI - erzwingt beim nächsten Lauf ein frisches Scraping
```

```bash
curl -X DELETE http://localhost:8001/cache/pages   # API - derselbe Effekt
```

Beide entfernen jede zwischengespeicherte Seite ohne Unterscheidung
(Zutaten, die Effekttabelle und jede Prioritätsseite pro Effekt) — es gibt
keine Möglichkeit, nur eine einzelne ungültig zu machen.
