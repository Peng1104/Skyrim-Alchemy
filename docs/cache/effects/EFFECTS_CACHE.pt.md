🌐 [English](EFFECTS_CACHE.md) · [Português](EFFECTS_CACHE.pt.md) · [Deutsch](EFFECTS_CACHE.de.md)

# Effect Cache

Este documento descreve o cache em disco que guarda o banco de dados
final de efeitos mágicos, em `cache/game_data/effects.json`, construído
na mesma passada que o [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) e
sempre escrito junto com ele. Não é um dump completo de todo efeito
mágico que existe em todo plugin ativo. O jogo define muitos milhares
de efeitos sem relação com alquimia: feitiços, encantamentos,
habilidades só-de-missão, e por aí vai. Uma entrada só acaba aqui se
pelo menos um ingrediente no [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md)
de fato a produz. A seção 3 explica por que essa filtragem importa.

## 1. Estrutura

Um objeto JSON mapeando o nome de exibição de cada efeito pros seus
dados.

```jsonc
{
  "Restore Stamina": {
    "name": "Restore Stamina",
    "cost": 0.6000000238418579,
    "harmful": false,
    "source_file": "unofficial skyrim special edition patch.esp",
    "form_id": "0003EB16"
  }
  // uma entrada por efeito de fato produzido por algum ingrediente
}
```

(Trecho real.)

| Campo | Lido de | Significado |
| :--- | :--- | :--- |
| `name` | Sub-registro `FULL` | O nome de exibição do efeito, também a chave sob a qual é guardado. Dois efeitos genuinamente não relacionados, sem relação de override entre eles, poderiam em princípio compartilhar exatamente o mesmo texto de exibição e colidir aqui, um sobrescrevendo o outro silenciosamente. Isso é raro, mas não hipotético: veja a seção 3 pra um caso real. |
| `cost` | Sub-registro `DATA`, bytes 4-7 (float de 32 bits) | O próprio custo base do efeito, uma propriedade real do efeito, independente de qualquer ingrediente em particular, usada ao calcular quanto vale uma poção usando este efeito. Mantido exatamente como esses 4 bytes decodificam, sem arredondamento. Veja a seção 2 pro porquê disso parecer `0.6000000238418579` em vez de um `0.6` mais limpo. |
| `harmful` | Sub-registro `DATA`, bytes 0-3 (flags de 32 bits), bit `0x01` (Hostile) ou `0x04` (Detrimental) | Se o jogo classifica isso como um efeito harmful, tipo veneno. Verdadeiro se qualquer um dos bits estiver setado. Veja a seção 2 pro porquê dessa combinação específica de bits. |
| `source_file` | Qual registro de efeito mágico venceu a resolução de override | Qual versão deste efeito é a que de fato vale, usando a mesma regra de override que o `source_file` de um ingrediente: não necessariamente quem primeiro adicionou o efeito, mas cuja versão atualmente vence. Só informativo. |
| `form_id` | O próprio FormID desse registro vencedor, sem modificação | O próprio identificador do plugin vencedor pro efeito. Só informativo. |

Não existe campo de magnitude ou duration aqui de propósito, e nunca
vai existir. Esses descrevem o quão fortemente um ingrediente em
particular produz este efeito, e isso varia de ingrediente pra
ingrediente, como descrito na lista `effects` do documento
[Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md). Nenhuma magnitude ou duration
base compartilhada por efeito existe em lugar nenhum dos próprios
dados do jogo.

## 2. De onde cost e harmful de fato vêm

Nenhum dos dois é algo que este projeto decide ou calcula. Ambos são
lidos tal como estão, de bytes que o próprio formato de plugin da
Bethesda já define, dentro do bloco `DATA` de todo registro de efeito
mágico: um campo de flags de 32 bits no offset de byte 0, e um custo
base float de 32 bits no offset de byte 4.

`harmful` é derivado de dois bits individuais daquele valor de flags:
bit `0x01` (Hostile) e bit `0x04` (Detrimental). É verdadeiro se
qualquer um dos bits estiver setado. Essa regra específica, Hostile ou
Detrimental em vez de só Detrimental, foi escolhida checando ela contra
cada um dos 205 efeitos de alquimia que uma wiki documenta de forma
independente como harmful ou beneficial. Detrimental sozinho discordou
dessa referência em 2 deles, Paralysis e Fear, que o próprio jogo
marca como Hostile mas não Detrimental, enquanto Hostile ou Detrimental
bateu com todos os 205 sem nenhuma incompatibilidade. As duas posições
de bit, e os offsets de byte acima, vêm do próprio layout de registro
da Bethesda, não de nada que este projeto tenha inventado.

Todo outro float que este projeto lê de um plugin, esse `cost`
incluído, e a própria magnitude e duration de cada ingrediente, é
mantido exatamente como aquele float de 4 bytes decodifica, sem
nenhum arredondamento aplicado. É por isso que um valor como
`0.6000000238418579` aparece em vez de um `0.6` mais limpo. Não é
corrupção: é o que esses 4 bytes de fato decodificam, já que `0.3` não
tem representação binária de ponto flutuante exata, então os próprios
dados do jogo nunca guardaram um `0.6` perfeitamente limpo pra
começo de conversa. Converter isso pra um float mais largo pra
serialização só torna essa imprecisão pré-existente visível em vez de
escondê-la atrás de um valor de exibição arredondado.

## 3. Como é populado

Construído na mesma etapa que constrói o
[Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md). Ao resolver os efeitos de
cada ingrediente por nome, batendo o apontador de cada ingrediente
contra o efeito ao qual ele de fato se refere, todo efeito que é batido
com sucesso desse jeito também é registrado aqui. Este arquivo acaba
contendo exatamente os efeitos de fato alcançáveis a partir de pelo
menos um ingrediente, e nada mais.

Essa filtragem é deliberada, não incidental. Incluir todo efeito
mágico que um plugin define, incondicionalmente, também traria efeitos
completamente não relacionados a alquimia, alguns dos quais podem
coincidentemente compartilhar texto de exibição com um efeito de
alquimia real. Isso já aconteceu na prática: um efeito só-de-missão de
uma DLC uma vez resolveu pro exato mesmo nome que um efeito de alquimia
genuíno, mas com um custo diferente, o que teria corrompido
silenciosamente os dados daquele efeito de alquimia se todo efeito
fosse incluído incondicionalmente. Restringir este arquivo só ao que os
ingredientes de fato usam evita essa classe específica de colisão,
embora o caso mais estreito da seção 1, dois efeitos que são ambos de
fato usados por algum ingrediente ainda compartilhando um nome,
continue possível.

Este arquivo e o [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) são sempre
escritos juntos, na mesma passada. Veja a seção 3.1 daquele documento
pra exatamente quando uma reescrita acontece contra quando o resultado
de um scan anterior é reusado tal como está.

## 4. Quem o lê

Carregado junto com o [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) na
inicialização, mas tratado de forma mais tolerante se estiver
faltando. Um banco de ingredientes ausente é uma falha grave, já que
nada na aplicação consegue funcionar sem um, enquanto um banco de
efeitos ausente é simplesmente tratado como nenhum efeito conhecido
ainda, e a aplicação continua iniciando. Na prática os dois arquivos
são sempre escritos juntos, então isso importa principalmente pra uma
pasta de cache parcialmente montada ou alterada manualmente, não pro
uso normal.
