# Dados de ingredientes e efeitos (scraping da UESP)

Este documento descreve de onde vêm os dados de ingredientes e efeitos do
projeto, e como são raspados (scraped) e armazenados em cache. A
implementação de referência está em `app/scraping/` (`_ingredients.py`,
`_effects.py`, `_effect_priorities.py`, `_http_cache.py`).

Existem dois conjuntos de dados, ambos raspados da [UESP](https://en.uesp.net/)
(Unofficial Elder Scrolls Pages) e ambos carregados uma vez por instância de
`AlchemyOptimizer` (`app/optimizer/_engine.py`), via `get_ingredients_data()`
e `get_effects_data()` (`app/scraping/__init__.py`).

## 1. Ingredientes

Fonte: [Skyrim:Ingredients](https://en.uesp.net/wiki/Skyrim:Ingredients).

`app/scraping/_ingredients.py` percorre com BeautifulSoup toda
`table.wikitable.striped2_1` da página. Cada ingrediente ocupa **duas linhas
consecutivas** da tabela:

- A primeira linha (identificada por ter um atributo `id`) contém o nome do
  ingrediente, extraído do texto do link na segunda célula.
- A linha logo em seguida tem até 4 células, uma por efeito que o
  ingrediente pode produzir. O texto do link de cada célula é o nome do
  efeito; se a célula também mostra um ícone de modificador
  `Value`/`Magnitude`/`Duration` (um multiplicador não padrão para aquele
  par específico ingrediente/efeito), o valor em `<b>` que precede o ícone é
  capturado como o fator daquele modificador (`get_modifiers`).

Isso produz um `dict[str, Ingredient]` — cada `Ingredient` tem um nome e uma
lista de até 4 `IngredientEffect`s, cada um com um mapa opcional
`{Modifier: fator}`.

## 2. Efeitos

Fonte: [Skyrim:Alchemy Effects](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects).

`app/scraping/_effects.py` percorre toda `table.wikitable.sortable` da
página. Para cada linha, lê o nome do efeito, o `cost` base, a `magnitude`
base e a `duration` base a partir de posições fixas de coluna, e deriva
`harmful` a partir da classe CSS da linha: a UESP marca linhas de efeitos
nocivos (do tipo veneno) com `EffectNeg`, e as benéficas com `EffectPos`.

### 2.1 Prioridades específicas por efeito

Alguns poucos efeitos (*Damage Health* sendo o mais notável) têm
ingredientes com magnitude/duração não padrão especificamente para aquele
efeito — veja a
[seção 2 do documento de cálculo](../calculation/CALCULATION.pt.md#2-resolução-de-prioridade-entre-ingredientes)
para entender por que isso importa. `app/scraping/_effect_priorities.py`
busca a página wiki própria de cada efeito
(`https://en.uesp.net/wiki/Skyrim:<Nome_Do_Efeito_Com_Underscores>`) e
procura por uma tabela com colunas `Priority`/`Base Mag`/`Base Dur`. Quando
presente, todo ingrediente com uma `Priority` não vazia recebe uma entrada
em `Effect.priority_overrides`, mapeando seu nome para
`(magnitude_ratio, duration_ratio)` — sua magnitude/duração base dividida
pelas do efeito padrão. A maioria dos efeitos não tem tal tabela, e acaba
sem nenhum override.

Isso roda uma vez por efeito depois que a tabela principal de efeitos é
processada, então carregar os dados de efeitos custa uma busca de página
para a tabela de efeitos mais uma busca por efeito (tudo em cache — veja
abaixo).

## 3. Cache

`download_data()`, em `app/scraping/_http_cache.py`, envolve toda busca: na
primeira requisição para uma URL, ela baixa a página e grava o HTML bruto em
`cache/pages/<caminho-após-o-domínio>.html` (ex.: `Ingredients.html`,
`Alchemy_Effects.html`, `Damage_Health.html`); toda chamada seguinte para a
mesma URL lê diretamente desse arquivo, sem requisição de rede. Não há
verificação de validade ou expiração — uma vez em cache, uma página nunca é
baixada de novo por conta própria.

Para pegar mudanças feitas na UESP, apague o cache e deixe a próxima
execução buscar tudo de novo:

```bash
rm -rf cache/pages/            # CLI - força uma nova raspagem na próxima execução
```

```bash
curl -X DELETE http://localhost:8001/cache/pages   # API - mesmo efeito
```

Ambos removem toda página em cache indiscriminadamente (ingredientes, a
tabela de efeitos, e cada página de prioridade por efeito) — não há como
invalidar apenas uma.
