-- 1. PREPARAÇÃO DO AMBIENTE
-- Habilita a extensão para vetores (ESSENCIAL PARA O RAG)
CREATE EXTENSION IF NOT EXISTS vector;
-- 2. CRIAÇÃO DAS TABELAS (SCHEMA)
-- Categorias e Objetos
CREATE TABLE IF NOT EXISTS CategoriaRegra (
    pkCategoriaRegra SERIAL PRIMARY KEY,
    NomeCategoria VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS ObjetoDb (
    pkObjetoDb SERIAL PRIMARY KEY,
    NomeObjeto VARCHAR(100) NOT NULL UNIQUE
);
-- Tabela Principal de Regras
CREATE TABLE IF NOT EXISTS RegraNomenclatura (
    pkRegraNomenclatura SERIAL PRIMARY KEY,
    pkCategoriaRegra INT REFERENCES CategoriaRegra(pkCategoriaRegra),
    pkObjetoDb INT REFERENCES ObjetoDb(pkObjetoDb), -- NULL se for regra geral
    DescricaoRegra TEXT NOT NULL,
    ContextoAdicional TEXT,
    embedding vector(768) -- Coluna onde o Python salvará os vetores
);
-- Tabelas Auxiliares
CREATE TABLE IF NOT EXISTS TipoDado (
    pkTipoDado SERIAL PRIMARY KEY,
    TipoDadoSybase VARCHAR(50) NOT NULL,
    SiglaColuna VARCHAR(10) UNIQUE,
    FaixaValor VARCHAR(255),
    EspacoOcupado VARCHAR(50)
);
CREATE TABLE IF NOT EXISTS AtributoComum (
    pkAtributoComum SERIAL PRIMARY KEY,
    Atributo VARCHAR(100) NOT NULL,
    TipoDadoRecomendado VARCHAR(100)
);
-- 3. INSERÇÃO DOS DADOS (POPULAÇÃO)
-- Inserindo Categorias e Objetos Básicos
INSERT INTO CategoriaRegra (NomeCategoria) VALUES ('Regras Gerais'), ('Nomenclatura de Objetos'), ('Boas Práticas'), ('Tipos de Dados'), ('Atributos Comuns') ON CONFLICT DO NOTHING;
INSERT INTO ObjetoDb (NomeObjeto) VALUES ('Banco'), ('Tabela'), ('Tabela Log'), ('Tabela Temp'), ('Tabela "z"'), ('Proxy Table'), ('Coluna'), ('fk (Primary Key)'), ('fk (Foreign Key)'), ('Unique'), ('Check'), ('View comum'), ('View materializada'), ('Índice'), ('Procedure'), ('Trigger') ON CONFLICT DO NOTHING;
-- Limpeza preventiva
TRUNCATE TABLE RegraNomenclatura RESTART IDENTITY CASCADE;
-- >>> REGRAS GERAIS
INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, ContextoAdicional) VALUES
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Usar apenas letras (A-Z, a-z), números (0-9) e _ (underline).', 'Caracteres permitidos'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar acentos, cedilha (ç), espaços.', 'Caracteres permitidos'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar caracteres especiais (#, @, %, $, !, *, +, -, /, =).', 'Caracteres permitidos'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Uso de Iniciais Maiúsculas em cada palavra, sem utilizar o termo "PascalCase".', 'Forma dos nomes'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Usar termos em português e no singular.', 'Ex.: "Veiculo" no lugar de "Veiculos"'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Usar nomes curtos, claros e sem ambiguidade.', 'Forma dos nomes'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Evitar preposições (Ex.: "de", "da", "do").', 'Forma dos nomes'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Máximo de 30 caracteres (se ultrapassar, usar abreviações coerentes).', 'Limite de tamanho'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar palavras reservadas (INSERT, DELETE, SELECT...).', 'Restrições'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar apenas números, verbos ou nomes próprios.', 'Restrições'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Siglas oficiais: primeira letra maiúscula e demais minúsculas.', 'Ex.: Ipva, Cnh');
-- >>> REGRAS DE OBJETOS
INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, ContextoAdicional) VALUES 
-- Banco e Tabelas
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Banco'), 'O nome do banco deve identificar o negócio ou a sigla da aplicação.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela'), 'Nome no singular, claro, sem abreviação (exceto se >30 chars).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela Log'), 'Tabelas de log devem ter o prefixo Log.', 'Log + nome da tabela'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela Temp'), 'Tabela temporária auxiliar.', 'temp + nome tabela', 'tmpVeiculol'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela "z"'), 'Tabelas que serão excluídas do banco de dados.', 'z + login + objetivo'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Proxy Table'), 'Tabelas espelho ou de referência externa.', 'px + Origem + NomeObjeto'),
-- Colunas
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Coluna'), 'Prefixo minúsculo indicando o tipo, seguido do nome em notação húngara.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Coluna'), 'Colunas usadas como parâmetro em procedures externas iniciam com underline.'),
-- Constraints 
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'pk (Primary Key)'), 'Chave primária natural ou sequencial.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'fk (Foreign Key)'), 'Padrão para Foreign Key (fk): Usar o prefixo fk mais os nomes das tabelas filha e pai.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Unique'), 'Restrição de unicidade.', 'u + NomeTabela + Coluna'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Check'), 'Restrição de checagem.', 'chk + NomeTabela + Coluna'),
-- Views e Índices
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'View comum'), 'View para consultas (SELECT apenas).', 'vw + Nome Tabela'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'View materializada'), 'View que armazena dados fisicamente.', 'vm + Objetivo[Complemento]'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Índice'), 'Nome da tabela seguido do nome da primeira coluna do índice.', 'Tabela + _ + Coluna'),
-- Procedures & Triggers
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Objetivo + Complemento + Operação (S, I, E, A, R).', 'Objetivo + [Complemento] + Operação'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Se executada via batch, iniciar com Batch.', 'Batch + Nomeprocedure'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Se acesso via internet, iniciar com i.', 'i + Nomeprocedure'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Trigger'), 'Prefixo tg + tabela + sigla evento (I, A, E).');
-- >>> BOAS PRÁTICAS
INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, ContextoAdicional) VALUES
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Todo comando SQL deve ser feito via Stored Procedure (exceto update/insert de text/image).', 'Programação'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Integridade referencial deve ser via constraints (pk, Unique, pk).', 'Programação'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Preferencialmente não utilizar cursor.', 'Programação'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Evitar JOIN com mais de 4 tabelas (usar temporárias se necessário).', 'Programação'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Evitar NOT EXISTS, NOT IN e NOT LIKE. Usar EXISTS, IN e LIKE.', 'Performance');

-- 3.1 Criação da tabela de exemplos práticos
DROP TABLE IF EXISTS ExemploPratico;

create table if not exists ExemploPratico (
    pkExemploPratico SERIAL PRIMARY KEY,
    ObjetoFoco VARCHAR(50),  
    ExemploTexto TEXT,       
    is_BomExemplo BOOLEAN,  
    Explicacao TEXT,
    embedding vector(768)
);
CREATE INDEX ON ExemploPratico USING hnsw (embedding vector_cosine_ops);

-- 4. DADOS AUXILIARES (Tipos e Atributos)
TRUNCATE TABLE TipoDado RESTART IDENTITY CASCADE;
INSERT INTO TipoDado (TipoDadoSybase, SiglaColuna, Faixavalor, EspacoOcupado) VALUES
('bit', 'b', '0 ou 1', '1 byte'),
('datetime, smalldatetime, bigdatetime', 'd', 'Data e hora', '8 ou 4 bytes'),
('text, image, binary, long', 'I', 'Binários ou texto longo', 'Variável'),
('money, smallmoney', 'm', 'Monetário', '8 ou 4 bytes'),
('numeric, int, smallint, tinyint, float', 'n', 'Numéricos', 'Variável'),
('char, varchar', 'S', 'Texto (String)', 'N bytes'),
('Time', 'T', 'Hora apenas', '-'),
('Booleano', 'bo', 'Lógico', '-');
TRUNCATE TABLE AtributoComum RESTART IDENTITY CASCADE;
INSERT INTO AtributoComum (atributo, TipoDadoRecomendado) VALUES
('Pessoas', 'Varchar(50)'),
('E-mail', 'Varchar(60)'),
('Telefone', 'Varchar(10)'),
('Fax', 'Varchar(10)'),
('Logradouro', 'Varchar(60)'),
('Complemento', 'Varchar(65)'),
('CEP', 'Numeric(8)'),
('Bairro', 'Varchar(60)'),
('Município', 'Varchar(60)'),
('País', 'Varchar(60)'),
('CGC', 'Char(14)'),
('CPF', 'Char(11)'),
('Login', 'Varchar(30)');

-- 5. CRIAÇÃO DE USUÁRIO E PRIVILÉGIOS

-- 5a. Criação do usuário para o Ollama
CREATE USER Ollama_trainer  WITH PASSWORD '123456';

-- 5b. Concessão de privilégios no SCHEMA 'public'
-- O esquema 'public' contém todas as tabelas criadas no seu script.
GRANT ALL PRIVILEGES ON SCHEMA public TO Ollama_trainer;

-- 5c. Concessão de privilégios futuros (para tabelas criadas depois)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO Ollama_trainer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO Ollama_trainer;

-- 6. CRIAÇÃO DE ÍNDICES VETORIAIS (Este comando estava no seu script)
CREATE INDEX ON RegraNomenclatura USING hnsw (embedding vector_cosine_ops);
