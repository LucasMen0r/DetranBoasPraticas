-- 1. PREPARAÇÃO DO AMBIENTE
-- Habilita a extensão para vetores (ESSENCIAL PARA O RAG)
CREATE EXTENSION IF NOT EXISTS vector;
-- 2. CRIAÇÃO DAS TABELAS (SCHEMA)
-- Categorias e Objetos
CREATE TABLE IF NOT EXISTS categorias_regras (
    id_categoria SERIAL PRIMARY KEY,
    nome_categoria VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS objetos_db (
    id_objeto SERIAL PRIMARY KEY,
    nome_objeto VARCHAR(100) NOT NULL UNIQUE
);
-- Tabela Principal de Regras
CREATE TABLE IF NOT EXISTS regras_nomenclatura (
    id_regra SERIAL PRIMARY KEY,
    id_categoria INT REFERENCES categorias_regras(id_categoria),
    id_objeto INT REFERENCES objetos_db(id_objeto), -- NULL se for regra geral
    descricao_regra TEXT NOT NULL,
    padrao_sintaxe TEXT,
    contexto_adicional TEXT,
    fonte_pagina INT,
    embedding vector(768) -- Coluna onde o Python salvará os vetores
);
-- Tabelas Auxiliares
CREATE TABLE IF NOT EXISTS tipos_dados (
    id_tipo_dado SERIAL PRIMARY KEY,
    tipo_dado_sybase VARCHAR(50) NOT NULL,
    sigla_coluna VARCHAR(10) UNIQUE,
    faixa_valores VARCHAR(255),
    espaco_ocupado VARCHAR(50)
);
CREATE TABLE IF NOT EXISTS atributos_comuns (
    id_atributo SERIAL PRIMARY KEY,
    atributo VARCHAR(100) NOT NULL,
    tipo_dado_recomendado VARCHAR(100)
);
-- 3. INSERÇÃO DOS DADOS (POPULAÇÃO)
-- Inserindo Categorias e Objetos Básicos
INSERT INTO categorias_regras (nome_categoria) VALUES ('Regras Gerais'), ('Nomenclatura de Objetos'), ('Boas Práticas'), ('Tipos de Dados'), ('Atributos Comuns') ON CONFLICT DO NOTHING;
INSERT INTO objetos_db (nome_objeto) VALUES ('Banco'), ('Tabela'), ('Tabela Log'), ('Tabela Temp'), ('Tabela "z"'), ('Proxy Table'), ('Coluna'), ('PK (Primary Key)'), ('FK (Foreign Key)'), ('Unique'), ('Check'), ('View comum'), ('View materializada'), ('Índice'), ('Procedure'), ('Trigger') ON CONFLICT DO NOTHING;
-- Limpeza preventiva
TRUNCATE TABLE regras_nomenclatura RESTART IDENTITY CASCADE;
-- >>> REGRAS GERAIS
INSERT INTO regras_nomenclatura (id_categoria, id_objeto, descricao_regra, contexto_adicional, fonte_pagina) VALUES
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Usar apenas letras (A-Z, a-z), números (0-9) e _ (underline).', 'Caracteres permitidos', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Não usar acentos, cedilha (ç), espaços.', 'Caracteres permitidos', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Não usar caracteres especiais (#, @, %, $, !, *, +, -, /, =).', 'Caracteres permitidos', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Uso de Iniciais Maiúsculas em cada palavra, sem utilizar o termo "PascalCase".', 'Forma dos nomes', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Usar termos em português e no singular.', 'Ex.: "Veiculo" no lugar de "Veiculos"', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Usar nomes curtos, claros e sem ambiguidade.', 'Forma dos nomes', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Evitar preposições (Ex.: "de", "da", "do").', 'Forma dos nomes', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Máximo de 30 caracteres (se ultrapassar, usar abreviações coerentes).', 'Limite de tamanho', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Não usar palavras reservadas (INSERT, DELETE, SELECT...).', 'Restrições', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Não usar apenas números, verbos ou nomes próprios.', 'Restrições', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Siglas oficiais: primeira letra maiúscula e demais minúsculas.', 'Ex.: Ipva, Cnh', 4);
-- >>> REGRAS DE OBJETOS
INSERT INTO regras_nomenclatura (id_categoria, id_objeto, descricao_regra, padrao_sintaxe, fonte_pagina) VALUES
-- Banco e Tabelas
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Banco'), 'O nome do banco deve identificar o negócio ou a sigla da aplicação.', 6),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela'), 'Nome no singular, claro, sem abreviação (exceto se >30 chars).', 5),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela Log'), 'Tabelas de log devem ter o prefixo Log.', 'Log + nome da tabela', 7),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela Temp'), 'Tabela temporária auxiliar.', 'temp + nome tabela', 'tmpVeiculol', 7),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela "z"'), 'Tabelas que serão excluídas do banco de dados.', 'z + login + objetivo', 7),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Proxy Table'), 'Tabelas espelho ou de referência externa.', 'px + Origem + NomeObjeto', 8),
-- Colunas
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Coluna'), 'Prefixo minúsculo indicando o tipo, seguido do nome em notação húngara.', 8),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Coluna'), 'Colunas usadas como parâmetro em procedures externas iniciam com underline.', 9),
-- Constraints 
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'PK (Primary Key)'), 'Chave primária natural ou sequencial.', 10),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'FK (Foreign Key)'), 'Padrão para Foreign Key (FK): Usar o prefixo fk mais os nomes das tabelas filha e pai.', 11),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Unique'), 'Restrição de unicidade.', 'u + NomeTabela + Coluna', 11),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Check'), 'Restrição de checagem.', 'chk + NomeTabela + Coluna', 11),
-- Views e Índices
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'View comum'), 'View para consultas (SELECT apenas).', 'vw + Nome Tabela', 12),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'View materializada'), 'View que armazena dados fisicamente.', 'vm + Objetivo[Complemento]', 12),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Índice'), 'Nome da tabela seguido do nome da primeira coluna do índice.', 'Tabela + _ + Coluna', 12),
-- Procedures & Triggers
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Procedure'), 'Objetivo + Complemento + Operação (S, I, E, A, R).', 'Objetivo + [Complemento] + Operação', 13),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Procedure'), 'Se executada via batch, iniciar com Batch.', 'Batch + Nomeprocedure', 14),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Procedure'), 'Se acesso via internet, iniciar com i.', 'i + Nomeprocedure', 14),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Trigger'), 'Prefixo tg + tabela + sigla evento (I, A, E).', 16);
-- >>> BOAS PRÁTICAS
INSERT INTO regras_nomenclatura (id_categoria, id_objeto, descricao_regra, contexto_adicional, fonte_pagina) VALUES
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Todo comando SQL deve ser feito via Stored Procedure (exceto update/insert de text/image).', 'Programação', 18),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Integridade referencial deve ser via constraints (PK, Unique, FK).', 'Programação', 18),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Preferencialmente não utilizar cursor.', 'Programação', 18),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Evitar JOIN com mais de 4 tabelas (usar temporárias se necessário).', 'Programação', 19),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Evitar NOT EXISTS, NOT IN e NOT LIKE. Usar EXISTS, IN e LIKE.', 'Performance', 20);

-- 3.1 Criação da tabela de exemplos práticos
DROP TABLE IF EXISTS exemplos_praticos;

create table if not exists exemplos_praticos (
    id SERIAL PRIMARY KEY,
    objeto_foco VARCHAR(50),  
    exemplo_texto TEXT,       
    is_bom_exemplo BOOLEAN,  
    explicacao TEXT,
    embedding vector(768)
);
CREATE INDEX ON exemplos_praticos USING hnsw (embedding vector_cosine_ops);

-- 4. DADOS AUXILIARES (Tipos e Atributos)
TRUNCATE TABLE tipos_dados RESTART IDENTITY CASCADE;
INSERT INTO tipos_dados (tipo_dado_sybase, sigla_coluna, faixa_valores, espaco_ocupado) VALUES
('bit', 'b', '0 ou 1', '1 byte'),
('datetime, smalldatetime, bigdatetime', 'd', 'Data e hora', '8 ou 4 bytes'),
('text, image, binary, long', 'I', 'Binários ou texto longo', 'Variável'),
('money, smallmoney', 'm', 'Monetário', '8 ou 4 bytes'),
('numeric, int, smallint, tinyint, float', 'n', 'Numéricos', 'Variável'),
('char, varchar', 'S', 'Texto (String)', 'N bytes'),
('Time', 'T', 'Hora apenas', '-'),
('Booleano', 'bo', 'Lógico', '-');
TRUNCATE TABLE atributos_comuns RESTART IDENTITY CASCADE;
INSERT INTO atributos_comuns (atributo, tipo_dado_recomendado) VALUES
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
CREATE USER Ollama_trainer WITH PASSWORD '123456';

-- 5b. Concessão de privilégios no SCHEMA 'public'
-- O esquema 'public' contém todas as tabelas criadas no seu script.
GRANT ALL PRIVILEGES ON SCHEMA public TO Ollama_trainer;

-- 5c. Concessão de privilégios futuros (para tabelas criadas depois)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO Ollama_trainer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO Ollama_trainer;

-- 6. CRIAÇÃO DE ÍNDICES VETORIAIS (Este comando estava no seu script)
CREATE INDEX ON regras_nomenclatura USING hnsw (embedding vector_cosine_ops);
