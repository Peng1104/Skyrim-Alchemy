# Dependências de leitura binária

Este documento descreve um risco assumido conscientemente por este
projeto. As duas bibliotecas de terceiros das quais o scan de dados do
jogo depende pra ler os próprios formatos binários do Skyrim são
relativamente novas e pouco usadas, e este documento registra o que foi
verificado sobre elas, e o que acontece se um plugin ou arquivo bater
numa variação de formato que elas não cobrem.

## 1. O que cada biblioteca faz, e por que o risco existe

A [`sse-plugin-interface`](https://github.com/cutleast/sse-plugin-interface)
parseia os próprios arquivos de plugin: estrutura de registro e
sub-registro, headers, listas de masters, FormIDs.
A [`sse-bsa`](https://github.com/cutleast/sse-bsa) parseia os arquivos
de recurso empacotados do jogo, usados pra extrair arquivos de texto
localizado (veja a seção 1.2 do documento
[fontes de dados](../data-sources/DATA_SOURCES.md)).

As duas são implementações puramente Python dos próprios formatos
binários não documentados e engenheirados por engenharia reversa da
Bethesda, mantidas pelo mesmo autor,
[cutleast](https://github.com/cutleast), como projetos open-source
pequenos com relativamente poucas contribuições comparado a uma
biblioteca de propósito geral amplamente usada. Isso é um risco real
pra um projeto que agora depende delas pra sua única fonte de dados de
ingredientes e efeitos (veja o documento
[fontes de dados](../data-sources/DATA_SOURCES.md)). Uma variação de
formato que nenhuma das duas bibliotecas trata poderia produzir dados
errados ou faltando silenciosamente em vez de um erro limpo, se nada
mais estivesse guardando contra isso.

## 2. O que foi de fato verificado

Isso não foi aceito por fé. As duas bibliotecas foram exercitadas de
ponta a ponta contra os dois casos reais que mais importam na prática,
numa instalação real, pesadamente modificada, com cerca de 170 plugins
ativos.

| | Tipo de plugin | Codificação do texto de exibição | Biblioteca exercitada |
| :--- | :--- | :--- | :--- |
| Caso 1 | Mod pequeno, não oficial, não localizado (uma criação hobby, não um lançamento oficial da Bethesda ou de Creation Club) | Texto literal, guardado direto no registro, sem nenhum arquivo envolvido | Só a biblioteca de parsing de plugin |
| Caso 2 | Lançamento oficial e localizado de Creation Club | Id numérico de string localizada, resolvido através do próprio arquivo empacotado do plugin | A biblioteca de parsing de plugin e a de parsing de arquivo juntas |

Os dois casos bateram com as expectativas exatamente, verificados
contra nomes de ingrediente e valores de efeito conhecidos, e pro caso
de Creation Club, cross-referenciados contra a própria saída de FormID
de um comando de console do jogo. Combinado com um scan completo de 218
ingredientes e 65 efeitos por todo plugin numa load order real batendo
com valores de referência conhecidos, vanilla, DLC, e vários outros
ingredientes de Creation Club e de mod verificados individualmente,
isso cobre as duas formas estruturalmente diferentes que o texto de
exibição pode ser codificado, que é o eixo real de risco pra essas
bibliotecas, não o polimento ou tamanho de nenhum plugin específico.

## 3. O que acontece quando uma variação não é coberta

Nada foi observado que essas bibliotecas falhem em parsear. O
scanner é deliberadamente construído de forma que, se algum dia isso
acontecer, ele falha alto pra aquele ingrediente específico, nunca
silenciosamente.

| Falha | Comportamento |
| :--- | :--- |
| O nome de exibição de um registro não pode ser resolvido (uma entrada de string faltando, um arquivo não parseável, ou qualquer outra causa) | Colapsa pro mesmo resultado vazio, nunca um chute errado. O ingrediente é logado, com o próprio identificador interno e o plugin que o define, pra ser rastreável, e pulado. Ele nunca entra no banco final de ingredientes com um nome errado ou em branco. |
| Um plugin falha em carregar de jeito nenhum (um arquivo genuinamente corrompido ou não suportado) | Logado, e aquele plugin inteiro é pulado, o mesmo princípio numa granularidade mais grossa. |

Nos dois casos o scan continua pra todo outro plugin e ingrediente. Um
registro ou plugin não parseável não aborta a execução inteira, e a
falha está sempre visível na saída de console ou log, nunca engolida.

## 4. Fixação de versão

A lista de dependências do projeto atualmente declara limites
inferiores em aberto pras duas bibliotecas, e o lockfile resolve isso
pra versões exatas, então uma instalação normal já é reproduzível. O
limite em aberto em si, porém, não impede que uma futura atualização de
dependência puxe silenciosamente uma versão major mais nova de
qualquer uma das duas bibliotecas sem uma decisão deliberada de fazê-lo.
Pra maioria das dependências isso é tranquilo, mas pra duas bibliotecas
das quais este projeto não tem fallback nenhum, não tem mais wiki pra
recorrer, e que são mantidas por projetos pequenos e de baixa
atividade, um bump de versão major não revisado é exatamente o tipo de
mudança que deveria exigir uma decisão consciente, não acontecer como
efeito colateral de atualizar um pacote não relacionado. Fixar essas
duas na próxima vez que qualquer uma delas for tocada garantiria que um
bump de versão pra essas duas especificamente sempre passe por uma
mudança explícita e revisada.
