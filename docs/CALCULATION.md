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

## 1. Valor base de um efeito

Cada efeito de alquimia (`Effect`) tem três atributos base, extraídos da UESP:

- $C$ — `cost` (custo base)
- $M_0$ — `magnitude` (magnitude base)
- $D_0$ — `duration` (duração base, em segundos)

Ingredientes fornecem fatores multiplicativos que ajustam esses valores antes
do cálculo do custo final:

- $f_c$ — fator de custo (`cost_factor`, modificador `Value`)
- $f_m$ — fator de magnitude (`magnitude_factor`, modificador `Magnitude`)
- $f_d$ — fator de duração (`duration_factor`, modificador `Duration`)

Cada fator vale $1$ quando o ingrediente não possui o modificador correspondente.

### 1.1 Magnitude e duração efetivas

$$
M = M_0 \cdot f_m
\qquad\qquad
D = D_0 \cdot f_d
$$

### 1.2 Custo do efeito

O jogo trata efeitos "instantâneos" ($D_0 < 1$, sem duração real, ex.: Restore
Health) de forma diferente de efeitos com duração:

$$
\text{cost}(effect) =
\begin{cases}
  C \cdot \max\!\big(M^{1.1},\, 1\big) & \text{se } D_0 < 1 \\[6pt]
  C \cdot \max\!\big(M^{1.1},\, 1\big) \cdot T(D) & \text{se } D_0 \ge 1
\end{cases}
$$

onde o termo de duração $T(D)$ é

$$
T(D) =
\begin{cases}
  \left(\dfrac{D}{10}\right)^{1.1} & \text{se } D > 0 \\[8pt]
  1 & \text{se } D = 0
\end{cases}
$$

> $D = 0$ só ocorre quando a perícia **Purity** zera o fator de duração de um
> efeito que normalmente tem duração; nesse caso o termo de duração é
> descartado (fator neutro) em vez de anular o custo inteiro.

### 1.3 Aplicação do fator de custo

$$
\text{value}(effect) = \text{cost}(effect) \cdot f_c
$$

### 1.4 Arredondamento

O valor final é truncado (não arredondado) para o número de casas decimais
configurado ($p$, `decimal_places`, padrão $p=3$ na otimização e $p=0$ para
exibição):

$$
\text{value}_p(effect) = \frac{\big\lfloor \text{value}(effect) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

Com $p = 0$ isso equivale a $\lfloor \text{value}(effect) \rfloor$.

## 2. Resolução de prioridade entre ingredientes

Uma poção só é válida se pelo menos **2 ingredientes compartilham um mesmo
efeito** (ver seção 4). Quando dois ou mais ingredientes contribuem para o
mesmo efeito, o jogo **não soma nem faz a média** de seus fatores — ele usa
apenas os fatores do ingrediente de maior prioridade e descarta os demais.

Para cada ingrediente $i$ que contribui com o efeito $e$, define-se a tripla
de fatores $(f_c^{(i)}, f_m^{(i)}, f_d^{(i)})$, obtida de uma das duas formas:

1. **Prioridade explícita** (`Effect.priority_overrides`): alguns efeitos
   (ex.: *Damage Health*) têm uma tabela própria na UESP listando razões de
   magnitude/duração não padrão por ingrediente (ex.: *River Betty*). Nesse
   caso $f_c^{(i)} = 1$ e $(f_m^{(i)}, f_d^{(i)})$ vêm da tabela.
2. **Modificadores padrão**: quando não há override, usa-se
   $(f_c^{(i)}, f_m^{(i)}, f_d^{(i)})$ dos modificadores `Value`/`Magnitude`/`Duration`
   do próprio ingrediente para aquele efeito.

O ingrediente vencedor é aquele que **maximiza o valor resultante do efeito**:

$$
(f_c, f_m, f_d) = \text{arg\,max}_{i \,\in\, \text{contribuintes}(e)}
\;\; \text{value}\big(e;\, f_c^{(i)}, f_m^{(i)}, f_d^{(i)}\big)
$$

Se nenhum ingrediente tiver modificadores, usa-se a tripla neutra $(1, 1, 1)$.

## 3. Bônus de perícia (perks)

Perícias opcionais (`app/config.py`: `perk_physician`, `perk_benefactor`,
`perk_poisoner`, `perk_purity`) ajustam magnitude/duração **depois** da
resolução de prioridade da seção 2. O bônus fixo de todas elas é

$$
b = 1.25 \quad (+25\%)
$$

### 3.1 Classificação poção vs. veneno

Antes de aplicar qualquer perícia, calcula-se o valor de **cada** efeito sem
nenhum bônus de perícia ($\text{value}_{raw}$). O efeito dominante é o de
maior valor bruto, e ele decide se a mistura inteira é tratada como poção ou
veneno:

$$
e^{\ast} = \text{arg\,max}_{e \,\in\, \text{effects}} \; \text{value}_{raw}(e)
\qquad\qquad
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 3.2 Purity

Se **Purity** está ativa e a "polaridade" do efeito não bate com a da mistura
(efeito nocivo dentro de uma poção benéfica, ou efeito benéfico dentro de um
veneno), magnitude e duração daquele efeito são zeradas:

$$
\text{harmful}(e) \ne \text{isPoison}
\;\Longrightarrow\;
f_m \leftarrow 0,\quad f_d \leftarrow 0
$$

Isso colapsa o efeito ao seu custo base mínimo (o termo $\max(M^{1.1},1)$ vira
$1$, e o termo de duração vira $1$ pela regra de $D=0$ da seção 1.2).

### 3.3 Physician, Benefactor, Poisoner

Um multiplicador $\mu$ é acumulado (independente de Purity):

$$
\mu = 1
$$

$$
\text{Physician ativo} \;\wedge\; e \in \{\text{Restore Health, Restore Magicka, Restore Stamina}\}
\;\Longrightarrow\; \mu \leftarrow \mu \cdot b
$$

$$
\text{isPoison} \;\wedge\; \text{Poisoner ativo} \;\wedge\; \text{harmful}(e)
\;\Longrightarrow\; \mu \leftarrow \mu \cdot b
$$

$$
\lnot\,\text{isPoison} \;\wedge\; \text{Benefactor ativo} \;\wedge\; \lnot\,\text{harmful}(e)
\;\Longrightarrow\; \mu \leftarrow \mu \cdot b
$$

### 3.4 Aplicação do multiplicador

Para a maioria dos efeitos o multiplicador escala a **magnitude**. Para um
conjunto fixo de efeitos que não têm magnitude significativa
($\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\}$), o jogo escala a
**duração** em vez disso:

$$
(f_m, f_d) \leftarrow
\begin{cases}
  (f_m,\; f_d \cdot \mu) & \text{se } e \in \text{efeitos de duração} \\[4pt]
  (f_m \cdot \mu,\; f_d) & \text{caso contrário}
\end{cases}
$$

Os $(f_m, f_d)$ resultantes substituem os da seção 2 no cálculo final do
efeito (seção 1).

## 4. Validade de uma poção

Uma combinação de $n \in \{2, 3\}$ ingredientes só forma uma poção válida
(`Potion.valid`) se **todas** as regras abaixo forem satisfeitas:

1. $2 \le n \le 3$
2. O conjunto de efeitos compartilhados não é vazio
3. Cada efeito $e$ da poção aparece em pelo menos 2 dos ingredientes:
   $\forall e \in \text{effects} : \big|\{i : e \in \text{effects}(i)\}\big| \ge 2$
4. Cada ingrediente compartilha pelo menos um efeito com outro ingrediente da
   mesma poção (nenhum ingrediente "solto")

## 5. Valor total de uma poção

O valor de uma poção é a **soma** dos valores de todos os seus efeitos
compartilhados, cada um já ajustado por prioridade de ingrediente (seção 2) e
por perícias (seção 3):

$$
\text{value}(potion) = \sum_{e \,\in\, \text{effects}(potion)} \text{value}_p(e)
$$

## 6. Otimização (programação linear inteira)

Dado o inventário $\text{amount}(g)$ de cada ingrediente $g$, o motor
(`app/optimizer/_engine.py`) gera **todas** as combinações válidas de 2 e 3
ingredientes a partir dos itens em posse, calcula $\text{value}(potion)$ para
cada uma (seções 1–5), remove duplicatas mantendo a de maior valor, e resolve
o seguinte problema de programação linear inteira com PuLP/CBC:

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

A solução ótima $\{x_r\}$ define a sequência de fabricação
(`fabrication_sequence`), ordenada por valor decrescente, e os ingredientes
sobrando são o inventário inicial menos o consumido pela solução.
