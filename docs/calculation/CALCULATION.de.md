# Berechnung des Trankwerts und Optimierung

Dieses Dokument beschreibt, wie das Projekt den **Gold**-Wert eines
Effekts und eines Tranks berechnet, und wie der Solver die profitabelste
Trankkombination anhand des verfügbaren Inventars auswählt.

Das Projekt optimiert nur für den Goldwert, aber das maximiert auch den
**Alchemie-XP**, der beim Brauen der Tränke gewonnen wird. Laut
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP) ist der
beim Brauen eines Tranks gewonnene XP **proportional zu seinem
Goldwert** (das Spiel dokumentiert die genaue
Proportionalitätskonstante nicht, aber die Beziehung ist monoton: ein
teurerer Trank $\Rightarrow$ mehr XP). Mit anderen Worten: die von
diesem Optimierer zurückgegebene Fertigungsreihenfolge, die
$\sum \text{value}(r)$ maximiert, ist aus demselben Grund auch die
Reihenfolge, die den angesammelten Alchemie-XP maximiert.

## 1. Eigenschaften von Effekt und Zutat

### 1.1 Effektwert und -typ

Jeder Alchemie-Effekt (`Effect`) hat zwei Eigenschaften, direkt aus dem
eigenen binären
[`MGEF`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/MGEF)-Datensatz
des Spiels gelesen (siehe
[docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md)):

- $V_{base}$: der Basis-`value` des Effekts (Base-Cost-Feld von `MGEF.DATA`)
- `harmful`: ob der Effekt Hostile/Detrimental ist (Flag-Bits von
  `MGEF.DATA`), verwendet in Abschnitt 4.1, um einen Trank von einem
  Gift zu unterscheiden

### 1.2 Zutat

Jede Zutat hat bis zu 4 (`IngredientEffect`), direkt aus dem eigenen
binären [`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)-Datensatz
des Spiels gelesen (siehe
[docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md)).
Jedes `IngredientEffect` enthält zwei Eigenschaften:

- $M$: die `magnitude` des Effekts, wie stark die Version dieser Zutat
  für diesen Effekt ist.
- $D$: die `duration` des Effekts, wie lange die Version dieser Zutat
  anhält.

## 2. Trankwert

### 2.1 Effektwert

Laut dem eigenen
[`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)-Datensatzformat
des Spiels (der eigenen Auto-Calc-Notiz von `EFIT`) ist der Wert eines
Effekts:

$$
\text{V}(\text{effect,ingredientEffect}) = V_{base} \cdot \left(\dfrac{M' \cdot D'}{10}\right)^{1.1}
$$

wobei $M' = \max(M, 1)$, und $D' = D$ falls $D > 0$, sonst $D' = 10$
(eine `Magnitude < 1` wird als `1` behandelt, und eine `Duration` von
`0` als `10`). Äquivalent dazu, da Exponentiation sich über ein Produkt
verteilt:

$$
\text{V}(\text{effect,ingredientEffect}) = V_{base} \cdot M'^{1.1} \cdot \left(\dfrac{D'}{10}\right)^{1.1}
$$

`Duration` ist immer eine ganze Zahl (das Duration-Feld von `EFIT` ist
ein `uint32`), also gilt $D > 0 \iff D \ge 1$: die Ersetzung $D' = 10$
greift nur genau dann, wenn $D = 0$. Es gibt keine Untergrenze für
$1 \le D < 10$: eine kurze, aber von null verschiedene Dauer verringert
den Wert tatsächlich unter das, was die Magnitude allein ergeben würde.

### 2.2 Rundung

Der endgültige Wert wird auf die konfigurierte Anzahl Nachkommastellen
abgeschnitten (nicht gerundet) ($p$, `decimal_places`, Standard $p=3$
während der Optimierung und $p=0$ für die Anzeige):

$$
\text{value}_p(effect; M, D) = \frac{\big\lfloor \text{value}(effect; M, D) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

Mit $p = 0$ entspricht das $\lfloor \text{value}(effect; M, D) \rfloor$.

## 3. Auflösen des gewinnenden IngredientEffect in einem Trank

Ein Trank ist nur gültig, wenn mindestens **2 Zutaten einen einzigen
Effekt teilen** (siehe Abschnitt 6). Für jeden Effekt $e$ verwendet das
Spiel nur das `IngredientEffect` einer der Zutaten: dasjenige, das die
Formel aus Abschnitt 2 maximiert. Gegeben $S_e$, die Menge der von jeder
Zutat im Trank mit Effekt $e$ beigetragenen Paare $(M_i, D_i)$:

$$
(M^{\ast}, D^{\ast}) = \underset{(M_i,\, D_i) \,\in\, S_e}{\text{arg max}} \quad \text{value}_{6}(e; M_i, D_i)
$$

Hat keine Zutat im Trank tatsächlich Effekt $e$, gilt $(M^{\ast},
D^{\ast}) = (0, 0)$.

Verifiziert gegen UESPs eigene Priority/Gold-Mult-Tabellen, pro Effekt:

- **Damage Health**: Jarrin Root ($M = 200$) übertrifft River Betty
  ($M = 5$).
- Die sofortige Dauer von Nirnroot ($D = 0$) übertrifft mehrere Zutaten
  mit höherer Magnitude, aber echter Dauer, für denselben Effekt.

## 4. Perk-Boni

Optionale Perks (`Physician`, `Benefactor`, `Poisoner`, `Purity`) passen
Magnitude/Duration **nach** der Prioritätsauflösung aus Abschnitt 3 an.
Alle teilen denselben festen Bonus, $b = 1.25$ (also einen
**+25%**-Multiplikator).

### 4.1 Klassifizierung Trank vs. Gift

Bevor irgendein Perk angewendet wird, wird der Wert **jedes** Effekts im
Trank ohne jeden Perk-Bonus berechnet ($\text{value}_{raw}$). Der
dominante Effekt $e^{\ast}$ ist der mit dem höchsten Rohwert, und er
entscheidet, ob die gesamte Mischung als Trank oder als Gift behandelt
wird:

$$
e^{\ast} = \text{arg max}_e \quad \text{value}_{raw}(e)
$$

$$
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 4.2 Purity

Wenn **Purity** aktiv ist und die "Polarität" eines Effekts nicht zur
Mischung passt (ein schädlicher Effekt in einem wohltätigen Trank, oder
ein wohltätiger Effekt in einem Gift), wird dieser Effekt vollständig
aus der Mischung entfernt: er trägt nichts zum Gesamtwert des Tranks bei
(Abschnitt 7) und erreicht die Formel aus Abschnitt 2 überhaupt nicht:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
e \notin \text{effects}(potion) \text{ (für Wertzwecke)}
$$

### 4.3 Physician, Benefactor, Poisoner

Ein Multiplikator $\mu$ wird akkumuliert (unabhängig von Purity),
beginnend bei $\mu = 1$. Jeder Perk unten multipliziert $\mu$ mit $b$,
falls aktiv und seine Bedingung zutrifft:

- **Physician**: $e$ ist Restore Health, Restore Magicka oder Restore
  Stamina
- **Poisoner**: die Mischung ist ein Gift (`isPoison`) und $e$ ist
  schädlich (`harmful(e)`)
- **Benefactor**: die Mischung ist **kein** Gift und $e$ ist **nicht**
  schädlich

$$
\mu \leftarrow \mu \cdot b
$$

### 4.4 Anwenden des Multiplikators

Für die meisten Effekte skaliert der Multiplikator die **Magnitude**.
Für eine feste Menge von Effekten ohne aussagekräftige Magnitude
($\\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\\}$), skaliert
das Spiel stattdessen die **Duration**:

$$
(M, D) \leftarrow (M, D \cdot \mu) \qquad \text{falls } e \text{ in dieser Menge ist}
$$

$$
(M, D) \leftarrow (M \cdot \mu, D) \qquad \text{sonst}
$$

Das resultierende $(M, D)$ ersetzt das gewinnende Paar aus Abschnitt 3
in der endgültigen Berechnung des Effekts (Abschnitt 2).

## 5. Absichtlich nicht modellierte Faktoren

Die Magnitude, mit der der Effekt eines gebrauten Tranks im Spiel
tatsächlich endet, ist nicht einfach der eigene `EFIT`-Wert der Zutat:
das Spiel berechnet sie zum Braumoment aus dem eigenen Skill, den Perks
und der Ausrüstung der Figur neu, nach dieser Formel (dieselbe
Struct/Eigenschaft, aus der dieses Projekt bereits `BaseMag` liest, im
`EFIT` des
[`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)-Datensatzes):

$$
\text{Result} = \text{fAlchemyIngredientInitMult} \cdot \text{BaseMag} \cdot \text{SkillMult}
\cdot \text{Alchemist} \cdot \text{Benefactor} \cdot \text{Physician} \cdot \text{Poisoner}
\cdot \text{Enchantments} \cdot \text{SeekerOfShadows}
$$

wobei `fAlchemyIngredientInitMult` $= 4$ (feste Spieleinstellung),
`SkillMult` $= 1 + (\text{fAlchemySkillFactor} - 1) \cdot \text{Skill}/100$
mit `fAlchemySkillFactor` $= 1.5$ (also reicht `SkillMult` von $1.0$ bei
Alchemie-Skill $0$ bis $1.5$ bei Skill $100$), `Alchemist` reicht von
$1.0$ (kein Perk) bis $2.0$ (Rang 5), `Enchantments` ist $1.0$ plus die
Summe jeder ausgerüsteten Fortify-Alchemy-Ausrüstung, und
`SeekerOfShadows` ist $1.1$, wenn diese Dragonborn-Fähigkeit aktiv ist
(kommt das Ergebnis negativ heraus, fällt es auf reines `BaseMag`
zurück, ein defensiver Clamp, kein echter Spielfall, da hier jeder
Faktor positiv ist).

$M$ in diesem Dokument (Abschnitt 1.2) ist genau `BaseMag`; dieses
Projekt hört dort auf und berechnet `Result` nie.
`Benefactor`/`Physician`/`Poisoner` **werden** modelliert (Abschnitt 4),
nur nach der eigenen Wertformel dieses Projekts (Abschnitt 2) angewendet,
statt vorher in `Result` eingefaltet zu werden; mathematisch ist es so
oder so dasselbe $\times 1.25$. Alles andere in dieser Formel,
`fAlchemyIngredientInitMult`, `SkillMult`, `Alchemist`, `Enchantments`
und `SeekerOfShadows`, wird absichtlich weggelassen:

- Jeder davon ist ein **einheitlicher** Multiplikator: derselbe Wert
  gilt für jeden Effekt jedes Tranks, unabhängig davon, welcher Effekt
  es ist oder welche Zutaten beteiligt sind (anders als
  `Benefactor`/`Physician`/`Poisoner`/`Purity`, die von dem spezifischen
  Effekt und der Polarität der Mischung abhängen).
- Ein einheitlicher Multiplikator $k$ auf $M$ (oder auf $D$, für die
  Duration-skalierenden Effekte aus Abschnitt 4.4) skaliert die
  Wertformel aus Abschnitt 2 um dieselbe Konstante $k^{1.1}$ für
  **jeden** Effekt, und skaliert daher $\text{value}(potion)$ um
  dieselbe Konstante für **jeden** Kandidatentrank (Abschnitt 7).
- Den Wert jedes Kandidaten mit derselben positiven Konstante zu
  multiplizieren, kann nicht ändern, welcher der höchste ist; die
  optimale Fertigungsreihenfolge des ILP (Abschnitt 8) kommt
  **identisch** heraus, ob diese Faktoren einbezogen werden oder nicht.

Die eine echte Konsequenz: die von diesem Projekt gemeldeten
Goldwerte sind eine **Untergrenze**: Alchemie-Skill $0$, keine
`Alchemist`-Ränge, keine Fortify-Alchemy-Ausrüstung, `Seeker of Shadows`
inaktiv; nicht das, was eine bestimmte, hochgelevelte Figur tatsächlich
im Spiel sehen würde. Das ist ein absichtlicher Kompromiss: diese
Faktoren zu modellieren würde jede Zahl nur um dieselbe Konstante neu
skalieren, auf Kosten dessen, den genauen Skill/Perks/Ausrüstung des
Spielers als zusätzliche Eingabe zu benötigen, ohne jede Änderung
daran, welche Tränke empfohlen werden.

## 6. Trankgültigkeit

Eine Kombination von $n \in \\{2, 3\\}$ Zutaten bildet nur dann einen
gültigen Trank, wenn **alle** Regeln unten zutreffen:

1. $2 \le n \le 3$
2. Die Menge der geteilten Effekte ist nicht leer
3. Jeder Effekt $e$ im Trank kommt in mindestens 2 der Zutaten vor:
   $\forall e \in \text{effects} : \big|\\{i : e \in \text{effects}(i)\\}\big| \ge 2$
4. Jede Zutat teilt mindestens einen Effekt mit einer anderen Zutat im
   selben Trank (keine "lose" Zutat)

## 7. Gesamter Trankwert

Der Wert eines Tranks ist die **Summe** der Werte all seiner geteilten
Effekte, jeder bereits auf seine gewinnende Zutat aufgelöst (Abschnitt
3) und um Perks angepasst (Abschnitt 4):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 8. Optimierung (ganzzahlige lineare Programmierung)

Gegeben das Inventar $\text{amount}(g)$ jeder Zutat $g$, erzeugt die
Engine **jede** gültige 2- und 3-Zutaten-Kombination aus den
vorhandenen Gegenständen, berechnet $\text{value}(potion)$ für jede
davon (Abschnitte 1 bis 7), dedupliziert sie unter Beibehaltung des
höchsten Werts und löst das folgende ganzzahlige lineare Programm mit
PuLP/CBC.

### 8.1 Kombinationsanzahl

Der Schritt zur Kandidatengenerierung kombiniert nur die **im Inventar
tatsächlich vorhandenen, unterschiedlichen Zutatentypen**, sodass er
für $k$ unterschiedliche vorhandene Typen bis zu
$\binom{k}{2} + \binom{k}{3}$ Kandidatentränke aufbaut, bevor
Gültigkeitsfilterung und Deduplizierung das reduzieren. $k$ ist nach
oben begrenzt durch die Gesamtzahl der Zutaten im Spieldaten-Cache (218
zum Zeitpunkt dieser Erstellung, siehe
[docs/data-sources](../data-sources/DATA_SOURCES.md#1-zutaten)), was
einen theoretischen Worst Case von
$\binom{218}{2} + \binom{218}{3} = 23{,}653 + 1{,}703{,}016 = 1{,}726{,}669$
Kandidaten ergibt; in der Praxis nie erreicht, da kein einzelnes
Inventar jede bekannte Zutat gleichzeitig enthält.

**Entscheidungsvariablen**: für jedes eindeutige Rezept $r$ ist
$x_r \in \mathbb{Z}_{\ge 0}$ die Anzahl, wie oft es gebraut wird.

**Zielfunktion** (Gesamtwert maximieren):

$$
\max \sum_{r} x_r \cdot \text{value}(r)
$$

**Nebenbedingungen**: für jede Zutat $g$ im Inventar darf die über alle
Rezepte hinweg verbrauchte Menge die verfügbare Menge nicht
überschreiten:

$$
\forall g : \sum_{r} x_r \cdot \text{count}(g, r) \le \text{amount}(g)
$$

$\text{count}(g, r) = 1$, wenn Rezept $r$ Zutat $g$ verwendet, sonst
$\text{count}(g, r) = 0$ und der Term fällt einfach aus der Summe für
$g$ heraus; ein Rezept ist eine **Kombination** unterschiedlicher
Zutatentypen (Abschnitt 6), verwendet also nie mehr als eine Einheit
derselben Zutat.

Die optimale Lösung $\\{x_r\\}$ definiert die Fertigungsreihenfolge,
sortiert nach absteigendem Wert, und die verbleibenden Zutaten sind das
Startinventar abzüglich dessen, was die Lösung verbraucht hat.
