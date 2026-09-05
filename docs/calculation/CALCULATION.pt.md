# Cálculo de valor de poções e otimização

Este documento descreve como o projeto calcula o valor em **ouro** de um
efeito e de uma poção, e como o solver escolhe a combinação de poções mais
lucrativa dado o inventário disponível.

O projeto só otimiza pra valor em ouro, mas isso também maximiza o **XP de
Alquimia** ganho ao fabricar as poções. Segundo a
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy#Gaining_Skill_XP), o XP
ganho ao fabricar uma poção é **proporcional ao seu valor em ouro** (o jogo
não documenta a constante de proporcionalidade exata, mas a relação é
monotônica: uma poção mais cara $\Rightarrow$ mais XP). Em outras
palavras, a sequência de fabricação retornada por este otimizador, que
maximiza $\sum \text{value}(r)$, é, pelo mesmo motivo, também a sequência
que maximiza o XP de Alquimia acumulado.

## 1. Atributos de Efeito e Ingrediente

### 1.1 Valor e tipo do efeito

Cada efeito de alquimia (`Effect`) tem dois atributos, lidos direto do
próprio registro binário
[`MGEF`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/MGEF) do jogo
(veja [docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md)):

- $V_{base}$: o `value` base do efeito (campo Base Cost do `MGEF.DATA`)
- `harmful`: se o efeito é Hostile/Detrimental (bits de flag do
  `MGEF.DATA`), usado na seção 4.1 pra classificar uma poção contra um
  veneno

### 1.2 Ingrediente

Cada ingrediente tem até 4 (`IngredientEffect`), lidos direto do próprio
registro binário
[`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR) do jogo
(veja [docs/data-sources/DATA_SOURCES.md](../data-sources/DATA_SOURCES.md)).
Cada `IngredientEffect` contém dois atributos:

- $M$: a `magnitude` do efeito, o quão forte é a versão deste ingrediente
  pra esse efeito.
- $D$: a `duration` do efeito, quanto tempo dura a versão deste
  ingrediente.

## 2. Valor da Poção

### 2.1 Valor do efeito

Segundo o próprio formato de registro
[`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR) do jogo
(a própria nota de auto-cálculo do `EFIT`), o valor de um efeito é:

$$
\text{V}(\text{effect,ingredientEffect}) = V_{base} \cdot \left(\dfrac{M' \cdot D'}{10}\right)^{1.1}
$$

onde $M' = \max(M, 1)$, e $D' = D$ se $D > 0$, senão $D' = 10$ (uma
`Magnitude < 1` é tratada como `1`, e uma `Duration` de `0` como `10`).
De forma equivalente, já que a exponenciação distribui sobre um produto:

$$
\text{V}(\text{effect,ingredientEffect}) = V_{base} \cdot M'^{1.1} \cdot \left(\dfrac{D'}{10}\right)^{1.1}
$$

`Duration` é sempre um número inteiro (o campo Duration do `EFIT` é um
`uint32`), então $D > 0 \iff D \ge 1$: a substituição $D' = 10$ só se
aplica exatamente quando $D = 0$. Não existe piso pra $1 \le D < 10$: uma
duração curta, mas não nula, reduz de fato o valor abaixo do que a
magnitude sozinha daria.

### 2.2 Arredondamento

O valor final é truncado (não arredondado) pro número configurado de
casas decimais ($p$, `decimal_places`, padrão $p=3$ durante a otimização
e $p=0$ pra exibição):

$$
\text{value}_p(effect; M, D) = \frac{\big\lfloor \text{value}(effect; M, D) \cdot 10^{p} \big\rfloor}{10^{p}}
$$

Com $p = 0$ isso equivale a $\lfloor \text{value}(effect; M, D) \rfloor$.

## 3. Resolvendo o IngredientEffect vencedor numa poção

Uma poção só é válida se pelo menos **2 ingredientes compartilham um
único efeito** (veja a seção 6). Para cada efeito $e$, o jogo só usa o
`IngredientEffect` de um dos ingredientes: o que maximiza a fórmula da
seção 2. Dado $S_e$, o conjunto dos pares $(M_i, D_i)$ contribuídos por
cada ingrediente da poção que tem o efeito $e$:

$$
(M^{\ast}, D^{\ast}) = \underset{(M_i,\, D_i) \,\in\, S_e}{\text{arg max}} \quad \text{value}_{6}(e; M_i, D_i)
$$

Se nenhum ingrediente da poção tiver de fato o efeito $e$, $(M^{\ast},
D^{\ast}) = (0, 0)$.

Verificado contra as próprias tabelas de Priority/Gold Mult da UESP, por
efeito:

- **Damage Health**: Jarrin Root ($M = 200$) supera River Betty ($M = 5$).
- A duração instantânea do Nirnroot ($D = 0$) supera diversos
  ingredientes de magnitude maior, mas com duração real, pro mesmo efeito.

## 4. Bônus de perks

Perks opcionais (`Physician`, `Benefactor`, `Poisoner`, `Purity`) ajustam
magnitude/duration **depois** da resolução de prioridade da seção 3.
Todos compartilham o mesmo bônus fixo, $b = 1.25$ (ou seja, um
multiplicador de **+25%**).

### 4.1 Classificação poção vs. veneno

Antes de aplicar qualquer perk, o valor de **todo** efeito da poção é
calculado sem nenhum bônus de perk ($\text{value}_{raw}$). O efeito
dominante $e^{\ast}$ é o de maior valor bruto, e é ele que decide se a
mistura inteira é tratada como poção ou veneno:

$$
e^{\ast} = \text{arg max}_e \quad \text{value}_{raw}(e)
$$

$$
\text{isPoison} = \text{harmful}(e^{\ast})
$$

### 4.2 Purity

Se **Purity** está ativo e a "polaridade" de um efeito não bate com a da
mistura (um efeito harmful dentro de uma poção benéfica, ou um efeito
benéfico dentro de um veneno), esse efeito é removido da mistura por
completo: não contribui nada pro valor total da poção (seção 7), e nunca
chega na fórmula da seção 2:

$$
\text{harmful}(e) \ne \text{isPoison}
\quad\Longrightarrow\quad
e \notin \text{effects}(potion) \text{ (para fins de valor)}
$$

### 4.3 Physician, Benefactor, Poisoner

Um multiplicador $\mu$ é acumulado (independente de Purity), começando em
$\mu = 1$. Cada perk abaixo, se ativo e sua condição bater, multiplica
$\mu$ por $b$:

- **Physician**: $e$ é Restore Health, Restore Magicka ou Restore Stamina
- **Poisoner**: a mistura é um veneno (`isPoison`) e $e$ é harmful (`harmful(e)`)
- **Benefactor**: a mistura **não** é um veneno e $e$ **não** é harmful

$$
\mu \leftarrow \mu \cdot b
$$

### 4.4 Aplicando o multiplicador

Pra maioria dos efeitos o multiplicador escala a **magnitude**. Pra um
conjunto fixo de efeitos sem magnitude significativa
($\\{\text{Invisibility, Paralysis, Slow, Waterbreathing}\\}$), o jogo
escala a **duration** em vez disso:

$$
(M, D) \leftarrow (M, D \cdot \mu) \qquad \text{se } e \text{ está nesse conjunto}
$$

$$
(M, D) \leftarrow (M \cdot \mu, D) \qquad \text{caso contrário}
$$

O $(M, D)$ resultante substitui o vencedor da seção 3 no cálculo final do
efeito (seção 2).

## 5. Fatores deliberadamente não modelados

A magnitude com que o efeito de uma poção fabricada de fato termina, no
jogo, não é simplesmente o valor de `EFIT` do ingrediente: o jogo a
recalcula no momento da fabricação a partir do skill, dos perks e do
equipamento do personagem, por esta fórmula (a mesma struct/propriedade
de onde este projeto já lê `BaseMag`, no `EFIT` do registro
[`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)):

$$
\text{Result} = \text{fAlchemyIngredientInitMult} \cdot \text{BaseMag} \cdot \text{SkillMult}
\cdot \text{Alchemist} \cdot \text{Benefactor} \cdot \text{Physician} \cdot \text{Poisoner}
\cdot \text{Enchantments} \cdot \text{SeekerOfShadows}
$$

onde `fAlchemyIngredientInitMult` $= 4$ (configuração fixa do jogo),
`SkillMult` $= 1 + (\text{fAlchemySkillFactor} - 1) \cdot \text{Skill}/100$
com `fAlchemySkillFactor` $= 1.5$ (então `SkillMult` varia de $1.0$ no
skill de Alchemy $0$ até $1.5$ no skill $100$), `Alchemist` varia de
$1.0$ (sem perk) a $2.0$ (rank 5), `Enchantments` é $1.0$ mais a soma de
qualquer equipamento Fortify Alchemy equipado, e `SeekerOfShadows` é
$1.1$ quando esse poder do Dragonborn está ativo (se o resultado sair
negativo, ele volta pro `BaseMag` puro: um clamp defensivo, não um caso
real de jogo, já que todo fator aqui é positivo).

$M$ neste documento (seção 1.2) é exatamente `BaseMag`; este projeto para
por aí e nunca calcula `Result`. `Benefactor`/`Physician`/`Poisoner`
**são** modelados (seção 4), só que aplicados depois da própria fórmula
de valor deste projeto (seção 2) em vez de dobrados dentro de `Result`
antes; matematicamente é o mesmo $\times 1.25$ de qualquer jeito. O resto
desta fórmula, `fAlchemyIngredientInitMult`, `SkillMult`, `Alchemist`,
`Enchantments` e `SeekerOfShadows`, é deixado de fora deliberadamente:

- Cada um é um multiplicador **uniforme**: o mesmo valor se aplica a todo
  efeito de toda poção, independente de qual efeito seja ou quais
  ingredientes estejam envolvidos (diferente de
  `Benefactor`/`Physician`/`Poisoner`/`Purity`, que são condicionais ao
  efeito específico e à polaridade da mistura).
- Um multiplicador uniforme $k$ sobre $M$ (ou sobre $D$, pros efeitos que
  escalam duration da seção 4.4) escala a fórmula de valor da seção 2
  pela mesma constante $k^{1.1}$ pra **todo** efeito, e portanto escala
  $\text{value}(potion)$ por essa mesma constante pra **toda** poção
  candidata (seção 7).
- Multiplicar o valor de toda candidata pela mesma constante positiva não
  pode mudar qual delas é a maior; a sequência ótima de fabricação do ILP
  (seção 8) sai **idêntica** com ou sem esses fatores.

A consequência real única: os valores em ouro que este projeto reporta
são um **piso**: skill de Alchemy $0$, sem ranks de `Alchemist`, sem
equipamento Fortify Alchemy, `Seeker of Shadows` inativo; não o que um
personagem específico, já desenvolvido, realmente veria no jogo. Essa é
uma escolha deliberada: modelar esses fatores só reescalaria todo número
pela mesma constante, ao custo de precisar do skill/perks/equipamento
exatos do jogador como entrada extra, sem nenhuma mudança em quais
poções são recomendadas.

## 6. Validade da poção

Uma combinação de $n \in \\{2, 3\\}$ ingredientes só forma uma poção
válida se **todas** as regras abaixo valerem:

1. $2 \le n \le 3$
2. O conjunto de efeitos compartilhados não é vazio
3. Cada efeito $e$ na poção aparece em pelo menos 2 dos ingredientes:
   $\forall e \in \text{effects} : \big|\\{i : e \in \text{effects}(i)\\}\big| \ge 2$
4. Cada ingrediente compartilha pelo menos um efeito com outro
   ingrediente da mesma poção (sem ingrediente "solto")

## 7. Valor total da poção

O valor de uma poção é a **soma** dos valores de todos os seus efeitos
compartilhados, cada um já resolvido pro seu ingrediente vencedor (seção
3) e ajustado pelos perks (seção 4):

$$
\text{value}(potion) = \sum_{e \in \text{effects}(potion)} \text{value}_p(e)
$$

## 8. Otimização (programação linear inteira)

Dado o inventário $\text{amount}(g)$ de cada ingrediente $g$, o motor
gera **toda** combinação válida de 2 e 3 ingredientes a partir dos itens
disponíveis, calcula $\text{value}(potion)$ pra cada uma (seções 1 a 7),
deduplica mantendo o maior valor, e resolve o seguinte programa linear
inteiro com PuLP/CBC.

### 8.1 Contagem de combinações

A etapa de geração de candidatas só combina os **tipos de ingrediente
distintos que de fato estão no inventário**, então pra $k$ tipos
distintos disponíveis, ela constrói até $\binom{k}{2} + \binom{k}{3}$
poções candidatas antes que a filtragem de validade e a deduplicação
reduzam esse número. $k$ é limitado por cima pelo total de ingredientes
no cache de dados do jogo (218 no momento desta escrita, veja
[docs/data-sources](../data-sources/DATA_SOURCES.md#1-ingredientes)),
dando um pior caso teórico de
$\binom{218}{2} + \binom{218}{3} = 23{,}653 + 1{,}703{,}016 = 1{,}726{,}669$
candidatas; nunca alcançado na prática, já que nenhum inventário sozinho
tem todo ingrediente conhecido ao mesmo tempo.

**Variáveis de decisão**: pra cada receita única $r$, $x_r \in
\mathbb{Z}_{\ge 0}$ é o número de vezes que ela será fabricada.

**Função objetivo** (maximizar o valor total):

$$
\max \sum_{r} x_r \cdot \text{value}(r)
$$

**Restrições**: pra cada ingrediente $g$ no inventário, as unidades
consumidas em todas as receitas não podem passar da quantidade
disponível:

$$
\forall g : \sum_{r} x_r \cdot \text{count}(g, r) \le \text{amount}(g)
$$

$\text{count}(g, r) = 1$ se a receita $r$ usa o ingrediente $g$, senão
$\text{count}(g, r) = 0$ e o termo simplesmente some da soma pra $g$; uma
receita é uma **combinação** de tipos de ingrediente distintos (seção 6),
então ela nunca repete o mesmo ingrediente.

A solução ótima $\\{x_r\\}$ define a sequência de fabricação, ordenada
por valor decrescente, e os ingredientes restantes são o inventário
inicial menos o que a solução consumiu.
