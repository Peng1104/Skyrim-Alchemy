🌐 [English](INGREDIENTS_CACHE.md) · [Português](INGREDIENTS_CACHE.pt.md) · [Deutsch](INGREDIENTS_CACHE.de.md)

# Ingredient Cache

Este documento descreve o cache em disco que guarda o banco de dados
final e completo de ingredientes, em `cache/game_data/ingredients.json`:
todo ingrediente de todo plugin ativo, já resolvido pra única versão
que de fato conta (a seção 2 explica o que "resolvido" quer dizer
aqui). Este é o arquivo que o resto da aplicação lê. O otimizador, a
API, tudo que vem depois do scan de dados do jogo passa por este
arquivo, nunca pelos dados brutos por plugin dos quais ele é
construído (veja o documento [Plugin Cache](../plugin/PLUGIN_CACHE.md)).

No momento desta escrita, um scan completo de uma instalação real com
mods produz 218 ingredientes, não um número fixo, só o que os plugins
ativos de fato contêm.

## 1. Estrutura

Um objeto JSON mapeando o nome de exibição de cada ingrediente pros
seus dados.

```jsonc
{
  "Silverside Perch": {
    "name": "Silverside Perch",
    "effects": [
      {
        "name": "Restore Stamina",
        "magnitude": 5.0,
        "duration": 0.0
      },
      {
        "name": "Damage Stamina Regen",
        "magnitude": 100.0,
        "duration": 5.0
      }
      // até 4 efeitos no total
    ],
    "source_file": "Skyrim.esm",
    "form_id": "00106E1C"
  }
  // uma entrada por ingrediente
}
```

(Trecho real, truncado.)

| Campo | Significado |
| :--- | :--- |
| `name` | O nome de exibição do ingrediente, também a chave sob a qual ele é guardado. |
| `effects` | Até 4 efeitos que este ingrediente produz. A `magnitude` e a `duration` de cada um são a força real própria deste ingrediente específico pra aquele efeito, nunca arredondadas e nunca relativas a nenhuma base compartilhada: nenhuma base assim existe nos próprios dados do jogo, então dois ingredientes podem listar números bem diferentes pro que parece ser o mesmo efeito. O `name` aqui é o nome de exibição resolvido do efeito, já cross-referenciado contra qualquer plugin que defina aquele efeito. |
| `source_file` | Qual versão deste ingrediente é a que de fato vale, não necessariamente o plugin que originalmente o introduziu. Se um mod posterior, ou um patch de compatibilidade, sobrescreve o ingrediente de um plugin anterior, isso nomeia esse plugin posterior em vez disso. Só informativo: nada no cálculo usa este campo, ele existe pra rastrear de onde vêm os números de um ingrediente. |
| `form_id` | O próprio identificador do plugin vencedor pro ingrediente. Também só informativo. |

## 2. Identidade nos bastidores

Este arquivo em si não expõe a identidade de plugin subjacente do
ingrediente: ele indexa tudo por nome de exibição em vez disso, já que
é isso que o resto da aplicação precisa pra bater (um ingrediente
reconhecido a partir de uma screenshot, por exemplo, é batido pelo
nome). Internamente, antes deste arquivo ser construído, todo
ingrediente e efeito é rastreado por uma identidade mais precisa: qual
plugin de fato o define, mais um id numérico que permanece estável
independente de qual outro plugin esteja o referenciando (veja a seção
2.1 do documento [Plugin Cache](../plugin/PLUGIN_CACHE.md)). Essa identidade
precisa é o que permite que um ingrediente sobrescrito por cinco mods
diferentes ainda resolva pra exatamente uma entrada aqui, a que
pertence a qualquer um desses mods que carregue por último, em vez de
cinco entradas separadas e conflitantes.

Indexar o resultado final por nome em vez de por essa identidade
subjacente carrega uma desvantagem real, ainda que rara. Dois
ingredientes ou efeitos genuinamente não relacionados, sem relação de
override entre eles, poderiam em princípio compartilhar exatamente o
mesmo texto de exibição e colidir aqui, um sobrescrevendo o outro
silenciosamente. Isso não é hipotético: já foi observado na prática,
sempre com um efeito definido pra algo totalmente não relacionado a
alquimia, um script de missão por exemplo, que aconteceu de reusar um
nome já usado por um efeito de alquimia real.

## 3. Como é populado

Construído assim que os próprios dados por plugin de todo plugin ativo
estão disponíveis, recém-escaneados ou reusados de antes. Duas coisas
acontecem, puramente combinando dados já em disco. Nenhum arquivo de
plugin é reaberto nesta etapa.

Primeiro, um vencedor é escolhido pra todo ingrediente e efeito.
Plugins são percorridos na load order, e sempre que dois plugins
definem ou sobrescrevem o mesmo ingrediente ou efeito, o que carrega
por último vence, exatamente como o próprio jogo resolve esses
conflitos. O que sobra depois é exatamente uma versão de todo
ingrediente e efeito, a que de fato está em jogo.

Segundo, os efeitos de cada ingrediente são anexados por nome. Cada
ingrediente vencedor ainda só aponta pros próprios efeitos por
identificador nesta etapa. Cada um desses apontadores é buscado contra
os efeitos vencedores da primeira etapa pra preencher o nome de
exibição real do efeito. Um apontador que não resolve pra nenhum efeito
conhecido, porque o plugin que o define nunca foi escaneado por
exemplo, é simplesmente descartado daquele ingrediente em vez de
derrubar o scan inteiro.

Este arquivo e o [Effect Cache](../effects/EFFECTS_CACHE.md) são sempre
produzidos e escritos juntos, na mesma passada. Não existe cenário onde
um é atualizado sem o outro.

### 3.1 Quando é de fato reescrito

Se nada mudou desde o scan anterior, nenhum dado próprio de plugin
ativo mudou, e a própria lista de plugins ativos é a mesma, essa etapa
é pulada por completo e o arquivo existente é reusado tal como está.
Qualquer mudança real em qualquer lugar, dados de um plugin mudaram ou
um mod foi adicionado ou removido, faz o arquivo inteiro ser
reconstruído do zero. Não existe atualização parcial. Diferente do
cache por plugin, este arquivo não rastreia quais ingredientes
individuais mudaram: ele é sempre regenerado por completo a partir de
qualquer que seja o retrato atual e completo.

## 4. Quem o lê

Este é o banco de dados que o resto da aplicação de fato usa, carregado
uma única vez quando o otimizador inicia. É uma leitura pura: nada que
consome este arquivo dispara um scan por conta própria, então funciona
bem mesmo num lugar sem acesso à instalação real do jogo. Se este
arquivo ainda não existir de jeito nenhum, isso é tratado como um erro
grave, já que nada na aplicação consegue funcionar sem um banco de
ingredientes, então a inicialização falha alto em vez de rodar
silenciosamente com um banco vazio. O [Effect Cache](../effects/EFFECTS_CACHE.md)
companheiro é tratado de forma mais tolerante se for ele que estiver
faltando; veja aquele documento pro porquê.
