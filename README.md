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

## Estrutura do Projeto
A base de código é dividida nos seguintes módulos principais:

* `DetranNorma.sql`: Script DDL e DML para recriação estrutural do banco de dados, tabelas relacionais de regras, restrições e carga das normativas padrão.
* `perguntar_ao_manual.py`: Script principal de interação. Recebe a requisição do usuário, classifica a intenção, busca os vetores de contexto no banco e interage com o LLM para retornar o diagnóstico da auditoria.
* `adicionar_exemplo_interativo.py`: Interface de linha de comando (CLI) para manutenção da memória do Gandalf. Permite a inserção, atualização (via `UPSERT`) e remoção de casos de sucesso e falha aprovados pela Administração de Dados.
* `treinar_gandalf.py`: Script responsável pelo processamento em lote e vetorização de arquivos `.txt` contendo histórico e manuais auxiliares, armazenando o conhecimento na tabela `ConhecimentoHistorico`.

## Configuração do Ambiente

1. **Dependências Python:**
Instale as bibliotecas necessárias utilizando o gerenciador de pacotes:

`pip install -r requirements.txt`

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
# Comunicacao HTTP com a API do Ollama
`requests`

# Conexao com o banco de dados PostgreSQL
`psycopg2-binary`

# Suporte aos embeddings e operacoes vetoriais no PostgreSQL
`pgvector`

# TODO: Biblioteca mantida como dependencia para suporte futuro. 
 Será utilizada na implementacao da ingestao e processamento em lote de manuais normativos em formato PDF.
`PyPDF2`

# Leitura automatica do arquivo .env
`python-dotenv`
