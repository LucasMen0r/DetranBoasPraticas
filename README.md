# G.E.N.D.A.L.F.
**Gestor Automatizado de Normas do Detran por meio de LLM para Fiscalização de Código**

## Visão Geral
O G.E.N.D.A.L.F. é um sistema automatizado de governança e auditoria de banco de dados baseado em Inteligência Artificial. Utilizando arquitetura RAG (Retrieval-Augmented Generation), o sistema atua como um revisor estrito de nomenclaturas e boas práticas para objetos de banco de dados (Tabelas, Procedures, Índices, Views, etc.), validando scripts DDL de desenvolvedores contra o manual normativo oficial da Administração de Dados (AD).

## Arquitetura e Tecnologias
O projeto foi desenhado para operar localmente com foco em segurança de dados e alta performance vetorial.
* **Banco de Dados:** PostgreSQL com extensão `pgvector` para armazenamento e busca por similaridade semântica.
* **Motor LLM:** Ollama rodando localmente.
  * **Modelo de Linguagem:** `deepseek-r1:8b` (Raciocínio lógico e extração estruturada).
  * **Modelo de Embedding:** `nomic-embed-text:latest` (Vetorização de contexto).
* **Linguagem:** Python 3.12+ 

## Mecânica de Inteligência (RAG Hierárquico)
O motor de decisão do G.A.N.D.A.L.F. não opera com prompts estáticos. Ele constrói o contexto dinamicamente com base em uma hierarquia estrita de obediência:
1. **Exemplos Práticos Homologados (Prioridade Máxima):** Scripts validados previamente pela AD têm peso absoluto. Se um script submetido possuir estrutura semântica idêntica a um caso aprovado, ele herda a aprovação.
2. **Normas do Manual Vigente (Prioridade Média):** Extração dinâmica de regras gerais e específicas baseadas no PDF normativo atualizado.
3. **Memória de Testes (Prioridade de Apoio):** Histórico de interações e dados sintéticos validados para refinamento de contexto e prevenção de alucinações.

## Roteamento Dinâmico de Modos (Novo)

Para otimizar o consumo de tokens e garantir a precisão semântica, o módulo auditor (PerguntarManual.py) analisa o volume da requisição e aciona automaticamente um dos dois modos de avaliação:

    Modo Precisão (Perguntas Curtas e Diretas): * Acionado para entradas curtas (até 800 caracteres).

        Mantém a restrição de distância vetorial rígida (0.32) e o limite de contexto estreito (top_k = 5).

        Ideal para dúvidas pontuais de desenvolvedores (ex: "Qual o padrão para nomear uma chave primária?").

    Modo Generalista (Scripts DDL Massivos):

        Acionado para blocos de código densos (> 800 caracteres).

        Flexibiliza a distância de cosseno (0.48) e expande a janela de recuperação de regras (top_k = 15).

        Permite que o LLM analise a criação de Tabelas, Índices, Chaves Estrangeiras e Triggers em uma única passagem de contexto contínuo, sem sofrer diluição semântica ou estourar os limites do modelo.

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

### 3. Esteira Automática de Dados Sintéticos (Data Augmentation)
Pipeline autônomo (Batch Processing) que expande a base de conhecimento estruturada do sistema, gerando, validando e ingerindo novos contextos sem supervisão manual constante.
* **`GerarPerguntasGendalf.py` (O Orquestrador):** Roda em loop baseado em timer (ex: 12 horas). Consulta a tabela de `ExemploPratico` e utiliza o modelo LLM para gerar pares complexos de Pergunta/Resposta. Ao atingir o limite de tempo, aciona os scripts subsequentes da esteira.
* **`LimpezaJson.py` (O Filtro Determinístico):** Atua como uma vacina contra alucinações do LLM. Varre os JSONs gerados *in-place* e aplica expressões regulares e regras de negócio estritas para identificar contradições (ex: sufixos trocados, regras de views aplicadas a tabelas). Atribui uma flag booleana (`valido: true/false`) a cada registro, mantendo o histórico de erros intacto para futuras análises.
* **`TreinoGendalf.py` (O Ingestor Vetorial):** Etapa final da esteira. Lê os JSONs classificados, ignora sumariamente os itens marcados como inválidos, converte os pares aprovados em embeddings e consolida a carga na tabela `ConhecimentoHistorico` do PostgreSQL.

### 4. `DetranNorma.sql` (Schema e Deploy)
Script de inicialização do ambiente de dados. Contém a modelagem relacional, aplicação da extensão `vector`, criação de chaves exclusivas complexas (`UNIQUE NULLS NOT DISTINCT`) para prevenção de duplicatas lógicas e inserção dos dados semente.

## Instalação e Configuração

1. **Configuração do Ambiente de Banco de Dados**
   * Instale o PostgreSQL e a extensão `pgvector`.
   * Execute o script `DetranNorma.sql` para construir o schema corporativo.
   * Necessário ter o docker baixado para acessar o container do Gendalf. 
   
2. **Configuração do Ollama**
   * Garanta que o serviço do Ollama esteja rodando no host configurado.
   * Execute o pull dos modelos necessários:
     ```bash
     ollama pull deepseek-r1:8b
     ollama pull nomic-embed-text
     ```

3. **Variáveis de Ambiente (.env)**
   Crie um arquivo `.env` na raiz do projeto contendo as credenciais de operação e configurações da esteira:
   ```
   DB_NAME=DetranNorma
   DB_USER=seu_usuario
   DB_PASS=sua_senha
   DB_HOST=ip_do_banco
   DB_PORT=5435
   OLLAMA_HOST=http://localhost:11436
   GERADOR_INTERVALO_MIN=60
   GERADOR_DURACAO_HORAS=12
   

4. **Dependências Python**
```pip install -r app_python/requirements.txt```

5. **Uso Básico**
Para submeter comandos ou dúvidas ao auditor, utilize o terminal:
Exemplo de uso - Modo Precisão (Pergunta Direta):
```
python app_python/PerguntarManual.py "CREATE UNIQUE INDEX pk_processoadm ON dbhcen.processoadm USING btree (nusuario);"
```

Exemplo de uso - Modo Generalista (Avaliação de Script DDL):
```
python app_python/PerguntarManual.py "CREATE TABLE dbvcen.historico_frotas ( id_veiculo int4 NOT NULL, data_frota timestamp NULL ); CREATE INDEX idx_01 ON dbvcen.historico_frotas (id_veiculo);"
```

7. **Para atualizar o manual ou inserir exemplos homologados:**
```
python app_python/AdicaoExemploPratico.py
```
