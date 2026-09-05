# Potion value calculation and optimization

This document describes how the project computes an effect's and a potion's
**gold** value, and how the solver picks the most profitable combination of
potions given the available inventory.

The project only optimizes for gold value, but that also maximizes the
**Alchemy XP** gained from brewing the potions. Per
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP), the XP
gained from brewing a potion is **proportional to its gold value** (the game
doesn't document the exact proportionality constant, but the relationship is
monotonic: a more expensive potion $\Rightarrow$ more XP). In other words,
the fabrication sequence returned by this optimizer, which maximizes
$\sum \text{value}(r)$ is, for the same reason, also the sequence that
maximizes accumulated Alchemy XP.

## 1. Effect and Ingredient's attributes

### 1.1 Effect value and type

Each alchemy effect (`Effect`) has two attributes, read directly from the
game's own [`MGEF`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/MGEF) binary record (see
[docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md))

- $V_{base}$: The base `value` of the effect (`MGEF.DATA`'s Base Cost field)
- `harmful`: Whether the effect is Hostile/Detrimental (`MGEF.DATA`'s flag
  bits), used in section 4.1 to classify a potion vs. a poison

### 1.2 Ingredient 

Each ingredient has four (`IngredientEffect`), read directly from the
game's own ([`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)) binary record (see
[docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md)), each `IngredientEffect`
contains two attributes:

- $M$: The `magnitude` of the effect, how strong this ingredient's version of the effect is.
- $D$: The `duration` of the effect, how long this ingredient's version lasts.

## 2. Potion Value

### 2.1 Effect value

Per the game's own [`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)
record format (`EFIT`'s own auto-calc note), an effect's value is:

$$
\text{V}(\text{effect,ingredientEffect}) = V_{base} \cdot \left(\dfrac{M' \cdot D'}{10}\right)^{1.1}
$$

where $M' = \max(M, 1)$, and $D' = D$ if $D > 0$, else $D' = 10$ (a
`Magnitude < 1` is treated as `1`, and a `Duration` of `0` as `10`).
Equivalently, since exponentiation distributes over a product:

$$
\text{V}(\text{effect,ingredientEffect}) = V_{base} \cdot M'^{1.1} \cdot \left(\dfrac{D'}{10}\right)^{1.1}
$$

### 2.2 Rounding

The final value is truncated (not rounded) to the configured number of
decimal places ($p$, `decimal_places`, default $p=3$ during optimization and
$p=0$ for display):

$$
\text{value}_p(effect; M, D) = \frac{\big\lfloor \text{value}(effect; M, D) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

With $p = 0$ this is equivalent to $\lfloor \text{value}(effect; M, D) \rfloor$.

## 3. Resolving the winning IngredientEffect in a potion

A potion is only valid if at least **2 ingredients share a single effect**
(see section 6). For each effect, the game only uses one of the ingredients'
`IngredientEffect`. To define which one will be used the game uses the
section 2's formula and select the `IngredientEffect` that maximizes the
value. Given $S_e$, the set of $(M_i, D_i)$ pairs contributed by every
ingredient in the potion that has effect $e$:

$$
(M^{\ast}, D^{\ast}) = \underset{(M_i,\, D_i) \,\in\, S_e}{\text{arg max}} \quad \text{value}_{6}(e; M_i, D_i)
$$

## 4. Perk bonuses

Optional perks (`Physician`, `Benefactor`, `Poisoner`, `Purity`) adjust
magnitude/duration **after** the priority resolution from section 3.
All of them share the same fixed bonus, $b = 1.25$ (i.e. a **+25%** 
multiplier).

### 4.1 Potion vs. poison classification

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

### 4.2 Purity

If **Purity** is active and an effect's "polarity" doesn't match the
mixture's (a harmful effect inside a beneficial potion, or a beneficial
effect inside a poison), that effect is removed from the mixture
entirely; it contributes nothing to the potion's total value (section
7), and never reaches section 2's formula at all:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
e \notin \text{effects}(potion) \text{ (for value purposes)}
$$

### 4.3 Physician, Benefactor, Poisoner

A multiplier $\mu$ is accumulated (independent of Purity), starting at
$\mu = 1$. Each perk below, if active and its condition matches, multiplies
$\mu$ by $b$:

- **Physician**: $e$ is Restore Health, Restore Magicka, or Restore Stamina
- **Poisoner**: the mixture is a poison (`isPoison`) and $e$ is harmful (`harmful(e)`)
- **Benefactor**: the mixture is **not** a poison and $e$ is **not** harmful

$$
\mu \leftarrow \mu \cdot b
$$

### 4.4 Applying the multiplier

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

The resulting $(M, D)$ replace the winning ones from section 3 in the 
effect's final calculation (section 2).

## 5. Factors deliberately not modeled

The magnitude a crafted potion's effect actually ends up with, in-game, is
not simply the ingredient's own `EFIT` value, the game recomputes it at
brew time from the character's own skill, perks, and gear, per this
formula (same struct/property this project already reads `BaseMag` from
the [`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)
record's `EFIT`):

$$
\text{Result} = \text{fAlchemyIngredientInitMult} \cdot \text{BaseMag} \cdot \text{SkillMult}
\cdot \text{Alchemist} \cdot \text{Benefactor} \cdot \text{Physician} \cdot \text{Poisoner}
\cdot \text{Enchantments} \cdot \text{SeekerOfShadows}
$$

where `fAlchemyIngredientInitMult` $= 4$ (fixed game setting),
`SkillMult` $= 1 + (\text{fAlchemySkillFactor} - 1) \cdot \text{Skill}/100$
with `fAlchemySkillFactor` $= 1.5$ (so `SkillMult` ranges $1.0$ at
Alchemy skill $0$ to $1.5$ at skill $100$), `Alchemist` ranges $1.0$
(no perk) to $2.0$ (rank 5), `Enchantments` is $1.0$ plus the sum of any
equipped Fortify Alchemy gear, and `SeekerOfShadows` is $1.1$ when that
Dragonborn power is active (if the result comes out negative, it falls
back to plain `BaseMag`; a defensive clamp, not a real gameplay case
since every factor here is positive).

$M$ in this document (section 1.2) is exactly `BaseMag`, this project
stops there and never computes `Result`. `Benefactor`/`Physician`/
`Poisoner` **are** modeled (section 4), just applied after this project's
own value formula (section 2) instead of folded into `Result` beforehand;
mathematically the same $\times 1.25$ either way. Everything else in
this formula the `fAlchemyIngredientInitMult`, `SkillMult`, `Alchemist`,
`Enchantments` and `SeekerOfShadows` are deliberately left out:

- Each one is a **uniform** multiplier: the same value applies to every
  effect of every potion, regardless of which effect it is or which
  ingredients are involved (unlike `Benefactor`/`Physician`/`Poisoner`/
  `Purity`, which are conditional on the specific effect and the
  potion/poison polarity).
- A uniform multiplier $k$ on $M$ (or on $D$, for the duration-scaling
  effects from section 4.4) scales section 2's value formula by the same
  constant $k^{1.1}$ for **every** effect, and therefore scales
  $\text{value}(potion)$ by that same constant for **every** candidate
  potion (section 7).
- Multiplying every candidate's value by the same positive constant
  cannot change which one is highest; the ILP's optimal fabrication
  sequence (section 8) comes out **identical** whether these factors are
  included or not.

The one real consequence: the gold values this project reports are a
**floor**: Alchemy skill $0$, no `Alchemist` ranks, no Fortify Alchemy
gear, `Seeker of Shadows` inactive; Not what a specific, leveled-up
character would actually see in-game. That's an intentional trade-off:
modeling these factors would only rescale every number by the same
constant, at the cost of needing the player's exact skill/perks/gear as
additional input for no change in which potions get recommended.

## 6. Potion validity

A combination of $n \in \\{2, 3\\}$ ingredients only forms a valid potion
if **all** of the rules below hold:

1. $2 \le n \le 3$
2. The set of shared effects is not empty
3. Each effect $e$ in the potion appears in at least 2 of the ingredients:
   $\forall e \in \text{effects} : \big|\\{i : e \in \text{effects}(i)\\}\big| \ge 2$
4. Each ingredient shares at least one effect with another ingredient in the
   same potion (no "loose" ingredient)

## 7. Total potion value

A potion's value is the **sum** of the values of all of its shared effects,
each already resolved to its winning ingredient (section 3) and adjusted for
perks (section 4):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 8. Optimization (integer linear programming)

Given the inventory $\text{amount}(g)$ of each ingredient $g$, the engine
generates **every** valid 2- and 3-ingredient combination from the items 
on hand, computes $\text{value}(potion)$ for each one (sections 1–7),
deduplicates them while keeping the highest value, and solves the 
following integer linear program with PuLP/CBC.

### 8.1 Combination count

The candidate generation step only combines the **distinct ingredient types
actually in the inventory**, so for $k$ distinct types on hand, it builds
up to $\binom{k}{2} + \binom{k}{3}$ candidate potions before validity
filtering and deduplication trim that down. $k$ is bounded above by the
total number of ingredients in the game-data cache (218 as of this
writing, see
[docs/data-sources](../data-sources/DATA_SOURCES.md#1-ingredients)),
giving a theoretical worst case of
$\binom{218}{2} + \binom{218}{3} = 23{,}653 + 1{,}703{,}016 = 1{,}726{,}669$
candidates; that is never reached in practice, since no single inventory holds
every known ingredient at once.

**Decision variables**: For each unique recipe $r$, $x_r \in \mathbb{Z}_{\ge 0}$
is the number of times it will be brewed.

**Objective function** (maximize total value):

$$
\max \sum_{r} x_r \cdot \text{value}(r)
$$

**Constraints**: For each ingredient $g$ in the inventory, the units
consumed across all recipes cannot exceed the available amount:

$$
\forall g : \sum_{r} x_r \cdot \text{count}(g, r) \le \text{amount}(g)
$$

$\text{count}(g, r) = 1$ if recipe $r$ uses ingredient $g$, otherwise
$\text{count}(g, r) = 0$ and the term simply drops out of the sum for
$g$, a recipe is a **combination** of distinct ingredient types
(section 6), so it never uses more than one unit of the same ingredient.

The optimal solution $\\{x_r\\}$ defines the fabrication sequence, sorted
by descending value, and the remaining ingredients are the starting 
inventory minus what the solution consumed.
