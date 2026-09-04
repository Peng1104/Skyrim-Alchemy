# Dependências de leitura binária: `sse-plugin-interface` e `sse-bsa`

Este documento descreve um risco assumido conscientemente por este
projeto: as duas bibliotecas de terceiros das quais `app/game_data/`
depende pra ler os próprios formatos binários do Skyrim são ambas
relativamente novas e pouco usadas, e este documento registra exatamente o
que foi verificado sobre elas, e o que acontece se um plugin ou BSA
esbarrar numa variação de formato que elas não cobrem.

## 1. O que cada biblioteca faz, e por que o risco existe

- **`sse-plugin-interface`** (`app/game_data/_plugin_records.py`) faz o
  parse de arquivos de plugin `.esp`/`.esm`/`.esl`: estrutura de
  registro/subrecord, headers `TES4`, listas de masters, `FormID`s.
- **`sse-bsa`** (`app/game_data/_bsa.py`) faz o parse de arquivos `.bsa`,
  usado pra extrair arquivos `.strings` de texto localizado (veja
  [DATA_SOURCES.pt.md §1.2](../data-sources/DATA_SOURCES.pt.md#12-strings-localizadas-e-o-fallback-de-bsa-das-dlc)).

Ambas são implementações puramente em Python dos formatos binários
não-documentados e feitos por engenharia reversa da Bethesda, mantidas por
projetos open-source pequenos, com relativamente poucos commits/estrelas
no GitHub comparado a, digamos, `pydantic` ou `requests`. Isso é um risco
real pra um projeto que agora depende delas como sua **única** fonte de
dados de ingredientes/efeitos (veja
[DATA_SOURCES.pt.md §0](../data-sources/DATA_SOURCES.pt.md#0-por-que-não-a-wiki))
— uma variação de formato que nenhuma das duas biblioteca trate poderia
produzir dado errado ou faltante silenciosamente em vez de um erro limpo,
se nada mais se protegesse contra isso.

## 2. O que foi de fato verificado

Isso não foi aceito por fé. As duas bibliotecas foram exercitadas ponta a
ponta nesta sessão contra os dois casos reais mais relevantes na prática,
numa instalação real fortemente modada (~170 plugins ativos):

- **Um mod pequeno, não-oficial, não-localizado**: `whitewind player
  home.esp` (um mod hobby, não um lançamento oficial da Bethesda/CC). A
  subrecord `FULL` do seu ingrediente guarda **texto literal**
  (`"Frozen Bee"`) direto no registro — sem BSA nenhum envolvido,
  exercitando o parse de registro/subrecord do `sse-plugin-interface`
  sozinho, num plugin construído por um pipeline completamente diferente,
  não-profissional, das próprias ferramentas da Bethesda.
- **Um lançamento oficial e localizado de Creation Club**:
  `ccbgssse037-curios.esl` (Curios). As subrecords `FULL` de seus
  ingredientes guardam **IDs numéricos de string localizada** (ex.: `7`),
  exigindo que o `sse-bsa` abra o `ccbgssse037-curios.bsa`, extraia
  `strings/ccbgssse037-curios_english.strings`, e o próprio tratamento de
  ID de string do `sse-plugin-interface` resolva o registro corretamente
  — exercitando as duas bibliotecas juntas, num plugin construído pelo
  próprio pipeline oficial da Bethesda.

Os dois casos bateram exatamente com o esperado (verificado contra nomes
de ingredientes conhecidos, valores de `EFIT`, e — especificamente pra
Curios — cruzado contra a própria saída de FormID de um comando `help` no
console do jogo, veja
[DATA_SOURCES.pt.md §1.3](../data-sources/DATA_SOURCES.pt.md#13-creation-club-e-skyrimccc)).
Combinado com o scan completo de 218 ingredientes/65 efeitos em todo plugin
de uma load order real batendo com valores de referência conhecidos
(vanilla, DLC, e vários outros ingredientes de CC/mod checados
individualmente durante o desenvolvimento desta sessão), isso cobre as duas
formas estruturalmente diferentes que uma subrecord `FULL` pode ser
codificada — que é o eixo real de risco pra essas bibliotecas, não o
polimento ou tamanho de um plugin específico qualquer.

## 3. O que acontece quando uma variação não é coberta

Nada foi observado que essas bibliotecas falhem em processar. Mas o
scanner é deliberadamente construído pra que, se algum dia isso aparecer,
falhe **alto e claro pra aquele único ingrediente**, nunca silenciosamente:

- `resolve_full` (`app/game_data/_strings.py`) retorna `None` sempre que
  não consegue resolver um valor `FULL` — uma entrada de `.strings`
  ausente, um BSA que não processa, ou qualquer outra falha colapsa pro
  mesmo `None`, nunca um chute errado.
- `_scan_plugin` (`app/game_data/_scan.py`) checa exatamente isso: um
  ingrediente cujo nome não resolve imprime
  `game_data_ingredient_unresolved` (com o `EDID` do registro e o plugin
  que o define, então é rastreável) e é **pulado** — nunca entra em
  `ingredients.json` com um nome errado ou vazio.
- Um plugin que falha em carregar completamente (`load_plugin` levantando
  exceção, ex.: um arquivo genuinamente corrompido ou não suportado)
  imprime `game_data_scan_plugin_unreadable` e aquele plugin inteiro é
  pulado, mesmo princípio numa granularidade mais grosseira.

Nos dois casos o scan continua pra todo outro plugin/ingrediente — um
registro ou plugin que não processa não aborta a execução inteira, e a
falha sempre fica visível na saída do console/log, nunca é engolida.

## 4. Fixação de versão

O `pyproject.toml` atualmente declara limites inferiores abertos:

```toml
"sse-plugin-interface>=1.0.1",
"sse-bsa>=1.1.0",
```

O `uv.lock` resolve isso pra versões exatas (`1.0.1` e `1.1.0` no momento
em que isso foi escrito) e o `uv sync` instala exatamente o que o lockfile
diz, então uma instalação normal já é reproduzível. O limite `>=` no
próprio `pyproject.toml`, porém, não impede que um `uv lock --upgrade`
futuro puxe silenciosamente uma versão major mais nova de qualquer uma das
duas bibliotecas sem uma decisão deliberada de fazer isso — pra maioria
das dependências isso é aceitável, mas pra duas bibliotecas das quais este
projeto não tem fallback nenhum (não tem mais wiki pra recorrer) e que são
mantidas por projetos pequenos e de baixa atividade, um bump major não
revisado é exatamente o tipo de mudança que deveria exigir uma decisão
consciente, não acontecer como efeito colateral de atualizar um pacote não
relacionado. Fixe-as com `==` em vez de `>=` na próxima vez que qualquer
uma delas for tocada, pra que um bump de versão dessas duas especificamente
sempre passe por uma edição explícita e revisada do `pyproject.toml`.
