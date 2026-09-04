# Cálculo de valor de poções e otimização

Este documento descreve como o projeto calcula o valor em **ouro** de um
efeito, de uma poção, e como o solver escolhe a combinação de poções mais
lucrativa dado o inventário disponível. A implementação de referência está em
`app/models.py` (`Effect.value`, `Potion.value`), `app/perks.py` (bônus de
perícia) e `app/optimizer/_engine.py` (ILP).

O projeto otimiza apenas o valor em ouro — mas isso também maximiza o
**XP de Alquimia** ganho ao fabricar as poções. Segundo a
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP), o XP
ganho ao fabricar uma poção é **proporcional ao seu valor em ouro**
(o jogo não documenta a constante exata de proporcionalidade, mas a relação é
monotônica: poção mais cara $\Rightarrow$ mais XP). Ou seja, a sequência de
fabricação retornada por este otimizador — que maximiza $\sum \text{value}(r)$
— é, pela mesma razão, a sequência que também maximiza o XP de Alquimia
acumulado, sem precisar de um modelo de XP separado.

## 1. Custo de um efeito e a magnitude/duração absoluta do ingrediente

Cada efeito de alquimia (`Effect`) tem dois atributos, lidos diretamente do
próprio registro binário `MGEF` do jogo (veja
[docs/data-sources/DATA_SOURCES.pt.md](../data-sources/DATA_SOURCES.pt.md)) —
não existe "magnitude base" nem "duração base" armazenada em lugar nenhum
para o efeito em si:

- $C$ — `cost` (o campo Base Cost do `MGEF.DATA`)
- `harmful` — se o efeito é Hostile/Detrimental (os bits de flag do
  `MGEF.DATA`), usado na seção 3 para classificar poção vs. veneno

Magnitude e duração não são propriedade do efeito de forma nenhuma — elas
pertencem a cada **ingrediente**, exatamente como o jogo as armazena: o
registro `INGR` de cada ingrediente carrega até 4 entradas `EFIT` (12 bytes
cada — Magnitude, Area, Duration), uma por efeito que ele produz, lidas
literalmente em `IngredientEffect.magnitude`/`.duration` daquele ingrediente.
Não existe nenhuma "base" compartilhada da qual o valor de cada ingrediente
seria um múltiplo — o par $(M, D)$ de cada ingrediente já é absoluto.

### 1.1 Custo do efeito

O jogo trata efeitos "instantâneos" ($D < 1$, sem duração real, ex.: Restore
Health) de forma diferente de efeitos com duração:

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \qquad \text{se } D < 1
$$

$$
\text{cost}(effect) = C \cdot \max\big(M^{1.1}, 1\big) \cdot T(D) \qquad \text{se } D \ge 1
$$

onde o termo de duração $T(D)$ é:

$$
T(D) = \left(\dfrac{D}{10}\right)^{1.1} \qquad \text{se } D > 0
$$

$$
T(D) = 1 \qquad \text{se } D = 0
$$

> $D = 0$ só ocorre quando a perícia **Purity** zera a duração de um efeito
> (seção 3.2); nesse caso o termo de duração é descartado (fator neutro) em
> vez de anular o custo inteiro.

Isso é `Effect.value(magnitude, duration, decimal_places)` em `app/models.py`.

### 1.2 Arredondamento

O valor final é truncado (não arredondado) para o número de casas decimais
configurado ($p$, `decimal_places`, padrão $p=3$ na otimização e $p=0$ para
exibição):

$$
\text{value}_p(effect; M, D) = \frac{\big\lfloor \text{value}(effect; M, D) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

Com $p = 0$ isso equivale a $\lfloor \text{value}(effect; M, D) \rfloor$.

## 2. Resolução do ingrediente vencedor em uma poção

Uma poção só é válida se pelo menos **2 ingredientes compartilham um mesmo
efeito** (ver seção 4). Quando dois ou mais ingredientes contribuem para o
mesmo efeito, o jogo **não soma nem faz a média** de seus pares $(M, D)$ —
ele usa apenas o ingrediente cuja contribuição produz o maior valor, e
descarta os demais.

Para cada ingrediente $i$ que contribui com o efeito $e$ numa poção
específica, seu `IngredientEffect` já carrega seu próprio par absoluto
$(M^{(i)}, D^{(i)})$ — lido diretamente do `EFIT` daquele ingrediente, sem
nenhuma tabela de consulta ou override envolvida. O ingrediente vencedor é
aquele, entre os contribuintes da poção para $e$, que **maximiza o valor
resultante do efeito**:

$$
(M, D) = \text{arg max}_i \quad \text{value}\big(e; M^{(i)}, D^{(i)}\big)
$$

Isso é `Potion.get_winning_effect(effect)` em `app/models.py`. É resolvido
**do zero para cada poção** — não é um ranking de prioridade global e
pré-computado sobre todo o catálogo de ingredientes. Aplicar "maior valor
vence" como um ranking global (independente de quais 2-3 ingredientes
específicos estão na poção) foi tentado e rejeitado: sempre favorecia
ingredientes da Creation Club, que o jogo deliberadamente equilibra mais
fortes que seus equivalentes vanilla, e teria silenciosamente substituído
eles em poções que na verdade nunca os contêm.

Isso foi validado contra a
[própria tabela de Priority/Gold Mult da UESP para Damage Health](https://en.uesp.net/wiki/Skyrim:Damage_Health):
calcular $\text{value}(e; M^{(i)}, D^{(i)})$ para cada um dos 7 níveis de
ingrediente documentados e ordenar por esse valor reproduz exatamente a
ordem de prioridade da própria UESP, incluindo o caso em que um ingrediente
com duração instantânea mais curta (Nirnroot) ainda supera um com magnitude
maior mas duração real (River Betty) — é a fórmula, não um ranking
editorial, que decide o vencedor.

## 3. Bônus de perícia (perks)

Perícias opcionais (`app/config.py`: `perk_physician`, `perk_benefactor`,
`perk_poisoner`, `perk_purity`) ajustam magnitude/duração **depois** da
resolução de prioridade da seção 2. O bônus fixo de todas elas é $b = 1.25$
(ou seja, um multiplicador de **+25%**).

### 3.1 Classificação poção vs. veneno

Antes de aplicar qualquer perícia, calcula-se o valor de **cada** efeito da
poção sem nenhum bônus de perícia ($\text{value}_{raw}$). O efeito dominante
$e^{\ast}$ é o de maior valor bruto, e ele decide se a mistura inteira é
tratada como poção ou veneno:

$$
e^{\ast} = \text{arg max}_e \quad \text{value}_{raw}(e)
$$

$$
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 3.2 Purity

Se **Purity** está ativa e a "polaridade" do efeito não bate com a da mistura
(efeito nocivo dentro de uma poção benéfica, ou efeito benéfico dentro de um
veneno), magnitude e duração daquele efeito (o par $(M, D)$ vencedor da
seção 2) são zeradas:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
M \leftarrow 0,\quad D \leftarrow 0
$$

Isso colapsa o efeito ao seu custo base mínimo (o termo $\max(M^{1.1}, 1)$
vira $1$, e o termo de duração vira $1$ pela regra de $D=0$ da seção 1.1).

### 3.3 Physician, Benefactor, Poisoner

Um multiplicador $\mu$ é acumulado (independente de Purity), começando em
$\mu = 1$. Cada perícia abaixo, se estiver ativa e sua condição bater,
multiplica $\mu$ por $b$:

- **Physician**: $e$ é Restore Health, Restore Magicka ou Restore Stamina
- **Poisoner**: a mistura é um veneno (`isPoison`) e $e$ é nocivo (`harmful(e)`)
- **Benefactor**: a mistura **não** é um veneno e $e$ **não** é nocivo

$$
\mu \leftarrow \mu \cdot b
$$

### 3.4 Aplicação do multiplicador

Para a maioria dos efeitos o multiplicador escala a **magnitude**. Para um
conjunto fixo de efeitos que não têm magnitude significativa
($\\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\\}$), o jogo escala
a **duração** em vez disso:

$$
(M, D) \leftarrow (M, D \cdot \mu) \qquad \text{se } e \text{ está nesse conjunto}
$$

$$
(M, D) \leftarrow (M \cdot \mu, D) \qquad \text{caso contrário}
$$

Isso é `apply_perk_modifiers` em `app/perks.py`. Os $(M, D)$ resultantes
substituem os vencedores da seção 2 no cálculo final do efeito (seção 1).

## 4. Validade de uma poção

Uma combinação de $n \in \\{2, 3\\}$ ingredientes só forma uma poção válida
(`Potion.valid`) se **todas** as regras abaixo forem satisfeitas:

1. $2 \le n \le 3$
2. O conjunto de efeitos compartilhados não é vazio
3. Cada efeito $e$ da poção aparece em pelo menos 2 dos ingredientes:
   $\forall e \in \text{effects} : \big|\\{i : e \in \text{effects}(i)\\}\big| \ge 2$
4. Cada ingrediente compartilha pelo menos um efeito com outro ingrediente da
   mesma poção (nenhum ingrediente "solto")

## 5. Valor total de uma poção

O valor de uma poção é a **soma** dos valores de todos os seus efeitos
compartilhados, cada um já resolvido para seu ingrediente vencedor (seção 2)
e ajustado por perícias (seção 3):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 6. Otimização (programação linear inteira)

Dado o inventário $\text{amount}(g)$ de cada ingrediente $g$, o motor
(`app/optimizer/_engine.py`) gera **todas** as combinações válidas de 2 e 3
ingredientes a partir dos itens em posse, calcula $\text{value}(potion)$ para
cada uma (seções 1–5), remove duplicatas mantendo a de maior valor, e resolve
o seguinte problema de programação linear inteira com PuLP/CBC.

### 6.1 Quantidade de combinações

A etapa de geração de candidatas (`_generate_potions`) só combina os
**tipos de ingrediente distintos que estão de fato no inventário**, não
todo ingrediente presente no cache de dados do jogo — então, para $k$ tipos
distintos em posse, ela monta até $\binom{k}{2} + \binom{k}{3}$ poções
candidatas, antes da filtragem de validade e da remoção de duplicatas
reduzirem esse número. $k$ é limitado pelo total de ingredientes no cache de
dados do jogo (218 no momento em que isso foi escrito — veja
[docs/data-sources](../data-sources/DATA_SOURCES.pt.md#1-ingredientes)),
o que dá um pior caso teórico de
$\binom{218}{2} + \binom{218}{3} = 23.653 + 1.703.016 = 1.726.669$
candidatas — nunca alcançado na prática, já que nenhum inventário tem todo
ingrediente conhecido ao mesmo tempo.

**Variáveis de decisão** — para cada receita única $r$, $x_r \in \mathbb{Z}_{\ge 0}$
é o número de vezes que ela será fabricada.

**Função objetivo** (maximizar valor total):

$$
\max \sum_{r} x_r \cdot \text{value}(r)
$$

**Restrições** — para cada ingrediente $g$ do inventário, a soma de unidades
consumidas por todas as receitas não pode exceder a quantidade disponível:

$$
\forall g : \sum_{r} x_r \cdot \text{count}(g, r) \le \text{amount}(g)
$$

onde $\text{count}(g, r)$ é o número de unidades do ingrediente $g$ que a
receita $r$ consome (1 ou 2, já que uma poção usa no máximo 3 ingredientes
distintos).

A solução ótima $\\{x_r\\}$ define a sequência de fabricação
(`fabrication_sequence`), ordenada por valor decrescente, e os ingredientes
sobrando são o inventário inicial menos o consumido pela solução.
