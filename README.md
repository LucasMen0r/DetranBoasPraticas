# Projeto G.A.N.D.A.L.F.
**Gerenciador de Análise de Normas do Detran**

## Visão Geral
O G.A.N.D.A.L.F. é um sistema de Inteligência Artificial baseado na arquitetura RAG (Retrieval-Augmented Generation). Sua principal função é atuar como um auditor rigoroso das regras de nomenclatura e boas práticas de banco de dados, garantindo que objetos (Procedures, Tabelas, Colunas, etc.) sigam estritamente o padrão normativo estabelecido.

O sistema utiliza modelos de linguagem locais (Ollama) integrados a um banco de dados vetorial (PostgreSQL + pgvector) para buscar contexto normativo, exemplos práticos aprovados e histórico de aprendizado antes de emitir um parecer técnico.

## Arquitetura e Tecnologias
* **Linguagem:** Python 3.12.3
* **Banco de Dados:** PostgreSQL com extensão `pgvector`
* **LLM (Chat):** DeepSeek-r1:8b (via Ollama)
* **Embedding:** nomic-embed-text:latest (via Ollama)

## Arquitetura RAG: O Impacto de Regras Duplicadas na Base de Conhecimento
Durante o desenvolvimento da base de conhecimento e do pipeline de ingestão de dados, estabeleceu-se a premissa de bloqueio estrito à entrada de registros duplicados na tabela de vetorização (`RegraNomenclatura`). 

A redundância de texto em arquiteturas RAG introduz falhas severas de performance e precisão no sistema como um todo. A decisão de isolar duplicatas baseia-se nos seguintes fatores arquiteturais:

* **Poluição da Janela de Contexto:** A busca vetorial (via `pgvector`) retorna os *Top K* resultados mais próximos semanticamente da pergunta do usuário. A existência de regras duplicadas faz com que um mesmo conteúdo ocupe múltiplas posições desse limite de retorno. Isso expulsa da janela de contexto outras regras complementares que seriam fundamentais para que o LLM formulasse uma resposta precisa.
* **Viés de Atenção do Modelo (Frequency Bias):** Modelos de linguagem ponderam suas respostas com base na repetição de tokens no prompt. Injetar a mesma regra múltiplas vezes no contexto força o LLM a atribuir um peso matemático desproporcional àquela instrução específica, podendo gerar alucinações ou ignorar as demais diretrizes normativas do banco.
* **Sobrecarga do Índice Vetorial (Consumo de RAM):** A busca por similaridade utiliza o algoritmo de indexação HNSW (Hierarchical Navigable Small World), que constrói grafos complexos mantidos ativamente na memória RAM do servidor. Vetores idênticos adicionam nós inúteis a essa estrutura, inchando o consumo de memória e degradando a performance matemática do cálculo de distância espacial.
* **Desperdício Computacional na Injeção:** A geração do vetor de 768 dimensões consome processamento (CPU/GPU) do servidor local. Processar textos idênticos repetidas vezes durante a leitura dos manuais gera gargalos de tempo e recursos desnecessários na etapa de ingestão.

**Implementação e Tratamento:**
Para garantir a integridade da base e a eficiência do modelo, o banco de dados impõe uma restrição estrutural (`UNIQUE CONSTRAINT`) validando a combinação de Categoria, Objeto e Texto. O script de automação em Python interage com essa trava utilizando a instrução `ON CONFLICT DO NOTHING`, garantindo que apenas regras inéditas ou atualizadas sejam vetorizadas e persistidas, sem interromper o fluxo de leitura de novos documentos em lote.

## Estrutura do Projeto
A base de código é dividida nos seguintes módulos principais:
* `DetranNorma.sql`: Script DDL e DML para recriação estrutural do banco de dados, tabelas relacionais de regras, restrições e carga das normativas padrão.
* `perguntar_ao_manual.py`: Script principal de interação. Recebe a requisição do usuário, classifica a intenção, busca os vetores de contexto no banco e interage com o LLM para retornar o diagnóstico da auditoria.
* `adicionar_exemplo_interativo.py`: Interface de linha de comando (CLI) multifuncional. Permite a manutenção da memória do sistema (inserção e remoção de exemplos práticos) e a ingestão automatizada de novos manuais normativos em formato PDF.
* `treinar_gandalf.py`: Script responsável pelo processamento em lote e vetorização de arquivos `.txt` contendo histórico e manuais auxiliares, armazenando o conhecimento na tabela `ConhecimentoHistorico`.

## Principais pacotes utilizados:
*requests: Comunicação HTTP com a API do Ollama.*

*psycopg2-binary: Conexão com o banco de dados PostgreSQL.*

*pgvector: Suporte aos embeddings e operações vetoriais no PostgreSQL.*

*python-dotenv: Leitura automática do arquivo .env.*

*pdfplumber: Leitura estruturada, extração semântica e ingestão automatizada em lote de manuais normativos em PDF.*
## Configuração do Ambiente

### 1. Dependências Python
Instale as bibliotecas necessárias utilizando o gerenciador de pacotes:
```pip install -r requirements.txt```

python adicionar_exemplo_interativo.py
Logs e Monitoramento
Todas as requisições e diagnósticos gerados pelo G.A.N.D.A.L.F. são registrados automaticamente na pasta memoria_gandalf/, salvos em arquivos .txt datados, permitindo a rastreabilidade das análises feitas pelo modelo. 

2. **Variáveis de Ambiente (.env):**
O projeto exige a configuração de variáveis de ambiente para a conexão com o PostgreSQL e com o servidor Ollama. Crie um arquivo .env na raiz do projeto seguindo a estrutura do arquivo .env.example e preencha com as suas credenciais locais:

DB_NAME
DB_USER
DB_PASS
DB_HOST
DB_PORT
OLLAMA_HOST

3. **Banco de Dados:**
Execute o script DetranNorma.sql no seu servidor PostgreSQL para criar os schemas, a extensão vetorial e popular as regras fundamentais.

3.1 **Para auditar um objeto (Uso Diário):**
Execute o script principal passando a pergunta como argumento ou utilize o modo interativo:
  `python perguntar_ao_manual.py "A procedure dbfisc01..EscalaS.scp está de acordo com o padrão?"`

3.2 **Para adicionar ou corrigir exceções na memória:**
Caso o sistema reprove um objeto válido, alimente a base de exemplos práticos para corrigir o comportamento do modelo na próxima execução:
  `python adicionar_exemplo_interativo.py`
4. **Imports**
Comunicacao HTTP com a API do Ollama
`requests`

Conexao com o banco de dados PostgreSQL
`psycopg2-binary`

Suporte aos embeddings e operacoes vetoriais no PostgreSQL
`pgvector`

Será utilizada na implementacao da ingestao e processamento em lote de manuais normativos em formato PDF.
`PyPDF2`

Leitura automatica do arquivo .env
`python-dotenv`
