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

## 1. Basiswert eines Effekts

Jeder Alchemie-Effekt (`Effect`) hat drei von UESP gescrapte Basiswerte:

- $C$ — `cost` (Basiskosten)
- $M_0$ — `magnitude` (Basisstärke)
- $D_0$ — `duration` (Basisdauer, in Sekunden)

Zutaten liefern multiplikative Faktoren, die diese Werte vor der
Kostenberechnung anpassen:

- $f_c$ — Kostenfaktor (`cost_factor`, der `Value`-Modifikator)
- $f_m$ — Stärkefaktor (`magnitude_factor`, der `Magnitude`-Modifikator)
- $f_d$ — Dauerfaktor (`duration_factor`, der `Duration`-Modifikator)

Jeder Faktor ist $1$, wenn die Zutat keinen passenden Modifikator hat.

### 1.1 Effektive Stärke und Dauer

$$
M = M_0 \cdot f_m
\qquad\qquad
D = D_0 \cdot f_d
$$

### 1.2 Effektkosten

Das Spiel behandelt "sofortige" Effekte ($D_0 < 1$, ohne echte Dauer, z. B.
Heilung wiederherstellen) anders als Effekte mit Dauer:

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \qquad \text{wenn } D_0 < 1
$$

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \cdot T(D) \qquad \text{wenn } D_0 \ge 1
$$

wobei der Dauerterm $T(D)$ ist:

$$
T(D) = \left(\dfrac{D}{10}\right)^{1.1} \qquad \text{wenn } D > 0
$$

$$
T(D) = 1 \qquad \text{wenn } D = 0
$$

> $D = 0$ tritt nur auf, wenn der Perk **Purity** den Dauerfaktor eines
> Effekts, der normalerweise eine Dauer hätte, auf null setzt; in diesem
> Fall entfällt der Dauerterm vollständig (neutraler Faktor), statt die
> gesamten Kosten auf null zu setzen.

### 1.3 Anwendung des Kostenfaktors

$$
\text{value}(effect) = \text{cost}(effect) \cdot f_c
$$

### 1.4 Rundung

Der Endwert wird auf die konfigurierte Anzahl an Dezimalstellen gekürzt
(nicht gerundet) ($p$, `decimal_places`, Standard $p=3$ bei der
Optimierung und $p=0$ für die Anzeige):

$$
\text{value}_p(effect) = \frac{\big\lfloor \text{value}(effect) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

Mit $p = 0$ entspricht das $\lfloor \text{value}(effect) \rfloor$.

## 2. Prioritätsauflösung zwischen Zutaten

Ein Trank ist nur gültig, wenn mindestens **2 Zutaten sich einen Effekt
teilen** (siehe Abschnitt 4). Wenn zwei oder mehr Zutaten zum selben Effekt
beitragen, **summiert oder mittelt** das Spiel ihre Faktoren **nicht** — es
verwendet nur die Faktoren der Zutat mit der höchsten Priorität und verwirft
die übrigen.

Für jede Zutat $i$, die zum Effekt $e$ beiträgt, wird das Faktor-Tripel
$(f_c^{(i)}, f_m^{(i)}, f_d^{(i)})$ auf eine von zwei Arten bestimmt:

1. **Explizite Priorität** (`Effect.priority_overrides`): Manche Effekte
   (z. B. *Damage Health*) haben eine eigene Tabelle in
   [UESPs Effektliste](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects),
   die nicht standardmäßige Stärke-/Dauerverhältnisse pro Zutat auflistet
   (z. B. *River Betty*). In diesem Fall ist $f_c^{(i)} = 1$, und
   $(f_m^{(i)}, f_d^{(i)})$ stammen aus der Tabelle.
2. **Standardmodifikatoren**: Gibt es keinen Override, wird
   $(f_c^{(i)}, f_m^{(i)}, f_d^{(i)})$ aus den eigenen
   `Value`/`Magnitude`/`Duration`-Modifikatoren der Zutat für diesen Effekt
   verwendet.

Die gewinnende Zutat ist diejenige unter den Beitragenden zu $e$, die
**den resultierenden Effektwert maximiert** ($i$ läuft dabei über die
beitragenden Zutaten):

$$
(f_c, f_m, f_d) = \text{arg max}_i \quad \text{value}\big(e; f_c^{(i)}, f_m^{(i)}, f_d^{(i)}\big)
$$

Hat keine Zutat Modifikatoren, wird das neutrale Tripel $(1, 1, 1)$
verwendet.

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
Effekts auf null gesetzt:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
f_m \leftarrow 0,\quad f_d \leftarrow 0
$$

Das reduziert den Effekt auf seine minimalen Basiskosten (der Term
$\max(M^{1.1}, 1)$ wird zu $1$, und der Dauerterm wird gemäß der
$D=0$-Regel aus Abschnitt 1.2 zu $1$).

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
(f_m, f_d) \leftarrow (f_m, f_d \cdot \mu) \qquad \text{wenn } e \text{ zu dieser Menge gehört}
$$

$$
(f_m, f_d) \leftarrow (f_m \cdot \mu, f_d) \qquad \text{andernfalls}
$$

Die resultierenden $(f_m, f_d)$ ersetzen die aus Abschnitt 2 in der
abschließenden Berechnung des Effekts (Abschnitt 1).

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
Effekte, jeweils bereits angepasst nach Zutatenpriorität (Abschnitt 2) und
Perks (Abschnitt 3):

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
nicht jede Zutat, die UESP kennt — für $k$ unterschiedliche Arten im
Besitz baut er also bis zu $\binom{k}{2} + \binom{k}{3}$ Kandidaten-Tränke,
bevor die Gültigkeitsprüfung und die Deduplizierung diese Zahl reduzieren.
$k$ ist nach oben durch die Gesamtzahl der gescrapten Zutaten begrenzt (190
zum Zeitpunkt dieses Schreibens — siehe
[docs/data-sources](../data-sources/DATA_SOURCES.de.md#1-zutaten)), was
einen theoretischen Worst Case von
$\binom{190}{2} + \binom{190}{3} = 17{,}955 + 1{,}125{,}180 = 1{,}143{,}135$
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
