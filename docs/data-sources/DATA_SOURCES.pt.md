# Dados de ingredientes e efeitos (leitura binária dos plugins)

Este documento descreve de onde vêm os dados de ingredientes e efeitos do
projeto: **os próprios dados binários de todo plugin ativo do Skyrim**
(`.esm`/`.esp`/`.esl`), lidos diretamente — sem wiki, sem raspagem, sem
requisições HTTP. A implementação de referência está em `app/game_data/`
(`_scan.py`, `_load_order.py`, `_plugin_records.py`, `_bsa.py`,
`_strings.py`).

Só o CLI (`cli.py`) escaneia a instalação do jogo e grava o cache — é o
único processo com um `game_directory` local. O `AlchemyOptimizer`
(`app/optimizer/_engine.py`) e a API só leem o cache
(`load_cached_game_data`, `app/game_data/__init__.py`) — veja a
[seção 3](#3-cache) pro que acontece quando esse cache não existe.

## 0. Por que não a wiki

Versões anteriores deste projeto raspavam a
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects) para dados de
ingredientes/efeitos, incluindo uma "magnitude base"/"duração base" por
efeito. Ler o formato binário do próprio jogo diretamente revelou que esse
conceito não existe de verdade: um efeito (`MGEF`) só tem um `cost` e uma
flag `harmful` como propriedades reais e definidas pelo jogo. Magnitude e
duração não são propriedade do *efeito* de forma nenhuma — pertencem a cada
*ingrediente*, guardadas por ingrediente nas entradas `EFIT` do seu registro
`INGR`. Os valores "base" da UESP são uma convenção editorial (os valores
que a maioria dos ingredientes "padrão" acontece de compartilhar), não um
campo que o motor do jogo lê de lugar nenhum — e essa convenção tem lacunas
reais (ex.: efeitos como *Fortify Alchemy*, que existem no jogo mas não
aparecem na tabela de efeitos da UESP). Ler o binário evita os dois
problemas: todo valor vem exatamente dos mesmos dados que o próprio motor do
jogo usa, e todo efeito que qualquer ingrediente ativo de fato produz é
incluído, seja vanilla, DLC, Creation Club ou mod de terceiro.

### 0.1 Caso confirmado: o antigo `cost_factor` contava a duração duas vezes (Giant's Toe)

Os modelos `Effect`/`IngredientEffect` de antes desta refatoração tinham um
`cost_factor` (raspado do ícone de modificador "Value" da UESP para o par
ingrediente-efeito) que multiplicava direto no custo de um efeito, junto
com fatores separados de `magnitude`/`duration`. O plano desta refatoração
removeu o `cost_factor` por completo, marcando-o como um risco assumido, já
que não tinha correspondência binária conhecida em `EFIT`/`MGEF`, e nenhum
caso que precisasse dele tinha aparecido durante o desenvolvimento.

Um caso real apareceu depois, comparando a saída dos sistemas antigo e novo
sobre o mesmo inventário real: **Giant's Toe**, combinado com *Blisterwort*
e *Wheat*, valia **544,239** de ouro no sistema antigo (raspado da wiki) vs.
**119,654** no novo (baseado no `.esm`) — uma diferença de ~4,5x, inteiramente
atribuível a um único efeito compartilhado, *Fortify Health*. O `EFIT` real
do Giant's Toe dá a ele `magnitude=4, duration=300` para *Fortify Health*
(o próprio `EFIT` de `Fortify Health` do Wheat é `magnitude=4, duration=60`
— o caso sem modificador nenhum), que o sistema novo lê e usa diretamente.
O sistema antigo tinha *também* raspado um ícone de modificador
`Value: 5.9` da tabela de ingredientes da UESP para esse par específico, e
aplicado isso como um `cost_factor` multiplicativo **extra**, em cima da
diferença de duração que já estava embutida em `duration=300`.

Esse `5.9` nunca foi um multiplicador independente pra começar — é a
própria explicação em prosa da UESP sobre a *consequência* do aumento de
5x na duração, não um mecanismo de jogo separado:

$$
\left(\frac{300}{10}\right)^{1.1} \Big/ \left(\frac{60}{10}\right)^{1.1}
= 5^{1.1} \approx 5,874 \approx 5,9
$$

ou seja, exatamente o próprio termo de duração da fórmula de valor (seção
1.1 de
[docs/calculation/CALCULATION.pt.md](../calculation/CALCULATION.pt.md#11-custo-do-efeito)),
elevado ao mesmo expoente 1.1 já aplicado a todo efeito. O raspador antigo
confundiu essa razão descritiva com um modificador `Value` independente e
multiplicou por ela como `cost_factor`, contando duas vezes o mesmo aumento
de duração que `duration=300` já contabilizava. O sistema novo, lendo
`duration=300` direto do `EFIT`, sem nenhum conceito de `cost_factor`,
calcula o valor correto uma única vez.

No mesmo inventário real, 88 das 89 receitas sem ingrediente de mod bateram
exatas entre o sistema antigo e o novo (bit a bit no valor final em ouro);
esse caso do Giant's Toe foi a única exceção, e ela se resolveu a favor do
sistema novo — confirmando que remover o `cost_factor` foi uma correção de
bug, não uma regressão, pelo menos em todo caso testado até agora.

## 1. Ingredientes

Todo ingrediente na load order ativa vira um `Ingredient`, construído a
partir do seu registro `INGR`:

- **Nome** — a subrecord `FULL` do registro, resolvida via `resolve_full`
  (`app/game_data/_strings.py`): texto literal, ou um ID de string
  localizada resolvido contra o BSA de `.strings` do plugin que define o
  registro (veja a
  [seção 1.2](#12-strings-localizadas-e-o-fallback-de-bsa-das-dlc)).
- **Efeitos** — até 4 `IngredientEffect`s, um por par `EFID`+`EFIT` do
  registro. `EFIT` (12 bytes) guarda a Magnitude (float32), Area (uint32,
  não usada por este projeto) e Duration (uint32) do efeito **exatamente
  como aquele ingrediente o produz** — não existe nenhuma "base"
  compartilhada da qual isso seja relativo (veja
  [CALCULATION.pt.md §1](../calculation/CALCULATION.pt.md#1-custo-de-um-efeito-e-a-magnitudeduração-absoluta-do-ingrediente)).
- **`source_file`/`form_id`** — o nome do arquivo do plugin e o FormID em
  hex do registro *autoritativo* (pós-override) do ingrediente — veja a
  [seção 1.1](#11-resolução-de-override).

No momento em que isso foi escrito, um scan completo de uma instalação
modada real produz **218 ingredientes**. Isso não está fixo em código nenhum
lugar — é o que a load order ativa de fato contém — mas é o limite superior
prático de quantos tipos distintos de ingrediente o otimizador pode ver, o
que importa para o pior caso da quantidade de combinações (veja a
[seção 6.1 do documento de cálculo](../calculation/CALCULATION.pt.md#61-quantidade-de-combinações)).

### 1.1 Resolução de override

O formato de plugin do Skyrim permite que um plugin mais tarde na load order
redefina o registro de um plugin anterior reutilizando seu FormID — um
override genuíno, não um item novo. Os próprios registros `INGR`/`MGEF` de
cada plugin são primeiro processados isoladamente num snapshot por plugin
(`_scan_plugin`, `app/game_data/_scan.py` — veja a
[seção 3.1](#31-scan-incremental) pra entender por que isso é cacheável por
plugin); `_merge_snapshots` então monta a load order uma única vez —
masters vanilla, depois o conteúdo de Creation Club listado no `Skyrim.ccc`
(veja a [seção 1.3](#13-creation-club-e-skyrimccc)), depois os plugins
ativos do `Plugins.txt`, nessa ordem — e indexa todo registro `INGR`/`MGEF`
pela sua identidade canônica `(defining_file, local_id)`, resolvida via
`resolve_form_id`. Um plugin mais tarde na load order simplesmente
sobrescreve a entrada do índice para um FormID que um plugin anterior já
tinha definido, então o índice acaba guardando só a versão final e
autoritativa de todo registro — exatamente como o próprio motor do jogo
resolve overrides. Veja
[docs/game_data/GAME_DATA.pt.md](../game_data/GAME_DATA.pt.md) pra
mecânica completa, incluindo o risco de colisão de nome que decorre disso.

`source_file`/`form_id` em `Ingredient`/`Effect` refletem essa versão
autoritativa, não necessariamente o plugin que originalmente introduziu o
item — ex.: um ingrediente originalmente adicionado por um plugin de
Creation Club, mas desde então corrigido pelo Unofficial Skyrim Special
Edition Patch (USSEP), reporta o USSEP como seu `source_file`.

### 1.2 Strings localizadas e o fallback de BSA das DLC

A subrecord `FULL` de um registro pode guardar tanto texto literal quanto um
ID numérico de string localizada, caso em que o texto de verdade vive num
arquivo `.strings` dentro de um dos próprios BSAs do plugin que o define
(`strings/<stem_do_plugin>_<idioma>.strings`, processado por
`parse_strings_file`). Uma lacuna real encontrada durante a validação: o
Skyrim SE distribui `Dawnguard.esm`, `HearthFires.esm`, `Dragonborn.esm` e
`Update.esm` **sem nenhum BSA próprio** — as strings deles ficam dentro do
próprio `Skyrim - Interface.bsa` do `Skyrim.esm`, sob o stem de cada DLC.
`_load_strings_table` (`app/game_data/_strings.py`) recorre aos BSAs do
`Skyrim.esm` sempre que a busca pelo stem do próprio plugin não encontra
nada, o que cobre esse caso sem fixar em código nenhuma DLC específica.

### 1.3 Creation Club e `Skyrim.ccc`

Conteúdo de Creation Club **não** é listado no `Plugins.txt` da forma como
um mod normal é — o motor da Bethesda carrega automaticamente o que estiver
listado no `Skyrim.ccc` (um arquivo texto puro, um plugin por linha, na raiz
de instalação do jogo, não em nenhum perfil de gerenciador de mods)
independentemente do `Plugins.txt`. Isso foi confirmado empiricamente: o
menu de Creations do próprio jogo mostrava um pacote de Creation Club como
ativo mesmo sem nenhuma entrada pra ele no `plugins.txt` do Mod Organizer 2
— o MO2 só lista conteúdo de Creation Club como uma entrada de prioridade
de mod "Not managed by MO2" (um artefato de ordenação de conflito de
arquivo, sem relação com se o plugin de fato carrega).
`_resolve_load_order` (`app/game_data/_scan.py`) lê o `Skyrim.ccc` via
`parse_ccc` (`app/game_data/_load_order.py`) e insere todo plugin que ele
lista na load order, entre os masters vanilla e o conteúdo do
`Plugins.txt`, então ingredientes/efeitos de Creation Club são escaneados
igual a tudo o mais.

O `Skyrim.ccc` (e a lista de masters vanilla) nomeia plugins com a grafia
mista da própria Bethesda (ex.: `ccBGSSSE037-Curios.esl`), que não
necessariamente bate com o nome de arquivo real em disco num sistema de
arquivos case-sensitive — uma biblioteca Steam compartilhada com o Windows
e montada no Linux costuma ser ext4, diferente do padrão case-insensitive
do próprio NTFS. Um check `.exists()` ingênuo contra a grafia do `.ccc`
descarta silenciosamente o plugin de todo o scan quando os dois diferem;
confirmado empiricamente numa instalação real, onde 74 de 75 entradas do
`Skyrim.ccc` falharam num check de case exato dessa forma, e qualquer
ingrediente delas não sobrescrito por outro plugin ativo (então nunca lido
indiretamente através da lista de masters, corretamente grafada, de outro
plugin) sumia inteiramente do banco de ingredientes.
`_index_data_dir_case_insensitively` (`app/game_data/_scan.py`) monta um
mapa nome-minúsculo → nome-real-em-disco uma vez por scan, e todo nome de
plugin vindo do `Skyrim.ccc`/lista de masters vanilla/`Plugins.txt` é
resolvido por ele antes de entrar na load order, então o resto do scan
sempre abre arquivos pela grafia real e exata, independente de qual grafia
a lista de origem usou.

### 1.4 Risco de colisão de nome

Dois registros **não relacionados** (FormIDs diferentes, sem relação de
override) ainda podem coincidentemente resolver pro mesmo nome de exibição
— esse é um risco real, ainda que raro, inerente a indexar os dicionários
finais por nome em vez de por FormID. Veja
[docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) para a explicação
completa, incluindo um caso real que este projeto encontrou durante o
desenvolvimento (um efeito só-de-quest do Dragonborn.esm que coincidiu de
resolver pro mesmo texto do efeito real de alquimia "Damage Health").

## 2. Efeitos

Um `Effect` só é criado para um `MGEF` de fato referenciado pelo `EFID` de
algum ingrediente — o jogo define muitos milhares de registros `MGEF` sem
relação com alquimia (encantamentos, habilidades de quest/script, etc.), e
construir a tabela de efeitos a partir de *todo* `MGEF` incondicionalmente
deixou um desses registros irrelevantes sobrescrever silenciosamente um
efeito de alquimia real que coincidia de compartilhar seu texto de exibição
(veja [docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) para esse
caso específico). Cada `Effect` lê dois campos direto do `MGEF.DATA`
(`get_mgef_base_cost`/`get_mgef_harmful`, `app/game_data/_plugin_records.py`):

- **`cost`** — o float32 de Base Cost no offset 4.
- **`harmful`** — se o bit de flag Hostile (`0x01`) ou Detrimental (`0x04`)
  está setado no offset 0. Validado contra 205 efeitos documentados pela
  UESP com zero divergências durante o desenvolvimento.

`cost` (e todo outro float lido de um plugin, incluindo o
`magnitude`/`duration` de cada ingrediente) é guardado exatamente como o
próprio float32 do jogo decodifica — deliberadamente sem arredondar. Um
valor como `0.30000001192092896` pra um `cost` que a própria UESP documenta
como `0.3` não é corrupção: `0.3` não tem representação binária de ponto
flutuante exata, então os próprios bytes float32 do jogo decodificam pra
esse mesmo valor mais próximo representável; converter isso pro float64 do
Python pra serializar como JSON só torna visível a imprecisão já existente,
em vez de escondê-la. O objetivo é manter exatamente o valor que o `.esm`
em si guarda, não uma aproximação arredondada mais bonita dele.

Não existe campo `magnitude`/`duration` no `MGEF` de forma nenhuma —
confirmado lendo as próprias definições de registro do xEdit
(`Core/wbDefinitionsTES5.pas`), além dos bytes brutos. Veja
[CALCULATION.pt.md §1](../calculation/CALCULATION.pt.md#1-custo-de-um-efeito-e-a-magnitudeduração-absoluta-do-ingrediente)
para como `cost`/`harmful` se combinam com os próprios valores `EFIT` de
cada ingrediente.

## 3. Cache

`scan_game_data` (`app/game_data/_scan.py`) grava sob `cache/game_data/`:

```
cache/game_data/
├── plugins/             Um arquivo JSON pequeno por resultado bruto de scan de plugin (<nome do plugin>.json)
├── ingredients.json    O banco final e mesclado de Ingredientes
└── effects.json         O banco final e mesclado de Efeitos
```

### 3.1 Scan incremental

O scan é incremental **por plugin**, não tudo-ou-nada. Os próprios
registros `INGR`/`MGEF` de cada plugin ativo são processados num
`PluginGameDataSnapshot` (nome, texto de exibição resolvido, FormIDs
canônicos — veja `app.models`) que depende só dos próprios bytes daquele
plugin e do(s) próprio(s) BSA(s) dele, nunca de nenhum outro plugin na load
order. Esse snapshot é guardado sob sua própria assinatura de invalidação
de cache (tamanho + mtime) em seu próprio arquivo,
`cache/game_data/plugins/<nome do plugin>.json` — um arquivo pequeno por
plugin em vez de um arquivo grande pra todos juntos, então a contribuição
de um plugin fica fácil de inspecionar isoladamente, e um re-scan só
reescreve os arquivos dos plugins que de fato mudaram (veja abaixo). Num
scan posterior, um plugin cuja assinatura ainda bate reaproveita seu
snapshot em cache tal como está — o parse binário/BSA de fato é pulado por
completo pra ele — e só os plugins que de fato mudaram são reprocessados.
A etapa (barata, puramente em memória) que resolve overrides de `FormID` e
referências cruzadas de nome de efeito por toda a load order continua
rodando em todo scan, sobre qualquer mistura de snapshots em cache e
recém-processados que a load order atual precisar, e produz
`ingredients.json`/`effects.json`.

Isso importa na prática: numa instalação real com ~100 plugins ativos, um
scan completo (todo plugin reprocessado, ex.: depois de instalar vários
mods de uma vez, ou via `force=True` do `--refresh`) levou **~30
segundos**; tocar a mtime de um único plugin e rodar de novo (todo outro
snapshot reaproveitado do cache, seu arquivo intocado em disco) levou
**~0,2 segundos** — uma diferença de ~150x, exatamente para o caso comum
de adicionar/atualizar/remover um ou dois mods por vez.

Um plugin removido da load order desde o último scan (mod desinstalado, ou
`Plugins.txt`/`Skyrim.ccc` que não o lista mais) tem seu
`cache/game_data/plugins/<nome>.json` apagado na próxima vez que os
snapshots são salvos, em vez de ficar pra sempre no diretório de cache.

Só o CLI chama `scan_game_data` — é o único processo com um
`game_directory` local pra ler arquivos `.esm`/`.esp`/`.esl`/`.bsa`.

### 3.2 Lendo o cache

`AlchemyOptimizer.__init__` chama `load_cached_game_data`
(`app/game_data/__init__.py`), que só lê `ingredients.json`/`effects.json`
— nunca escaneia, e nunca toca em `cache/game_data/plugins/` de forma
nenhuma (esse diretório existe só pra deixar o próprio `scan_game_data`
mais rápido; nada fora de `app/game_data/_scan.py` o lê). Se
`cache/game_data/ingredients.json` ainda não existir, `load_cached_game_data`
levanta `GameDataNotCachedError`; a API (`app/api.py`) deixa isso propagar
pra um `RuntimeError` no momento do import, então o processo falha alto e
claro no startup em vez de servir requisições com um banco vazio. Rode o
CLI com `--refresh` contra uma instalação local do Skyrim primeiro pra
popular o cache:

```bash
uv run python cli.py --refresh
```

Para pegar mudanças depois de instalar/remover/reordenar plugins, rode de
novo com `--refresh` — não há endpoint ou flag separado de limpeza de
cache; pela [seção 3.1](#31-scan-incremental), um plugin sem mudança nunca
é reprocessado, então um refresh é barato mesmo com muitos plugins
instalados. `force=True` (o efeito de fato do `--refresh`) ainda reprocessa
todo plugin do zero e reescreve todo arquivo sob
`cache/game_data/plugins/`, ignorando todo snapshot em cache — use se o
cache em si for suspeito de estar desatualizado ou corrompido, embora o
arquivo de cache malformado de um plugin individual já seja tratado de
forma graciosa sozinho (tratado como ausente, forçando só aquele plugin a
ser reescaneado sem precisar de `--refresh` explicitamente).
