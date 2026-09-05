# Dados de ingredientes e efeitos (leitura binária dos plugins)

Este documento descreve de onde vêm os dados de ingredientes e efeitos do
projeto: os próprios dados binários de todo plugin ativo do Skyrim, lidos
diretamente. Sem wiki, sem raspagem, sem requisições HTTP.

Só a ferramenta de linha de comando escaneia a instalação do jogo e
escreve o cache. É o único processo que tem um caminho local pro jogo. O
otimizador e a API só leem o cache. Veja a seção 3 pro que acontece
quando esse cache está faltando.

## 1. Ingredientes

Todo ingrediente na load order ativa vira parte do banco de ingredientes,
construído a partir do próprio registro binário.

| Atributo | Vem de | Notas |
| :--- | :--- | :--- |
| Nome | O campo de texto de exibição do registro | Texto literal, ou um id de string localizada resolvido contra os dados de string empacotados do próprio plugin que define o registro; veja a seção 1.2 |
| Efeitos | Até 4 pares de entradas no registro, um por efeito | Cada par é uma struct de 12 bytes com a magnitude do efeito, um valor de área não usado, e uma duration, exatamente como aquele ingrediente produz. Não existe base compartilhada da qual isso seja relativo; veja a seção 1 do documento [de cálculo](../calculation/CALCULATION.md) |
| Plugin de origem e FormID | A identidade própria do registro após a resolução de override | Identifica o registro autoritativo, pós-override, do ingrediente; veja a seção 1.1 |

No momento desta escrita, um scan completo de uma instalação real com
mods produz 218 ingredientes. Isso não está fixado em nenhum lugar: é o
que a load order ativa de fato contém, e é o limite superior prático de
quantos tipos de ingrediente distintos o otimizador poderia ver, o que
importa pro seu pior caso de contagem de combinações; veja a seção 8.1 do
documento [de cálculo](../calculation/CALCULATION.md).

### 1.1 Resolução de override

O formato de plugin do Skyrim deixa um plugin mais tarde na load order
redefinir o registro de um plugin anterior reusando seu FormID: um
override genuíno, não um item novo.

1. Os próprios registros de ingrediente e efeito de cada plugin são
   primeiro parseados isoladamente num snapshot por plugin; veja o
   documento [Plugin Cache](../cache/plugin/PLUGIN_CACHE.md) pro porquê disso
   ser cacheável por plugin.
2. A load order inteira é então percorrida uma vez, masters vanilla,
   depois conteúdo de Creation Club (veja a seção 1.3), depois a própria
   lista de plugins ativos do usuário, nessa ordem, e todo registro é
   indexado pela sua identidade canônica.
3. Um plugin mais tarde na load order simplesmente sobrescreve a entrada
   do índice pra um FormID que um plugin anterior já definiu, então o
   índice acaba guardando só a versão final e autoritativa de cada
   registro, exatamente como o próprio motor do jogo resolve overrides.

Veja o documento [dados do jogo](../game_data/GAME_DATA.md) pra mecânica
completa, incluindo o risco de colisão de nome que decorre disso.

O plugin de origem e o FormID registrados de um ingrediente ou efeito
refletem essa versão autoritativa, não necessariamente o plugin que
originalmente introduziu o item. Um ingrediente originalmente adicionado
por um plugin de Creation Club, mas desde então corrigido por um patch de
compatibilidade da comunidade amplamente usado, reporta esse patch como
sua origem.

### 1.2 Strings localizadas e o fallback de arquivo das DLC

O campo de texto de exibição de um registro pode ter uma de duas formas:

| Forma | Onde o texto vive |
| :--- | :--- |
| Texto literal | Direto no registro |
| Id numérico de string localizada | Um arquivo de strings dentro do arquivo empacotado do próprio plugin que define o registro |

Vários dos próprios add-ons oficiais do Skyrim Special Edition vêm sem
arquivo próprio nenhum. As strings deles vêm embutidas dentro do próprio
arquivo de interface do jogo base, sob o próprio stem de cada add-on.
Resolver as strings de um plugin cai de volta pros próprios arquivos do
jogo base sempre que a busca por stem do próprio plugin não encontra
nada, o que cobre isso sem fixar o nome de nenhuma DLC específica.

### 1.3 Creation Club e sua própria lista de carregamento

Conteúdo de Creation Club não é listado na própria lista de plugins
ativos do usuário do jeito que um mod comum é. O motor do jogo carrega
automaticamente o que estiver listado num arquivo separado, de texto
puro, na própria raiz de instalação do jogo, um plugin por linha, não
qualquer perfil de gerenciador de mods, independentemente da própria
lista de plugins ativos do usuário. Um gerenciador de mods popular só
lista conteúdo de Creation Club como uma entrada de ordenação de
prioridade, sem relação com se o plugin de fato carrega, então esse
arquivo separado é a única fonte confiável de qual conteúdo de Creation
Club está de fato ativo.

Esse arquivo separado, e a lista de masters vanilla, nomeiam plugins com
a própria grafia de caixa mista do publicador, que não necessariamente
bate com o nome de arquivo real em disco num sistema de arquivos sensível
a maiúsculas/minúsculas; uma biblioteca da Steam compartilhada com
Windows e montada no Linux costuma ser um desses.

| | Comportamento |
| :--- | :--- |
| Checagem de existência ingênua contra a grafia publicada | Derruba o plugin do scan inteiro silenciosamente quando os dois diferem, junto com qualquer um de seus ingredientes não sobrescrito por outro plugin ativo |
| Tratamento atual | Constrói um mapa de nome-em-minúsculas para nome-real-em-disco uma vez por execução, e resolve todo nome de plugin de qualquer uma dessas listas através dele antes de adicioná-lo à load order |

Isso sempre abre arquivos pela própria grafia real e exata deles,
independente de qual grafia a lista de origem usou.

### 1.4 Risco de colisão de nome

Dois registros não relacionados, FormIDs diferentes, sem relação de
override, ainda podem coincidentemente resolver pro mesmo nome de
exibição. Esse é um risco real, ainda que raro, inerente a indexar o
banco final por nome em vez de por FormID. Veja o documento
[dados do jogo](../game_data/GAME_DATA.md) pra explicação completa.

## 2. Efeitos

Um efeito só é adicionado ao banco de efeitos quando de fato é
referenciado por algum ingrediente. O jogo define muitos milhares de
registros de efeito sem relação com alquimia, encantamentos, habilidades
de missão e roteirizadas, e por aí vai, e incluir cada um deles
incondicionalmente arriscaria um registro irrelevante sobrescrever
silenciosamente um efeito de alquimia real que aconteça de compartilhar
seu texto de exibição; veja a seção 2 do documento
[dados do jogo](../game_data/GAME_DATA.md).

| Atributo | Vem de |
| :--- | :--- |
| Custo base | Um float de 32 bits no registro |
| Harmful | Se os bits de flag harmful do registro estão setados, uma regra que bate com 205 efeitos conhecidos sem nenhuma incompatibilidade |

O valor de custo, e todo outro float lido de um plugin, incluindo a
própria magnitude e duration de cada ingrediente, é guardado exatamente
como o próprio valor binário do jogo decodifica, deliberadamente sem
arredondar. Um valor como `0.30000001192092896` pra um custo que uma
wiki mesma documenta como `0.3` não é corrupção. `0.3` não tem
representação binária de ponto flutuante exata, então os próprios bytes
binários do jogo decodificam pro mesmo valor representável mais próximo.
O objetivo é manter exatamente o valor que o próprio plugin guarda, não
uma aproximação arredondada mais bonita dele.

Não existe campo de magnitude ou duration num registro de efeito de
jeito nenhum. Veja a seção 2.1 do documento
[de cálculo](../calculation/CALCULATION.md) pra como custo e a flag
harmful se combinam com a própria magnitude e duration de cada
ingrediente.

## 3. Cache

O scan escreve três tipos de arquivo sob um diretório de cache dedicado:

| Arquivos | Conteúdo | Documento |
| :--- | :--- | :--- |
| Um arquivo pequeno por plugin | Os próprios resultados brutos de scan daquele plugin | [Plugin Cache](../cache/plugin/PLUGIN_CACHE.md) |
| `ingredients.json` | O banco de ingredientes mesclado e resolvido por override | [Ingredient Cache](../cache/ingredients/INGREDIENTS_CACHE.md) |
| `effects.json` | O banco de efeitos mesclado e resolvido por override | [Effect Cache](../cache/effects/EFFECTS_CACHE.md) |

O scan é incremental por plugin, não tudo-ou-nada. Um plugin cujos
próprios bytes não mudaram desde o último scan reusa seus dados em cache
tal como estão, e só os plugins que de fato mudaram são reprocessados.
Isso importa na prática, numa instalação real com cerca de 100 plugins
ativos:

| Scan | Tempo |
| :--- | :--- |
| Completo, todo plugin reprocessado | Cerca de 30 segundos |
| Rescan após tocar um único plugin | Cerca de 0,2 segundos |

Uma diferença de cerca de 150x, exatamente pro caso comum de
adicionar, atualizar ou remover um ou dois mods por vez.

Só a ferramenta de linha de comando dispara um scan. Se o cache ainda não
foi populado, popule-o primeiro rodando essa ferramenta com sua opção de
refresh contra uma instalação local do Skyrim:

```bash
uv run python cli.py --refresh
```

Pra captar mudanças depois de instalar, remover ou reordenar plugins,
rode de novo com essa mesma opção. Não existe um comando separado de
limpar cache. Um plugin inalterado nunca é reprocessado, então um
refresh é barato mesmo com muitos plugins instalados. O efeito real da
opção de refresh é ignorar todo snapshot em cache e reprocessar todo
plugin do zero, útil se o próprio cache algum dia for suspeito de estar
desatualizado ou corrompido, embora o arquivo em cache de um único
plugin malformado já seja tratado de forma graciosa por conta própria,
sem precisar de um refresh completo.
