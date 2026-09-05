🌐 [English](PLUGIN_CACHE.md) · [Português](PLUGIN_CACHE.pt.md) · [Deutsch](PLUGIN_CACHE.de.md)

# Plugin Cache

Este documento descreve o cache bruto de scan em disco, dos próprios
dados de ingrediente e efeito mágico de um único plugin: um arquivo
JSON pequeno por plugin ativo, em
`cache/game_data/plugins/<nome do plugin>.json`, nomeado a partir do
próprio plugin (por exemplo `Skyrim.esm.json`).

Cada arquivo guarda exatamente o que os próprios dados binários de um
plugin contêm: seus registros de ingrediente
([`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR)) e
de efeito mágico
([`MGEF`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/MGEF)),
já parseados e com nomes de exibição resolvidos. Existe puramente pra
tornar o rescan rápido. Enquanto os próprios bytes de um plugin não
mudarem, o arquivo aqui pode ser reusado sem reabrir ou reparsear
aquele plugin de jeito nenhum.

## 1. Estrutura

```jsonc
{
  "signature": {
    "size": 249752131,
    "mtime": 1787841633.526221
  },
  "ingredients": [
    {
      "owner_file": "Skyrim.esm",
      "local_id": 1076764,
      "form_id": "00106E1C",
      "name": "Silverside Perch",
      "effect_refs": [
        {
          "effect_owner_file": "Skyrim.esm",
          "effect_local_id": 256790,
          "magnitude": 5.0,
          "duration": 0.0
        }
        // até 4 entradas, uma por efeito que o ingrediente tem
      ]
    }
    // uma entrada por ingrediente que este plugin define ou sobrescreve
  ],
  "effects": [
    {
      "owner_file": "Skyrim.esm",
      "local_id": 95196,
      "form_id": "000173DC",
      "name": "Banish - Damage Health",
      "cost": 0.0,
      "harmful": true
    }
    // uma entrada por efeito mágico que este plugin define ou sobrescreve
  ]
}
```

(Trecho real, truncado, de um arquivo de cache `Skyrim.esm.json`.)

### 1.1 Signature

A signature não é um hash de conteúdo: é o tamanho em bytes e a hora de
última modificação do arquivo do plugin, registrados no momento em que
este arquivo foi escaneado. Uma checagem simples de sistema de arquivos
contra esses dois números, barata o bastante pra rodar a cada scan sem
abrir o próprio plugin, já basta pra dizer se o plugin mudou desde
então. Qualquer edição real no plugin, uma atualização de mod ou um
patch aplicado numa ferramenta de edição, muda pelo menos um dos dois
valores.

Um plugin listado como ativo mas que não está de fato presente em disco
(uma situação rotineira sob gerenciadores de mod que listam um plugin
como ativo sem copiar fisicamente seu arquivo pra pasta de dados do
jogo) recebe uma signature `size: -1, mtime: -1.0` em vez disso, junto
com listas `ingredients` e `effects` vazias. Esse valor sentinela
impede que todo scan futuro fique repetidamente tentando, e falhando,
ler um plugin que simplesmente nunca vai ser encontrado em disco.

### 1.2 Ingredients

Uma entrada por ingrediente que este plugin define ou sobrescreve.

| Campo | Lido de | Significado |
| :--- | :--- | :--- |
| `owner_file` | O próprio FormID do registro `INGR`, byte 3 (índice de master), resolvido contra a lista de masters deste plugin | O plugin que de fato define este ingrediente, não necessariamente o plugin a quem este arquivo de cache pertence. Se este plugin só sobrescreve um ingrediente que um master originalmente criou, `owner_file` nomeia esse master em vez disso. Se este plugin criou o ingrediente originalmente, ele nomeia a si mesmo. |
| `local_id` | O próprio FormID do registro `INGR`, bytes 2-0 | Um identificador numérico estável pro ingrediente, único junto com `owner_file`. Diferente de um FormID bruto, esse valor não muda dependendo de qual plugin está referenciando. Veja a seção 2.1 pro porquê. |
| `form_id` | O próprio FormID do registro `INGR`, todos os 4 bytes, sem modificação | O FormID do ingrediente exatamente como o próprio registro deste plugin específico guarda, útil pra cross-checar contra uma ferramenta de edição de plugin. |
| `name` | Sub-registro `FULL` (texto literal, ou uma busca em tabela de string pra um plugin localizado) | O nome de exibição do ingrediente, exatamente como o jogo mostra. |
| `effect_refs` | Um par de sub-registro `EFID`/`EFIT` por entrada | Até 4 entradas, uma por efeito que este ingrediente produz. |

Cada entrada de `effect_refs` descreve um efeito que o ingrediente
produz, com a força própria daquele ingrediente pra ele.

| Campo | Lido de | Significado |
| :--- | :--- | :--- |
| `effect_owner_file` | `EFID`, byte 3 (índice de master), resolvido contra a lista de masters deste plugin | O plugin onde o efeito mágico é definido. |
| `effect_local_id` | `EFID`, bytes 2-0 | O identificador numérico estável pro efeito mágico. |
| `magnitude` | Sub-registro `EFIT`, bytes 0-3 (float de 32 bits) | O quão forte é a versão deste ingrediente pra esse efeito. |
| `duration` | Sub-registro `EFIT`, bytes 8-11 (inteiro de 32 bits) | Quanto tempo dura a versão deste ingrediente pra esse efeito. |

### 1.3 Effects

Uma entrada por efeito mágico que este plugin define ou sobrescreve,
todo aquele que existe neste plugin, seja ou não um ingrediente de fato
o usando.

| Campo | Lido de | Significado |
| :--- | :--- | :--- |
| `owner_file` | O próprio FormID do registro `MGEF`, byte 3 (índice de master), resolvido contra a lista de masters deste plugin | O plugin que de fato define este efeito mágico, não necessariamente o plugin a quem este arquivo de cache pertence. Mesma regra de override que `owner_file` de um ingrediente. |
| `local_id` | O próprio FormID do registro `MGEF`, bytes 2-0 | Um identificador numérico estável pro efeito mágico, único junto com `owner_file`. |
| `form_id` | O próprio FormID do registro `MGEF`, todos os 4 bytes, sem modificação | O FormID do efeito como lido deste plugin. |
| `name` | Sub-registro `FULL` | O nome de exibição do efeito. |
| `cost` | Sub-registro `DATA`, bytes 4-7 (float de 32 bits) | O custo base do efeito, uma propriedade real do próprio efeito, usada ao valorar uma poção. |
| `harmful` | Sub-registro `DATA`, bytes 0-3 (flags de 32 bits), bit `0x01` (Hostile) ou `0x04` (Detrimental) | Se o jogo classifica isso como um efeito harmful, tipo veneno. Verdadeiro se qualquer um dos bits estiver setado. |

## 2. De onde esses valores de fato vêm

Nenhum dos campos acima é um valor que este projeto inventa: todos são
derivados de bytes que o próprio formato de plugin da Bethesda já
define. Este projeto não escolhe como um FormID é estruturado ou como
dados de efeito são organizados; ele lê o que já está lá.

### 2.1 FormIDs e identidade local

Todo registro, um ingrediente, um efeito mágico, qualquer um, tem um
FormID de 4 bytes, dividido em duas partes: o byte mais alto é um
índice de master, identificando a posição do plugin que define aquilo
na lista de masters do próprio plugin deste registro, e os 3 bytes
mais baixos são o id numérico real do registro.

O byte de índice de master é a pegadinha: é um índice numa lista que é
diferente pra cada plugin, já que cada plugin declara seus próprios
masters, na própria ordem. O mesmo registro exato pode, portanto, ter
um FormID bruto completamente diferente dependendo de qual plugin está
apontando pra ele. O byte de índice de master só faz sentido junto com
a lista de masters daquele plugin específico.

`owner_file` e `local_id` contornam isso. `local_id` é só os 3 bytes
mais baixos, a parte que nunca depende da lista de masters de nenhum
plugin em particular, e `owner_file` é o nome de arquivo real pra onde
o byte de índice de master apontava, resolvido uma vez pra esta entrada
de cache usando a própria lista de masters deste plugin. Juntos,
`owner_file` e `local_id` identificam um registro do mesmo jeito não
importa qual plugin esteja referenciando, que é exatamente o que é
preciso pra reconhecer que dois plugins diferentes estão se referindo
ao mesmo ingrediente ou efeito. O campo `form_id` bruto é mantido junto
principalmente pra que os bytes exatos que este plugin em si guardou
ainda possam ser cross-checados contra uma ferramenta de edição de
plugin.

### 2.2 Os dados de efeito próprios de um ingrediente

Os até 4 efeitos de um ingrediente vêm de até 4 pares de entradas dentro
do próprio registro: uma entrada `EFID` (o FormID do efeito referenciado,
dividido do mesmo jeito de acima) imediatamente seguida por uma entrada
`EFIT` (12 bytes: uma magnitude de 32 bits, uma área de 32 bits, e uma
duration de 32 bits, nessa ordem).

`magnitude` e `duration` são lidos direto desses bytes, exatamente como
o jogo os guarda, sem nenhum escalonamento ou arredondamento aplicado;
esse é o único lugar de onde qualquer um dos dois valores vem. Não
existe uma magnitude ou duration base separada em nenhum lugar do
formato de plugin da qual esses sejam relativos. Os próprios bytes de
`EFIT` de cada ingrediente já são o valor completo e absoluto. O campo
de área existe na mesma estrutura mas não tem efeito no valor da poção
nos próprios cálculos deste projeto, então é lido e imediatamente
descartado.

A mesma estrutura `DATA` subjacente é também como os próprios campos
`cost` e `harmful` de um efeito mágico são lidos, no próprio registro
`MGEF`, e não a partir de nenhum ingrediente. Veja o documento
[Effect Cache](../effects/EFFECTS_CACHE.md) pra esse layout.

## 3. Como é populado

Um scan percorre a lista completa de plugins ativos, na ordem em que o
próprio jogo os carregaria. Pra cada um, ele calcula a signature atual
daquele plugin e a compara contra o que já está em cache.

Se a signature está inalterada desde a última vez, o arquivo em cache é
reusado exatamente como está: os próprios dados binários do plugin
nunca são reabertos, e este arquivo fica intocado em disco. Se a
signature mudou, ou nada foi cacheado antes, os dados binários do
plugin (e seus arquivos de recurso empacotados, pra qualquer texto
guardado fora do próprio plugin) são lidos de novo, e uma nova versão
deste arquivo substitui a antiga. Se o plugin está listado como ativo
mas faltando em disco, um snapshot vazio é escrito em vez disso, com a
signature sentinela da seção 1.1.

Uma vez que todo plugin ativo tem um snapshot atualizado desse jeito,
um plugin que não faz mais parte da lista ativa de jeito nenhum, um mod
que foi desinstalado ou simplesmente desativado, tem seu arquivo de
cache remanescente deletado em vez de deixado pra trás indefinidamente.

Como só os plugins que de fato mudaram são reprocessados, um rescan
depois de uma pequena mudança, um mod adicionado ou atualizado, só
toca o arquivo daquele mod e termina quase instantaneamente, em vez de
reprocessar todo plugin ativo toda vez. Um rescan completo, do zero, de
tudo ainda pode ser forçado quando necessário, por exemplo se o próprio
cache algum dia for suspeito de estar corrompido ou fora de sincronia.
