# Referência da API HTTP

Este documento descreve todo endpoint HTTP exposto pelo projeto: o
serviço público app, e o serviço interno-apenas ocr. A Swagger UI
interativa também está disponível no próprio caminho `/docs` de cada
serviço enquanto ele está rodando.

```
Cliente --HTTP--> app (porta publicada) --rede interna--> ocr (sem porta publicada)
```

O serviço ocr não tem nenhuma porta publicada pro host. Só é alcançável
a partir do serviço app pela rede interna, e adicionalmente exige um
header de segredo compartilhado, descrito na seção 2.3. Nada fora dessa
rede interna consegue chamá-lo diretamente.

O serviço app constrói seu otimizador, e carrega o banco de
ingredientes e efeitos, uma única vez, na inicialização do processo.
Ele nunca escaneia arquivos de plugin ou de arquivo empacotado por
conta própria. Se o cache de dados do jogo ainda não foi populado, o
serviço app falha em iniciar de jeito nenhum, com um erro claro, em vez
de servir requisições contra um banco vazio. Veja a seção 3 do
documento [fontes de dados](../data-sources/DATA_SOURCES.md).

## 1. Serviço app (público)

### 1.1 GET /health

Checagem de liveness e readiness.

Requisição: sem parâmetros.

Resposta `200 OK`

```json
{ "status": "ok" }
```

### 1.2 POST /optimize/screenshots

O endpoint principal. Roda OCR em uma ou mais screenshots de inventário
enviadas e retorna a sequência ótima de fabricação de poções pros
ingredientes resultantes.

O OCR em si nunca roda neste processo. Cada arquivo enviado é validado
aqui, por magic bytes, tamanho e contagem, e então seus bytes brutos
são encaminhados pro serviço ocr isolado, seção 2.2, pela rede interna.
Perks são pegos estritamente do corpo da requisição, nunca de nenhuma
configuração compartilhada, então requisições concorrentes com seleções
de perk diferentes nunca interferem entre si.

Requisição: `multipart/form-data`

| Campo | Tipo | Obrigatório | Padrão | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `files` | array de arquivo | Sim | nenhum | Uma ou mais screenshots PNG. Quando um inventário se espalha por várias screenshots roladas, a leitura de um arquivo posterior pra um dado nome de ingrediente sobrescreve uma anterior: cada screenshot mostra o total atual do ingrediente, não um delta. |
| `perk_physician` | campo de formulário booleano | Não | `false` | Perk Physician ativo. |
| `perk_benefactor` | campo de formulário booleano | Não | `false` | Perk Benefactor ativo. |
| `perk_poisoner` | campo de formulário booleano | Não | `false` | Perk Poisoner ativo. |
| `perk_purity` | campo de formulário booleano | Não | `false` | Perk Purity ativo. |

Restrições de upload, aplicadas nesta ordem antes de qualquer coisa ser
enviada pro serviço ocr:

| Checagem | Limite | Falha |
| :--- | :--- | :--- |
| Contagem de arquivos | 20 ou menos | `400`, motivo `too_many_files` |
| Magic bytes | Deve ser PNG | `400`, motivo `invalid_type` |
| Tamanho do arquivo | 15 MiB ou menos por arquivo | `413`, motivo `too_large` |

A validação para no primeiro arquivo que falhar no lote. A requisição
inteira é rejeitada, nenhum dos arquivos é processado.

Resposta `200 OK`

```json
{
  "fabrication_sequence": [
    {
      "order": 1,
      "count": 3,
      "ingredients": ["Blue Mountain Flower", "Wheat"],
      "effects": ["Restore Health"],
      "value": 12.5
    }
  ],
  "remaining_ingredients": {
    "Blue Mountain Flower": 0,
    "Wheat": 1
  }
}
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `fabrication_sequence` | array | Poções a fabricar, em ordem. |
| `fabrication_sequence[].order` | inteiro | Posição, começando em 1, na sequência de fabricação. |
| `fabrication_sequence[].count` | inteiro | Quantas poções dessa receita fazer. |
| `fabrication_sequence[].ingredients` | array de string | Nomes de ingrediente usados por poção dessa receita. |
| `fabrication_sequence[].effects` | array de string | Efeitos compartilhados que essa receita produz. |
| `fabrication_sequence[].value` | número | Valor em ouro de uma poção dessa receita. |
| `remaining_ingredients` | objeto | Nome do ingrediente mapeado pra quantidade restante após a fabricação. |

Veja o documento [de cálculo](../calculation/CALCULATION.md) pra
exatamente como `value` e as receitas escolhidas são derivadas.

Respostas de erro:

| Status | Corpo | Causa |
| :--- | :--- | :--- |
| `400` | `{"detail": "No files uploaded."}` | O campo `files` estava vazio. |
| `400` | `{"detail": {"filename": "...", "reason": "too_many_files ou invalid_type"}}` | Lote de upload falhou na validação, tabela da seção 1.2. |
| `413` | `{"detail": {"filename": "...", "reason": "too_large"}}` | Um arquivo passou de 15 MiB. |
| `502` | `{"detail": "<mensagem do serviço ocr>"}` | A chamada ao serviço ocr interno falhou: inalcançável, deu timeout, ou retornou um erro por conta própria. |

## 2. Serviço ocr (interno apenas)

Não alcançável de fora da rede interna, já que nenhuma porta de host é
publicada pra ele. Documentado aqui porque o endpoint de screenshot do
serviço app depende dele, e porque ele valida o próprio input de forma
independente como defesa em profundidade: não pode assumir que seu
único chamador é o serviço app confiável.

### 2.1 GET /health

Checagem de liveness e readiness, usada pelo healthcheck do container.
Deliberadamente sem autenticação, já que o próprio healthcheck não tem
como fornecer facilmente o token de autenticação interno.

Requisição: sem parâmetros.

Resposta `200 OK`

```json
{ "status": "ok" }
```

### 2.2 POST /ocr

Decodifica um PNG enviado e retorna a saída estruturada do motor de
OCR.

Requisição: `multipart/form-data`

| Campo | Local | Obrigatório | Descrição |
| :--- | :--- | :--- | :--- |
| `image` | campo de formulário (arquivo) | Sim | A screenshot pra fazer OCR, PNG apenas. |
| `X-Internal-Auth` | header | Sim | Segredo compartilhado, veja a seção 2.3. |

Resposta `200 OK`, um array por coluna, todos os arrays do mesmo
tamanho, uma entrada por caixa de texto detectada:

```json
{
  "level": [1, 2, 3, 4, 5],
  "page_num": [1, 1, 1, 1, 1],
  "block_num": [0, 1, 1, 1, 1],
  "par_num": [0, 0, 1, 1, 1],
  "line_num": [0, 0, 0, 1, 1],
  "word_num": [0, 0, 0, 0, 1],
  "left": [0, 34, 34, 34, 34],
  "top": [0, 19, 19, 19, 19],
  "width": [1920, 400, 400, 400, 120],
  "height": [1080, 30, 30, 30, 22],
  "conf": [-1, -1, -1, -1, 96.4],
  "text": ["", "", "", "", "Wheat"]
}
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `level` | array de inteiro | Nível de hierarquia: 1 é página, 5 é palavra. |
| `page_num`, `block_num`, `par_num`, `line_num`, `word_num` | arrays de inteiro | Posição de cada elemento detectado na hierarquia de página, bloco, parágrafo, linha e palavra. |
| `left`, `top`, `width`, `height` | arrays de inteiro | Caixa delimitadora do elemento detectado, em pixels. |
| `conf` | array de número | Confiança da detecção, `-1` pros níveis que não são palavra. |
| `text` | array de string | Texto reconhecido, vazio pros níveis que não são palavra. |

Essa saída é o que o leitor de inventário consome pra reconstruir nomes
e quantidades de ingrediente. Veja o documento
[de cálculo](../calculation/CALCULATION.md) pra como a saída do OCR
vira um inventário de ingredientes.

Respostas de erro:

| Status | Corpo | Causa |
| :--- | :--- | :--- |
| `401` | `{"detail": "Invalid or missing internal auth token."}` | Header de autenticação interno faltando ou incorreto. |
| `413` | `{"detail": "Image exceeds maximum allowed size."}` | Imagem acima de 15 MiB, mantido em sincronia com o próprio limite do serviço app. |
| `400` | `{"detail": "Only PNG images are accepted."}` | Os primeiros 8 bytes não são o magic number do PNG. |
| `400` | `{"detail": "Could not decode image."}` | O magic number do PNG está presente mas o arquivo não pôde ser decodificado, por exemplo uma imagem truncada ou corrompida. |

### 2.3 Autenticação interna

Toda chamada pra `/ocr` deve carregar um header de autenticação interno
batendo com um valor de segredo compartilhado, comparado em tempo
constante pra evitar ataques de timing. O serviço app lê esse mesmo
segredo e anexa o header automaticamente, então esse token nunca
precisa ser fornecido por um usuário final da API pública. A checagem
de saúde, seção 2.1, é isenta.

## 3. Exemplos de linha de comando

```bash
# Checagem de saúde
curl http://localhost:8001/health

# Otimizar uma única screenshot, sem perks
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png"

# Otimizar várias screenshots com perks ativos
curl -X POST http://localhost:8001/optimize/screenshots \
  -F "files=@ScreenShot0.png" \
  -F "files=@ScreenShot1.png" \
  -F "perk_physician=true" \
  -F "perk_benefactor=true"
```

A porta 8001 assume o mapeamento padrão de deployment pro serviço app.
Ajuste pro seu deployment real.
