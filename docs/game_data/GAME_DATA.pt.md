# Scan de dados do jogo: resolução de override e risco de colisão de nome

Este documento descreve como `app/game_data/` resolve overrides entre
plugins, e uma limitação específica e conhecida que decorre disso: dois
registros **não relacionados** que coincidem de resolver pro mesmo nome de
exibição não são ambos mantidos — os dicionários que este projeto constrói
são indexados por nome, então um deles é descartado silenciosamente. A
implementação de referência é `app/game_data/_scan.py` (`_scan_plugin`,
`_merge_snapshots`).

## 1. Como os overrides são resolvidos

O scan acontece em dois estágios (veja
[DATA_SOURCES.pt.md §3.1](../data-sources/DATA_SOURCES.pt.md#31-scan-incremental)
pra visão completa do cache incremental). `_scan_plugin` processa os
próprios registros `INGR`/`MGEF` de um plugin isoladamente, calculando a
identidade canônica `(owner_file, local_id)` de cada registro via
`resolve_form_id` (`app/game_data/_plugin_records.py`), aplicado contra a
própria lista de masters daquele plugin — essa etapa nunca olha pra nenhum
outro plugin, o que é justamente o que torna seu resultado (um
`PluginGameDataSnapshot`) seguro de cachear por plugin.

`_merge_snapshots(load_order, snapshots)` então percorre a load order ativa
inteira **uma vez** — masters vanilla, depois conteúdo de Creation Club
listado no `Skyrim.ccc`, depois os plugins ativos do `Plugins.txt`, nessa
ordem exata (veja
[DATA_SOURCES.pt.md §1.3](../data-sources/DATA_SOURCES.pt.md#13-creation-club-e-skyrimccc))
— e indexa todo registro de um tipo por essa mesma identidade canônica.
Quando um plugin mais tarde na load order define um registro com a mesma
identidade canônica de um que um plugin anterior já indexou (um override
genuíno — o plugin posterior lista o anterior como master e reutiliza seu
FormID), a entrada posterior **substitui** a anterior no índice. Quando toda
a load order já foi percorrida, cada chave no índice guarda só sua versão
final e autoritativa — exatamente como o próprio motor do jogo resolve
overrides, e exatamente por que `Ingredient`/`Effect.source_file` reporta o
plugin que atualmente *vence* para aquele FormID, não necessariamente o que
o introduziu originalmente (veja
[DATA_SOURCES.pt.md §1.1](../data-sources/DATA_SOURCES.pt.md#11-resolução-de-override)).

Essa parte é precisa em relação a FormID: não é possível confundir um
override genuíno com um registro novo não relacionado, ou vice-versa,
porque a identidade canônica é derivada da matemática real de FormID
relativa à lista de masters que o próprio jogo usa — e continua precisa
independente de quantos plugins foram reaproveitados do cache vs.
reprocessados no `_scan_plugin`, já que as identidades canônicas de um
snapshot em cache foram calculadas exatamente da mesma forma da última vez
que os bytes daquele plugin foram de fato lidos.

## 2. Onde a precisão de FormID para: os dicionários finais são indexados por nome

A segunda metade de `_merge_snapshots` transforma o índice indexado por
FormID nos `dict[str, Ingredient]`/`dict[str, Effect]` que o resto do
projeto usa, indexados pelo **nome de exibição resolvido** de cada
registro — é aqui que a precisão de FormID deixa de valer. Se dois
registros com identidades canônicas genuinamente diferentes e não
relacionadas (nenhuma relação de override entre eles) coincidem de resolver
pra string de exibição idêntica, só um deles sobrevive no dicionário final;
a própria atribuição de `dict` do Python sobrescreve silenciosamente o
outro. A ordem de iteração sobre o índice segue a ordem de inserção durante
o merge (posição na load order, agrupada por arquivo master), então na
prática **quem for processado por último naquela passagem vence** — não
necessariamente quem é semanticamente "correto" ou o override mais recente;
é puramente uma colisão de nome, independente do mecanismo de override da
seção 1.

## 3. Um caso real encontrado durante o desenvolvimento

Efeitos são o caso que este projeto de fato observou, não uma hipótese. No
início, `effects` era construído a partir de **todo** `MGEF` no índice
incondicionalmente (espelhando como `ingredients` é construído a partir de
todo `INGR`). Isso produzia 1525 efeitos — bem mais do que a alquimia tem —
e uma checagem pontual de "Damage Health" mostrava `cost=5.0,
source_file='Dragonborn.esm'` em vez do correto `cost=3.0,
source_file='Skyrim.esm'`. A causa: `Dragonborn.esm` define um `MGEF`
genuinamente não relacionado, só-de-quest (`DLC2TTR4aAbDamageHealth`,
usado por uma habilidade de quest com script, nada a ver com alquimia),
cujo texto `FULL` *também* coincide de resolver pra "Damage Health" —
mesma string, FormID completamente diferente, nenhuma relação de override.
Como `Dragonborn.esm` é processado depois de `Skyrim.esm` na load order,
seu `MGEF` não relacionado sobrescreveu silenciosamente a entrada do efeito
de alquimia real.

A correção **não** foi um detector de colisão de nome — foi restringir o
que vira um `Effect` logo de cara: `_merge_snapshots` só adiciona um
`MGEF` ao dict `effects` quando o `EFID` de algum ingrediente de fato o
referencia, o que exclui a vasta maioria dos registros `MGEF`
(encantamentos, habilidades de quest, etc.) antes mesmo de chegarem ao
dicionário indexado por nome. Isso derrubou a contagem de efeitos de 1525
pra 63 e corrigiu o caso do Damage Health. Isso **não** elimina o risco
geral da seção 2 — só remove a fonte específica e grande de falsos
positivos que vinha de incluir registros `MGEF` irrelevantes. Dois efeitos
*diferentes*, ambos referenciados por ingredientes (ou dois ingredientes
diferentes), que coincidentemente compartilham um nome ainda são possíveis,
só que bem mais raros.

## 4. Mitigação atual: nenhuma automática — cruze `form_id` manualmente

Não existe código que detecte "dois FormIDs diferentes e não relacionados
resolveram pro mesmo nome" e sinalize isso — uma duplicata descartada é
silenciosa, igual antes desta refatoração. Como `Ingredient`/`Effect`
agora carregam `source_file` e `form_id` (veja
[DATA_SOURCES.pt.md §1](../data-sources/DATA_SOURCES.pt.md#1-ingredientes)),
a forma prática de investigar uma colisão suspeita mudou: procure o
`form_id` da entrada em `cache/game_data/ingredients.json`/`effects.json`
e cruze com o xEdit ou a documentação do próprio mod — se o FormID não
bater com o que você esperava pra aquele nome, o registro de um plugin
diferente venceu a colisão de nome. Reordenar os plugins afetados no Mod
Organizer 2 (ou no `Plugins.txt` nativo) e rodar de novo com `--refresh`
muda qual registro vence o nome, como solução alternativa — o mesmo de
antes, mas agora verificável via `form_id` em vez de só inferido a partir
de entradas ausentes.
