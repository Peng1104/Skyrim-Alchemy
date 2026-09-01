# Potion value calculation and optimization

This document describes how the project computes an effect's and a potion's
**gold** value, and how the solver picks the most profitable combination of
potions given the available inventory. The reference implementation lives in
`app/models.py` (`Effect.value`, `Potion.value`), `app/perks.py` (perk
bonuses), and `app/optimizer/_engine.py` (ILP).

The project only optimizes for gold value — but that also maximizes the
**Alchemy XP** gained from brewing the potions. Per
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP), the XP
gained from brewing a potion is **proportional to its gold value** (the game
doesn't document the exact proportionality constant, but the relationship is
monotonic: a more expensive potion $\Rightarrow$ more XP). In other words,
the fabrication sequence returned by this optimizer — which maximizes
$\sum \text{value}(r)$ — is, for the same reason, also the sequence that
maximizes accumulated Alchemy XP, without needing a separate XP model.

## 1. Base value of an effect

Each alchemy effect (`Effect`) has three base attributes, scraped from UESP:

- $C$ — `cost` (base cost)
- $M_0$ — `magnitude` (base magnitude)
- $D_0$ — `duration` (base duration, in seconds)

Ingredients provide multiplicative factors that adjust these values before
the final cost calculation:

- $f_c$ — cost factor (`cost_factor`, the `Value` modifier)
- $f_m$ — magnitude factor (`magnitude_factor`, the `Magnitude` modifier)
- $f_d$ — duration factor (`duration_factor`, the `Duration` modifier)

Each factor is $1$ when the ingredient has no matching modifier.

### 1.1 Effective magnitude and duration

$$
M = M_0 \cdot f_m
\qquad\qquad
D = D_0 \cdot f_d
$$

### 1.2 Effect cost

The game treats "instant" effects ($D_0 < 1$, no real duration, e.g. Restore
Health) differently from effects that have a duration:

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \qquad \text{if } D_0 < 1
$$

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \cdot T(D) \qquad \text{if } D_0 \ge 1
$$

where the duration term $T(D)$ is:

$$
T(D) = \left(\dfrac{D}{10}\right)^{1.1} \qquad \text{if } D > 0
$$

$$
T(D) = 1 \qquad \text{if } D = 0
$$

> $D = 0$ only happens when the **Purity** perk zeroes out the duration
> factor of an effect that would normally have a duration; in that case the
> duration term is dropped entirely (neutral factor) instead of zeroing out
> the whole cost.

### 1.3 Applying the cost factor

$$
\text{value}(effect) = \text{cost}(effect) \cdot f_c
$$

### 1.4 Rounding

The final value is truncated (not rounded) to the configured number of
decimal places ($p$, `decimal_places`, default $p=3$ during optimization and
$p=0$ for display):

$$
\text{value}_p(effect) = \frac{\big\lfloor \text{value}(effect) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

With $p = 0$ this is equivalent to $\lfloor \text{value}(effect) \rfloor$.

## 2. Resolving priority between ingredients

A potion is only valid if at least **2 ingredients share a single effect**
(see section 4). When two or more ingredients contribute to the same effect,
the game **does not sum or average** their factors — it uses only the
factors of the single highest-priority ingredient and discards the rest.

For each ingredient $i$ that contributes to effect $e$, define the factor
triple $(f_c^{(i)}, f_m^{(i)}, f_d^{(i)})$, obtained one of two ways:

1. **Explicit priority** (`Effect.priority_overrides`): some effects (e.g.
   *Damage Health*) have their own table on
   [UESP's effects list](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects)
   listing non-standard magnitude/duration ratios per ingredient (e.g.
   *River Betty*). In that case $f_c^{(i)} = 1$ and $(f_m^{(i)}, f_d^{(i)})$
   come from the table.
2. **Standard modifiers**: when there's no override, use
   $(f_c^{(i)}, f_m^{(i)}, f_d^{(i)})$ from the ingredient's own
   `Value`/`Magnitude`/`Duration` modifiers for that effect.

The winning ingredient is the one that **maximizes the resulting effect
value**:

$$
(f_c, f_m, f_d) = \text{arg max}_{i \in \text{contributors}(e)}
\quad \text{value}\big(e; f_c^{(i)}, f_m^{(i)}, f_d^{(i)}\big)
$$

If no ingredient has modifiers, the neutral triple $(1, 1, 1)$ is used.

## 3. Perk bonuses

Optional perks (`app/config.py`: `perk_physician`, `perk_benefactor`,
`perk_poisoner`, `perk_purity`) adjust magnitude/duration **after** the
priority resolution from section 2. All of them share the same fixed bonus,
$b = 1.25$ (i.e. a **+25%** multiplier).

### 3.1 Potion vs. poison classification

Before applying any perk, the value of **every** effect is computed with no
perk bonus at all ($\text{value}_{raw}$). The dominant effect is the one with
the highest raw value, and it decides whether the whole mixture is treated as
a potion or a poison:

$$
e^{\ast} = \text{arg max}_{e \in \text{effects}} \quad \text{value}_{raw}(e)
\qquad\qquad
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 3.2 Purity

If **Purity** is active and an effect's "polarity" doesn't match the
mixture's (a harmful effect inside a beneficial potion, or a beneficial
effect inside a poison), that effect's magnitude and duration are zeroed
out:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
f_m \leftarrow 0,\quad f_d \leftarrow 0
$$

This collapses the effect to its minimum base cost (the $\max(M^{1.1}, 1)$
term becomes $1$, and the duration term becomes $1$ per the $D=0$ rule from
section 1.2).

### 3.3 Physician, Benefactor, Poisoner

A multiplier $\mu$ is accumulated (independent of Purity), starting at
$\mu = 1$:

$$
\text{Physician active} \wedge e \in \\{\text{Restore Health, Restore Magicka, Restore Stamina}\\}
\quad\Longrightarrow\quad \mu \leftarrow \mu \cdot b
$$

$$
\text{isPoison} \wedge \text{Poisoner active} \wedge \text{harmful}(e)
\quad\Longrightarrow\quad \mu \leftarrow \mu \cdot b
$$

$$
\lnot \text{isPoison} \wedge \text{Benefactor active} \wedge \lnot \text{harmful}(e)
\quad\Longrightarrow\quad \mu \leftarrow \mu \cdot b
$$

### 3.4 Applying the multiplier

For most effects the multiplier scales **magnitude**. For a fixed set of
effects that have no meaningful magnitude
($\\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\\}$), the game
scales **duration** instead:

$$
(f_m, f_d) \leftarrow (f_m, f_d \cdot \mu) \qquad \text{if } e \text{ is in that set}
$$

$$
(f_m, f_d) \leftarrow (f_m \cdot \mu, f_d) \qquad \text{otherwise}
$$

The resulting $(f_m, f_d)$ replace the ones from section 2 in the effect's
final calculation (section 1).

## 4. Potion validity

A combination of $n \in \\{2, 3\\}$ ingredients only forms a valid potion
(`Potion.valid`) if **all** of the rules below hold:

1. $2 \le n \le 3$
2. The set of shared effects is not empty
3. Each effect $e$ in the potion appears in at least 2 of the ingredients:
   $\forall e \in \text{effects} : \big|\\{i : e \in \text{effects}(i)\\}\big| \ge 2$
4. Each ingredient shares at least one effect with another ingredient in the
   same potion (no "loose" ingredient)

## 5. Total potion value

A potion's value is the **sum** of the values of all of its shared effects,
each already adjusted for ingredient priority (section 2) and perks
(section 3):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 6. Optimization (integer linear programming)

Given the inventory $\text{amount}(g)$ of each ingredient $g$, the engine
(`app/optimizer/_engine.py`) generates **every** valid 2- and 3-ingredient
combination from the items on hand, computes $\text{value}(potion)$ for each
one (sections 1–5), deduplicates them while keeping the highest value, and
solves the following integer linear program with PuLP/CBC:

**Decision variables** — for each unique recipe $r$, $x_r \in \mathbb{Z}_{\ge 0}$
is the number of times it will be brewed.

**Objective function** (maximize total value):

$$
\max \sum_{r} x_r \cdot \text{value}(r)
$$

**Constraints** — for each ingredient $g$ in the inventory, the units
consumed across all recipes cannot exceed the available amount:

$$
\forall g : \sum_{r} x_r \cdot \text{count}(g, r) \le \text{amount}(g)
$$

where $\text{count}(g, r)$ is the number of units of ingredient $g$ that
recipe $r$ consumes (1 or 2, since a potion uses at most 3 distinct
ingredients).

The optimal solution $\\{x_r\\}$ defines the fabrication sequence
(`fabrication_sequence`), sorted by descending value, and the remaining
ingredients are the starting inventory minus what the solution consumed.
