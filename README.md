# G.A.N.D.A.L.F.
**Gerenciador de Análise de Normas do Detran**

## Visão Geral
O G.A.N.D.A.L.F. é um sistema automatizado de governança e auditoria de banco de dados baseado em Inteligência Artificial. Utilizando arquitetura RAG (Retrieval-Augmented Generation), o sistema atua como um revisor estrito de nomenclaturas e boas práticas para objetos de banco de dados (Tabelas, Procedures, Índices, Views, etc.), validando scripts DDL de desenvolvedores contra o manual normativo oficial da Administração de Dados (AD).

## Arquitetura e Tecnologias
O projeto foi desenhado para operar localmente com foco em segurança de dados e alta performance vetorial.
* **Banco de Dados:** PostgreSQL com extensão `pgvector` para armazenamento e busca por similaridade semântica.
* **Motor LLM:** Ollama rodando localmente.
  * **Modelo de Linguagem:** `deepseek-r1:8b` (Raciocínio lógico e extração estruturada).
  * **Modelo de Embedding:** `nomic-embed-text:latest` (Vetorização de contexto).
* **Linguagem:** Python 3.12+ (psycopg2, requests, pdfplumber).

## Mecânica de Inteligência (RAG Hierárquico)
O motor de decisão do G.A.N.D.A.L.F. não opera com prompts estáticos. Ele constrói o contexto dinamicamente com base em uma hierarquia estrita de obediência:
1. **Exemplos Práticos Homologados (Prioridade Máxima):** Scripts validados previamente pela AD têm peso absoluto. Se um script submetido possuir estrutura semântica idêntica a um caso aprovado, ele herda a aprovação.
2. **Normas do Manual Vigente (Prioridade Média):** Extração dinâmica de regras gerais e específicas baseadas no PDF normativo atualizado.
3. **Memória de Testes (Prioridade de Apoio):** Histórico de interações anteriores para refinamento de contexto e prevenção de alucinações.

## Componentes Principais

### 1. `PerguntarManual.py` (O Auditor)
Módulo principal de interação. 
* Captura o script DDL do usuário.
* Utiliza o DeepSeek para classificar a intenção e extrair o objeto foco.
* Executa a busca vetorial cruzada (`vector_cosine_ops`) no PostgreSQL.
* Emite um parecer rigoroso formatado (Objeto, Conformidade, Justificativa e Recomendação).
* Salva logs diários de auditoria em diretório seguro.

### 2. `AdicaoExemploPratico.py` (O Gerenciador de Conhecimento)
Módulo administrativo para a equipe de AD.
* **Opção 1 & 2:** Gerenciamento manual da base de Exemplos Práticos (jurisprudência técnica) com rastreabilidade de data (`ultima_verificacao`).
* **Opção 3:** Ingestão automatizada de novos Manuais Normativos (PDF).
  * **Upsert Inteligente:** Identifica quais regras já existem no banco e apenas renova o carimbo de tempo, vetorizando apenas textos inéditos.
  * **Soft Delete Seguro:** Remove automaticamente regras que se tornaram obsoletas ou foram retiradas da versão mais recente do manual, sem gerar inatividade do sistema.

### 3. `DetranNorma.sql` (Schema e Deploy)
Script de inicialização do ambiente de dados. Contém a modelagem relacional, aplicação da extensão `vector`, criação de chaves exclusivas complexas (`UNIQUE NULLS NOT DISTINCT`) para prevenção de duplicatas lógicas e inserção dos dados semente.

### 4. `TreinoGandalf.py` e `AdicaoExemploTeorico.py` (Módulos de Manutenção)
Scripts auxiliares para carga inicial em lote e sanitização de memória não supervisionada.

## Instalação e Configuração

1. **Configuração do Ambiente de Banco de Dados**
   * Instale o PostgreSQL e a extensão `pgvector`.
   * Execute o script `DetranNorma.sql` para construir o schema corporativo.
   
2. **Configuração do Ollama**
   * Garanta que o serviço do Ollama esteja rodando no host configurado.
   * Execute o pull dos modelos necessários:
     `ollama pull deepseek-r1:8b`
     `ollama pull nomic-embed-text`

3. **Variáveis de Ambiente (.env)**
   Crie um arquivo `.env` na raiz do projeto contendo as credenciais de operação:
   ```env
   DB_NAME=DetranNorma
   DB_USER=seu_usuario
   DB_PASS=sua_senha
   DB_HOST=ip_do_banco
   DB_PORT=5435

4. **Dependências Python**
```pip install -r requirements.txt```

5. **Uso Básico**
Para submeter um script à auditoria:

Bash
python app_python/PerguntarManual.py "CREATE UNIQUE INDEX pk_processoadm ON dbhcen.processoadm USING btree (nusuario);"

6. **Para atualizar o manual ou inserir exemplos homologados:**
```
python app_python/AdicaoExemploPratico.py
```
