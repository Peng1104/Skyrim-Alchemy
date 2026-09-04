# Potion value calculation and optimization

This document describes how the project computes an effect's and a potion's
**gold** value, and how the solver picks the most profitable combination of
potions given the available inventory. The reference implementation lives in
`app/models.py` (`Effect.value`, `Potion.value`), `app/perks.py` (perk
bonuses), and `app/optimizer/_engine.py` (ILP).

The project only optimizes for gold value, but that also maximizes the
**Alchemy XP** gained from brewing the potions. Per
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP), the XP
gained from brewing a potion is **proportional to its gold value** (the game
doesn't document the exact proportionality constant, but the relationship is
monotonic: a more expensive potion $\Rightarrow$ more XP). In other words,
the fabrication sequence returned by this optimizer — which maximizes
$\sum \text{value}(r)$ — is, for the same reason, also the sequence that
maximizes accumulated Alchemy XP, without needing a separate XP model.

## 1. Effect cost and an ingredient's absolute magnitude/duration

Each alchemy effect (`Effect`) has two attributes, read directly from the
game's own `MGEF` binary record (see
[docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md)) — there
is no "base magnitude" or "base duration" stored anywhere for an effect
itself:

- $C$ — `cost` (`MGEF.DATA`'s Base Cost field)
- `harmful` — whether the effect is Hostile/Detrimental (`MGEF.DATA`'s flag
  bits), used in section 3 to classify a potion vs. a poison

Magnitude and duration are not properties of the effect at all — they belong
to each **ingredient**, exactly as the game stores them: every ingredient's
`INGR` record carries up to 4 `EFIT` entries (12 bytes each — Magnitude,
Area, Duration), one per effect it produces, read verbatim into that
ingredient's `IngredientEffect.magnitude`/`.duration`. There is no shared
"base" that every ingredient's value is a multiplier of — each ingredient's
$(M, D)$ pair is already absolute.

### 1.1 Effect cost

The game treats "instant" effects ($D < 1$, no real duration, e.g. Restore
Health) differently from effects that have a duration:

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \qquad \text{if } D < 1
$$

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \cdot T(D) \qquad \text{if } D \ge 1
$$

where the duration term $T(D)$ is:

$$
T(D) = \left(\dfrac{D}{10}\right)^{1.1} \qquad \text{if } D > 0
$$

$$
T(D) = 1 \qquad \text{if } D = 0
$$

> $D = 0$ only happens when the **Purity** perk zeroes out an effect's
> duration (section 3.2); in that case the duration term is dropped entirely
> (neutral factor) instead of zeroing out the whole cost.

This is `Effect.value(magnitude, duration, decimal_places)` in `app/models.py`.

### 1.2 Rounding

The final value is truncated (not rounded) to the configured number of
decimal places ($p$, `decimal_places`, default $p=3$ during optimization and
$p=0$ for display):

$$
\text{value}_p(effect; M, D) = \frac{\big\lfloor \text{value}(effect; M, D) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

With $p = 0$ this is equivalent to $\lfloor \text{value}(effect; M, D) \rfloor$.

## 2. Resolving the winning ingredient in a potion

A potion is only valid if at least **2 ingredients share a single effect**
(see section 4). When two or more ingredients contribute to the same effect,
the game **does not sum or average** their $(M, D)$ pairs — it uses only the
single ingredient whose contribution produces the highest value, and
discards the rest.

For each ingredient $i$ that contributes to effect $e$ in a given potion, its
`IngredientEffect` already carries its own absolute $(M^{(i)}, D^{(i)})$ —
read straight from that ingredient's `EFIT`, no lookup or override table
involved. The winning ingredient is the one, among the potion's contributors
to $e$, that **maximizes the resulting effect value**:

$$
(M, D) = \text{arg max}_i \quad \text{value}\big(e; M^{(i)}, D^{(i)}\big)
$$

This is `Potion.get_winning_effect(effect)` in `app/models.py`. It is
resolved **fresh for every potion** — it is not a global, precomputed
priority ranking over the whole ingredient catalog. Applying "highest value
wins" as a global ranking (independent of which specific 2–3 ingredients are
in the potion) was tried and rejected: it always favored Creation Club
ingredients, which the game deliberately balances stronger than their
vanilla counterparts, and would have silently substituted them into potions
that never actually contain them.

This was verified against
[UESP's own Priority/Gold Mult table for Damage Health](https://en.uesp.net/wiki/Skyrim:Damage_Health):
computing $\text{value}(e; M^{(i)}, D^{(i)})$ for each of the 7 documented
ingredient tiers and ranking by that value reproduces UESP's own priority
order exactly, including the case where an ingredient with a shorter,
instant duration (Nirnroot) still outranks one with a larger magnitude but a
real duration (River Betty) — the formula, not an editorial ranking, decides
the winner.

## 3. Perk bonuses

Optional perks (`app/config.py`: `perk_physician`, `perk_benefactor`,
`perk_poisoner`, `perk_purity`) adjust magnitude/duration **after** the
priority resolution from section 2. All of them share the same fixed bonus,
$b = 1.25$ (i.e. a **+25%** multiplier).

### 3.1 Potion vs. poison classification

Before applying any perk, the value of **every** effect in the potion is
computed with no perk bonus at all ($\text{value}_{raw}$). The dominant
effect $e^{\ast}$ is the one with the highest raw value, and it decides
whether the whole mixture is treated as a potion or a poison:

$$
e^{\ast} = \text{arg max}_e \quad \text{value}_{raw}(e)
$$

$$
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 3.2 Purity

If **Purity** is active and an effect's "polarity" doesn't match the
mixture's (a harmful effect inside a beneficial potion, or a beneficial
effect inside a poison), that effect's magnitude and duration (the winning
$(M, D)$ from section 2) are zeroed out:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
M \leftarrow 0,\quad D \leftarrow 0
$$

This collapses the effect to its minimum base cost (the $\max(M^{1.1}, 1)$
term becomes $1$, and the duration term becomes $1$ per the $D=0$ rule from
section 1.1).

### 3.3 Physician, Benefactor, Poisoner

A multiplier $\mu$ is accumulated (independent of Purity), starting at
$\mu = 1$. Each perk below, if active and its condition matches, multiplies
$\mu$ by $b$:

- **Physician**: $e$ is Restore Health, Restore Magicka, or Restore Stamina
- **Poisoner**: the mixture is a poison (`isPoison`) and $e$ is harmful (`harmful(e)`)
- **Benefactor**: the mixture is **not** a poison and $e$ is **not** harmful

$$
\mu \leftarrow \mu \cdot b
$$

### 3.4 Applying the multiplier

For most effects the multiplier scales **magnitude**. For a fixed set of
effects that have no meaningful magnitude
($\\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\\}$), the game
scales **duration** instead:

$$
(M, D) \leftarrow (M, D \cdot \mu) \qquad \text{if } e \text{ is in that set}
$$

$$
(M, D) \leftarrow (M \cdot \mu, D) \qquad \text{otherwise}
$$

This is `apply_perk_modifiers` in `app/perks.py`. The resulting $(M, D)$
replace the winning ones from section 2 in the effect's final calculation
(section 1).

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
each already resolved to its winning ingredient (section 2) and adjusted for
perks (section 3):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 6. Optimization (integer linear programming)

Given the inventory $\text{amount}(g)$ of each ingredient $g$, the engine
(`app/optimizer/_engine.py`) generates **every** valid 2- and 3-ingredient
combination from the items on hand, computes $\text{value}(potion)$ for each
one (sections 1–5), deduplicates them while keeping the highest value, and
solves the following integer linear program with PuLP/CBC.

### 6.1 Combination count

The candidate generation step (`_generate_potions`) only combines the
**distinct ingredient types actually in the inventory**, not every
ingredient in the game-data cache — so for $k$ distinct types on hand, it builds
up to $\binom{k}{2} + \binom{k}{3}$ candidate potions before validity
filtering and deduplication trim that down. $k$ is bounded above by the
total number of ingredients in the game-data cache (218 as of this
writing — see
[docs/data-sources](../data-sources/DATA_SOURCES.md#1-ingredients)),
giving a theoretical worst case of
$\binom{218}{2} + \binom{218}{3} = 23{,}653 + 1{,}703{,}016 = 1{,}726{,}669$
candidates — never reached in practice, since no single inventory holds
every known ingredient at once.

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
