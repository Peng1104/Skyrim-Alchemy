# Scan de dados do jogo: resolução de override e risco de colisão de nome

Este documento descreve como o scan de dados do jogo resolve overrides
entre plugins, e uma limitação específica e conhecida que decorre disso.
Dois registros não relacionados que coincidem de resolver pro mesmo nome
de exibição não ficam ambos guardados: os dicionários finais que este
projeto constrói são indexados por nome, então um deles é derrubado
silenciosamente.

## 1. Como overrides são resolvidos

O scan acontece em dois estágios, descritos por completo nos documentos
[Plugin Cache](../cache/plugin/PLUGIN_CACHE.md) e
[Ingredient Cache](../cache/ingredients/INGREDIENTS_CACHE.md).

1. Os próprios registros de ingrediente e efeito mágico de cada plugin
   são primeiro parseados isoladamente, calculando a identidade
   canônica de cada registro: qual plugin de fato o define, e um id
   numérico que permanece estável independente de qual outro plugin
   está referenciando. Essa etapa nunca olha pra nenhum outro plugin, o
   que é o que torna seu resultado seguro pra cachear por plugin.
2. A load order ativa inteira é então percorrida uma vez, masters
   vanilla, depois conteúdo de Creation Club, depois a própria lista de
   plugins ativos do usuário, nessa ordem exata, e todo registro de um
   tipo é indexado por essa mesma identidade canônica. Quando um plugin
   mais tarde na load order define um registro com a mesma identidade
   canônica que um plugin anterior já indexou, um override genuíno onde
   o plugin mais tarde lista o anterior como master e reusa seu
   registro, a entrada mais tarde substitui a anterior no índice.

No momento em que a load order inteira foi percorrida, toda entrada no
índice guarda só sua versão final e autoritativa, exatamente como o
próprio motor do jogo resolve overrides, e exatamente por que o plugin
de origem registrado de um ingrediente ou efeito é o que atualmente
vence, não necessariamente o que originalmente o introduziu.

Essa parte do processo é exata. Não é possível que um override genuíno
seja confundido com um registro novo não relacionado, ou o contrário,
porque a identidade canônica é derivada da mesma numeração relativa à
lista de masters que o próprio jogo usa, e permanece exata não importa
quantos plugins tenham sido reusados do cache versus recém-parseados, já
que as próprias identidades canônicas de um plugin em cache foram
calculadas do mesmo jeito na última vez que os bytes daquele plugin
foram de fato lidos.

## 2. Onde a exatidão para: os dicionários finais são indexados por nome

| Etapa | Indexado por | Livre de colisão? |
| :--- | :--- | :--- |
| O índice construído na seção 1 | Identidade canônica | Sim |
| Os bancos finais de ingredientes e efeitos | Nome de exibição resolvido | Não |

Se dois registros com identidades canônicas genuinamente diferentes e
não relacionadas, sem relação de override entre eles, coincidem de
resolver pra string de exibição idêntica, só um deles sobrevive no
resultado final. O outro é sobrescrito silenciosamente.

Qual deles vence é determinado puramente pela ordem de processamento
durante essa passada, na prática qualquer um que seja processado por
último, não necessariamente o que é semanticamente correto ou o
sobrescrito mais recentemente. É puramente uma colisão de nome,
independente do mecanismo de override descrito na seção 1.

O banco de efeitos só inclui efeitos mágicos de fato referenciados por
algum ingrediente, excluindo a vasta maioria dos registros de efeito
mágico no jogo, encantamentos, habilidades de missão, e por aí vai,
antes deles sequer chegarem no dicionário indexado por nome. Isso reduz
substancialmente a exposição ao risco acima, já que a maioria dos
efeitos mágicos nunca vira candidata a colisão pra começo de conversa,
mas não o elimina: dois efeitos diferentes referenciados por
ingredientes, ou dois ingredientes diferentes, ainda podem
coincidentemente compartilhar um nome.

## 3. Mitigação atual: cross-referenciar o FormID manualmente

Não existe detecção automática pra duas identidades diferentes e não
relacionadas resolvendo pro mesmo nome. Uma duplicata derrubada é
silenciosa. Investigar uma colisão suspeita é um processo manual de três
passos:

1. Procure o FormID da entrada no cache de ingredientes ou efeitos. Todo
   ingrediente e efeito carrega seu plugin vencedor e FormID; veja a
   seção 1 do documento [fontes de dados](../data-sources/DATA_SOURCES.md).
2. Cross-referencie esse FormID contra o
   [xEdit](https://github.com/TES5Edit/TES5Edit), a ferramenta da
   comunidade pra ler e editar plugins que também documenta o layout de
   struct real de todo tipo de registro, ou a própria documentação do
   mod. Se não bater com o que era esperado pra aquele nome, o registro
   de um plugin diferente venceu a colisão de nome.
3. Reordene os plugins afetados na load order e rescaneie. Isso muda
   qual registro vence o nome, como solução alternativa, o mesmo de
   antes, mas agora verificável através do FormID em vez de só inferido
   de uma entrada faltando.
