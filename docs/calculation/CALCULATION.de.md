# Berechnung des Tränkewerts und Optimierung

Dieses Dokument beschreibt, wie das Projekt den **Gold**-Wert eines Effekts
und eines Tranks berechnet, und wie der Solver anhand des verfügbaren
Inventars die profitabelste Kombination von Tränken auswählt. Die
Referenzimplementierung befindet sich in `app/models.py` (`Effect.value`,
`Potion.value`), `app/perks.py` (Perk-Boni) und `app/optimizer/_engine.py`
(ILP).

Das Projekt optimiert nur nach Goldwert — das maximiert aber gleichzeitig
auch die gewonnenen **Alchemie-Erfahrungspunkte (XP)**. Laut
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP) sind die
beim Brauen eines Trankes gewonnenen XP **proportional zu seinem
Goldwert** (das Spiel dokumentiert die genaue Proportionalitätskonstante
nicht, aber der Zusammenhang ist monoton: teurerer Trank $\Rightarrow$ mehr
XP). Die von diesem Optimierer zurückgegebene Herstellungsreihenfolge — die
$\sum \text{value}(r)$ maximiert — ist aus demselben Grund also auch die
Reihenfolge, die die angesammelten Alchemie-XP maximiert, ohne dass ein
separates XP-Modell nötig wäre.

## 1. Effektkosten und die absolute Stärke/Dauer einer Zutat

Jeder Alchemie-Effekt (`Effect`) hat zwei Attribute, die direkt aus dem
eigenen binären `MGEF`-Datensatz des Spiels gelesen werden (siehe
[docs/data-sources/DATA_SOURCES.de.md](../data-sources/DATA_SOURCES.de.md))
— es gibt keine "Basisstärke" oder "Basisdauer", die für den Effekt selbst
irgendwo gespeichert wäre:

- $C$ — `cost` (das Base-Cost-Feld von `MGEF.DATA`)
- `harmful` — ob der Effekt Hostile/Detrimental ist (die Flag-Bits von
  `MGEF.DATA`), verwendet in Abschnitt 3 zur Klassifizierung Trank vs. Gift

Stärke und Dauer sind überhaupt keine Eigenschaft des Effekts — sie gehören
zu jeder einzelnen **Zutat**, genau wie das Spiel sie speichert: der
`INGR`-Datensatz jeder Zutat trägt bis zu 4 `EFIT`-Einträge (je 12 Bytes —
Magnitude, Area, Duration), einen pro Effekt, den sie erzeugt, wörtlich
gelesen in `IngredientEffect.magnitude`/`.duration` dieser Zutat. Es gibt
keine gemeinsame "Basis", von der der Wert jeder Zutat ein Vielfaches wäre
— das Paar $(M, D)$ jeder Zutat ist bereits absolut.

### 1.1 Effektkosten

Das Spiel behandelt "sofortige" Effekte ($D < 1$, ohne echte Dauer, z. B.
Heilung wiederherstellen) anders als Effekte mit Dauer:

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \qquad \text{wenn } D < 1
$$

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \cdot T(D) \qquad \text{wenn } D \ge 1
$$

wobei der Dauerterm $T(D)$ ist:

$$
T(D) = \left(\dfrac{D}{10}\right)^{1.1} \qquad \text{wenn } D > 0
$$

$$
T(D) = 1 \qquad \text{wenn } D = 0
$$

> $D = 0$ tritt nur auf, wenn der Perk **Purity** die Dauer eines Effekts
> auf null setzt (Abschnitt 3.2); in diesem Fall entfällt der Dauerterm
> vollständig (neutraler Faktor), statt die gesamten Kosten auf null zu
> setzen.

Das ist `Effect.value(magnitude, duration, decimal_places)` in `app/models.py`.

### 1.2 Rundung

Der Endwert wird auf die konfigurierte Anzahl an Dezimalstellen gekürzt
(nicht gerundet) ($p$, `decimal_places`, Standard $p=3$ bei der
Optimierung und $p=0$ für die Anzeige):

$$
\text{value}_p(effect; M, D) = \frac{\big\lfloor \text{value}(effect; M, D) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

Mit $p = 0$ entspricht das $\lfloor \text{value}(effect; M, D) \rfloor$.

## 2. Auflösung der gewinnenden Zutat in einem Trank

Ein Trank ist nur gültig, wenn mindestens **2 Zutaten sich einen Effekt
teilen** (siehe Abschnitt 4). Wenn zwei oder mehr Zutaten zum selben Effekt
beitragen, **summiert oder mittelt** das Spiel ihre $(M, D)$-Paare **nicht**
— es verwendet nur die eine Zutat, deren Beitrag den höchsten Wert erzeugt,
und verwirft die übrigen.

Für jede Zutat $i$, die in einem bestimmten Trank zum Effekt $e$ beiträgt,
trägt ihr `IngredientEffect` bereits ihr eigenes absolutes Paar
$(M^{(i)}, D^{(i)})$ — direkt aus dem `EFIT` dieser Zutat gelesen, ohne
irgendeine Nachschlagetabelle oder Override. Die gewinnende Zutat ist
diejenige unter den Beitragenden des Trankes zu $e$, die **den
resultierenden Effektwert maximiert**:

$$
(M, D) = \text{arg max}_i \quad \text{value}\big(e; M^{(i)}, D^{(i)}\big)
$$

Das ist `Potion.get_winning_effect(effect)` in `app/models.py`. Es wird
**für jeden Trank neu berechnet** — kein globales, vorberechnetes
Prioritäts-Ranking über den gesamten Zutatenkatalog. "Höchster Wert
gewinnt" als globales Ranking anzuwenden (unabhängig davon, welche
konkreten 2-3 Zutaten im Trank sind) wurde ausprobiert und verworfen: es
bevorzugte immer Zutaten der Creation Club, die das Spiel absichtlich
stärker balanciert als ihre Vanilla-Gegenstücke, und hätte sie
stillschweigend in Tränke eingesetzt, die sie in Wirklichkeit nie enthalten.

Das wurde gegen
[UESPs eigene Priority/Gold-Mult-Tabelle für Damage Health](https://en.uesp.net/wiki/Skyrim:Damage_Health)
verifiziert: die Berechnung von $\text{value}(e; M^{(i)}, D^{(i)})$ für
jede der 7 dokumentierten Zutatenstufen und das Ranking danach reproduziert
exakt UESPs eigene Prioritätsreihenfolge — einschließlich des Falls, in dem
eine Zutat mit kürzerer, sofortiger Dauer (Nirnroot) eine mit größerer
Stärke, aber echter Dauer (River Betty) trotzdem übertrifft — die Formel,
nicht ein redaktionelles Ranking, entscheidet den Gewinner.

## 3. Perk-Boni

Optionale Perks (`app/config.py`: `perk_physician`, `perk_benefactor`,
`perk_poisoner`, `perk_purity`) passen Stärke/Dauer **nach** der
Prioritätsauflösung aus Abschnitt 2 an. Alle teilen sich denselben festen
Bonus, $b = 1.25$ (also einen **+25%**-Multiplikator).

### 3.1 Klassifizierung Trank vs. Gift

Bevor irgendein Perk angewendet wird, wird der Wert **jedes** Effekts des
Trankes ohne jeden Perk-Bonus berechnet ($\text{value}_{raw}$). Der
dominante Effekt $e^{\ast}$ ist der mit dem höchsten Rohwert, und er
entscheidet, ob die gesamte Mischung als Trank oder als Gift behandelt wird:

$$
e^{\ast} = \text{arg max}_e \quad \text{value}_{raw}(e)
$$

$$
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 3.2 Purity

Ist **Purity** aktiv und stimmt die "Polarität" eines Effekts nicht mit der
der Mischung überein (ein schädlicher Effekt in einem wohltätigen Trank,
oder ein wohltätiger Effekt in einem Gift), werden Stärke und Dauer dieses
Effekts (das gewinnende Paar $(M, D)$ aus Abschnitt 2) auf null gesetzt:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
M \leftarrow 0,\quad D \leftarrow 0
$$

Das reduziert den Effekt auf seine minimalen Basiskosten (der Term
$\max(M^{1.1}, 1)$ wird zu $1$, und der Dauerterm wird gemäß der
$D=0$-Regel aus Abschnitt 1.1 zu $1$).

### 3.3 Physician, Benefactor, Poisoner

Ein Multiplikator $\mu$ wird akkumuliert (unabhängig von Purity), beginnend
bei $\mu = 1$. Jeder Perk unten multipliziert $\mu$ mit $b$, wenn er aktiv
ist und seine Bedingung zutrifft:

- **Physician**: $e$ ist Restore Health, Restore Magicka oder Restore Stamina
- **Poisoner**: die Mischung ist ein Gift (`isPoison`) und $e$ ist schädlich (`harmful(e)`)
- **Benefactor**: die Mischung ist **kein** Gift und $e$ ist **nicht** schädlich

$$
\mu \leftarrow \mu \cdot b
$$

### 3.4 Anwendung des Multiplikators

Bei den meisten Effekten skaliert der Multiplikator die **Stärke**. Für
eine feste Menge von Effekten ohne nennenswerte Stärke
($\\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\\}$), skaliert
das Spiel stattdessen die **Dauer**:

$$
(M, D) \leftarrow (M, D \cdot \mu) \qquad \text{wenn } e \text{ zu dieser Menge gehört}
$$

$$
(M, D) \leftarrow (M \cdot \mu, D) \qquad \text{andernfalls}
$$

Das ist `apply_perk_modifiers` in `app/perks.py`. Die resultierenden
$(M, D)$ ersetzen die gewinnenden aus Abschnitt 2 in der abschließenden
Berechnung des Effekts (Abschnitt 1).

## 4. Gültigkeit eines Trankes

Eine Kombination aus $n \in \\{2, 3\\}$ Zutaten bildet nur dann einen
gültigen Trank (`Potion.valid`), wenn **alle** folgenden Regeln erfüllt
sind:

1. $2 \le n \le 3$
2. Die Menge der geteilten Effekte ist nicht leer
3. Jeder Effekt $e$ des Trankes kommt in mindestens 2 der Zutaten vor:
   $\forall e \in \text{effects} : \big|\\{i : e \in \text{effects}(i)\\}\big| \ge 2$
4. Jede Zutat teilt sich mindestens einen Effekt mit einer anderen Zutat im
   selben Trank (keine "lose" Zutat)

## 5. Gesamtwert eines Trankes

Der Wert eines Trankes ist die **Summe** der Werte all seiner geteilten
Effekte, jeweils bereits zu ihrer gewinnenden Zutat aufgelöst (Abschnitt 2)
und nach Perks angepasst (Abschnitt 3):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 6. Optimierung (ganzzahlige lineare Programmierung)

Gegeben das Inventar $\text{amount}(g)$ jeder Zutat $g$, erzeugt die Engine
(`app/optimizer/_engine.py`) **alle** gültigen 2- und 3-Zutaten-Kombinationen
aus den vorhandenen Gegenständen, berechnet $\text{value}(potion)$ für jede
davon (Abschnitte 1–5), entfernt Duplikate unter Beibehaltung des höchsten
Werts und löst das folgende ganzzahlige lineare Programm mit PuLP/CBC.

### 6.1 Anzahl der Kombinationen

Der Kandidaten-Generierungsschritt (`_generate_potions`) kombiniert nur die
**tatsächlich im Inventar vorhandenen unterschiedlichen Zutatenarten**,
nicht jede Zutat im Cache der Spieldaten — für $k$ unterschiedliche Arten im
Besitz baut er also bis zu $\binom{k}{2} + \binom{k}{3}$ Kandidaten-Tränke,
bevor die Gültigkeitsprüfung und die Deduplizierung diese Zahl reduzieren.
$k$ ist nach oben durch die Gesamtzahl der Zutaten im Cache der Spieldaten
begrenzt (218 zum Zeitpunkt dieses Schreibens — siehe
[docs/data-sources](../data-sources/DATA_SOURCES.de.md#1-zutaten)), was
einen theoretischen Worst Case von
$\binom{218}{2} + \binom{218}{3} = 23.653 + 1.703.016 = 1.726.669$
Kandidaten ergibt — in der Praxis nie erreicht, da kein Inventar jemals
jede bekannte Zutat gleichzeitig enthält.

**Entscheidungsvariablen** — für jedes eindeutige Rezept $r$ ist
$x_r \in \mathbb{Z}_{\ge 0}$ die Anzahl, wie oft es gebraut wird.

**Zielfunktion** (Gesamtwert maximieren):

$$
\max \sum_{r} x_r \cdot \text{value}(r)
$$

**Nebenbedingungen** — für jede Zutat $g$ im Inventar darf die über alle
Rezepte verbrauchte Menge die verfügbare Menge nicht überschreiten:

$$
\forall g : \sum_{r} x_r \cdot \text{count}(g, r) \le \text{amount}(g)
$$

wobei $\text{count}(g, r)$ die Anzahl an Einheiten der Zutat $g$ ist, die
Rezept $r$ verbraucht (1 oder 2, da ein Trank höchstens 3 unterschiedliche
Zutaten verwendet).

Die optimale Lösung $\\{x_r\\}$ definiert die Herstellungsreihenfolge
(`fabrication_sequence`), absteigend nach Wert sortiert, und die
verbleibenden Zutaten sind das Ausgangsinventar abzüglich dessen, was die
Lösung verbraucht hat.
