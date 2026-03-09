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
```bash
pip install -r requirements.txt
