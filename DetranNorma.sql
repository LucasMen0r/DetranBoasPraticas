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
    pkCategoriaRegra INT REFERENCES (pkCategoriaRegra),
    pkObjetoDb INT REFERENCES ObjetoDb(pkObjetoDb), -- NULL se for regra geral
    DescricaoRegra TEXT NOT NULL,
    PadraoSintaxe TEXT,
    Exemplo TEXT,
    ContextoAdicional TEXT,
    FontePagina INT,
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
    pkAtributoCmum SERIAL PRIMARY KEY,
    Atributo VARCHAR(100) NOT NULL,
    TipoDadoRecomendado VARCHAR(100)
);
-- 3. INSERÇÃO DOS DADOS (POPULAÇÃO)
-- Inserindo Categorias e Objetos Básicos
INSERT INTO  (CategoriaRegra) VALUES ('Regras Gerais'), ('Nomenclatura de Objetos'), ('Boas Práticas'), ('Tipos de Dados'), ('Atributos Comuns') ON CONFLICT DO NOTHING;
INSERT INTO ObjetoDb (NomeObjeto) VALUES ('Banco'), ('Tabela'), ('Tabela Log'), ('Tabela Temp'), ('Tabela "z"'), ('Proxy Table'), ('Coluna'), ('PK (Primary Key)'), ('FK (Foreign Key)'), ('Unique'), ('Check'), ('View comum'), ('View materializada'), ('Índice'), ('Procedure'), ('Trigger') ON CONFLICT DO NOTHING;
-- Limpeza preventiva
TRUNCATE TABLE regras_nomenclatura RESTART IDENTITY CASCADE;
-- >>> REGRAS GERAIS
INSERT INTO regras_nomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, ContextoAdicional, FontePagina) VALUES
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Usar apenas letras (A-Z, a-z), números (0-9) e _ (underline).', 'Caracteres permitidos', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Não usar acentos, cedilha (ç), espaços.', 'Caracteres permitidos', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Não usar caracteres especiais (#, @, %, $, !, *, +, -, /, =).', 'Caracteres permitidos', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Uso de Iniciais Maiúsculas em cada palavra, sem utilizar o termo "PascalCase".', 'Forma dos nomes', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Usar termos em português e no singular.', 'Ex.: "Veiculo" no lugar de "Veiculos"', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Usar nomes curtos, claros e sem ambiguidade.', 'Forma dos nomes', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Evitar preposições (Ex.: "de", "da", "do").', 'Forma dos nomes', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Máximo de 30 caracteres (se ultrapassar, usar abreviações coerentes).', 'Limite de tamanho', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Não usar palavras reservadas (INSERT, DELETE, SELECT...).', 'Restrições', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Não usar apenas números, verbos ou nomes próprios.', 'Restrições', 4),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE CategoriaRegra = 'Regras Gerais'), NULL, 'Siglas oficiais: primeira letra maiúscula e demais minúsculas.', 'Ex.: Ipva, Cnh', 4);
-- >>> REGRAS DE OBJETOS
INSERT INTO regras_nomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, PadraoSintaxe, Exemplo, FontePagina) VALUES
-- Banco e Tabelas
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Banco'), 'O nome do banco deve identificar o negócio ou a sigla da aplicação.', 'db + área (até 5 posições) + seq', 'dbhbio01, dbhpop01', 6),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela'), 'Nome no singular, claro, sem abreviação (exceto se >30 chars).', 'Singular, Notação húngara (ParcelaDebito)', 'Veiculo, ParcelaDebito', 5),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela Log'), 'Tabelas de log devem ter o prefixo Log.', 'Log + nome da tabela', 'LogParcelaDebito', 7),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela Temp'), 'Tabela temporária auxiliar.', 'temp + nome tabela', 'tmpVeiculol', 7),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela "z"'), 'Tabelas que serão excluídas do banco de dados.', 'z + login + objetivo', 'zkrmlduplicidadedebitoLimpar', 7),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Proxy Table'), 'Tabelas espelho ou de referência externa.', 'px + Origem + NomeObjeto', 'pxProtLaudoToxicologico', 8),
-- Colunas
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Coluna'), 'Prefixo minúsculo indicando o tipo, seguido do nome em notação húngara.', 'tipo + NomeColuna', 'nValorPagar, nCpf, sChassi', 8),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Coluna'), 'Colunas usadas como parâmetro em procedures externas iniciam com underline.', '_ + NomeColuna', '_sNome, _Nome', 9),
-- Constraints 
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'pk (Primary Key)'), 'Chave primária natural ou sequencial.', 'pk + Nome Tabela', 'pkVeiculo, pkFeriado', 10),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'fk (Foreign Key)'), 'Padrão para Foreign Key (fk): Usar o prefixo fk mais os nomes das tabelas filha e pai.', 'fk + TabelaFilha + TabelaPai', 'fkProcessoUsuario', 11),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'unique'), 'Restrição de unicidade.', 'u + NomeTabela + Coluna', 'uUsuarioEmail', 11),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'check'), 'Restrição de checagem.', 'chk + NomeTabela + Coluna', 'chkUsuarioSexo', 11),
-- Views e Índices
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'View comum'), 'View para consultas (SELECT apenas).', 'vw + Nome Tabela', 'vwUsuarioProcesso', 12),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'View materializada'), 'View que armazena dados fisicamente.', 'vm + Objetivo[Complemento]', 'vmProcessoUsuario', 12),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Índice'), 'Nome da tabela seguido do nome da primeira coluna do índice.', 'Tabela + _ + Coluna', 'Usuario_nCpf', 12),
-- Procedures & Triggers
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Objetivo + Complemento + Operação (S, I, E, A, R).', 'Objetivo + [Complemento] + Operação', 'RegistroCfcCategoriaA, AtendimentoE', 13),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Se executada via batch, iniciar com Batch.', 'Batch + Nomeprocedure', 'BatchNomeprocedure', 14),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Se acesso via internet, iniciar com i.', 'i + Nomeprocedure', 'iNomeprocedure', 14),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Trigger'), 'Prefixo tg + tabela + sigla evento (I, A, E).', 'tg + Tabela + Operação', 'tgTabelal, tgTabelaA', 16);
-- >>> BOAS PRÁTICAS
INSERT INTO regras_nomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, ContextoAdicional, FontePagina) VALUES
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Boas Práticas'), NULL, 'Todo comando SQL deve ser feito via Stored Procedure (exceto update/insert de text/image).', 'Programação', 18),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Boas Práticas'), NULL, 'Integridade referencial deve ser via constraints (PK, Unique, FK).', 'Programação', 18),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Boas Práticas'), NULL, 'Preferencialmente não utilizar cursor.', 'Programação', 18),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Boas Práticas'), NULL, 'Evitar JOIN com mais de 4 tabelas (usar temporárias se necessário).', 'Programação', 19),
( (SELECT pkCategoriaRegra FROM  WHERE CategoriaRegra = 'Boas Práticas'), NULL, 'Evitar NOT EXISTS, NOT IN e NOT LIKE. Usar EXISTS, IN e LIKE.', 'Performance', 20);

-- 3.1 Criação da tabela de Exemplos práticos
DROP TABLE IF EXISTS ExemploPratico;

create table if not exists ExemploPratico (
    pkExemploPratico SERIAL PRIMARY KEY,
    ObjetoFoco VARCHAR(50),  
    ExemploTexto TEXT,       
    isBomExemplo BOOLEAN,  
    Explicacao TEXT,
    embedding vector(768)
);
CREATE INDEX ON ExemploPratico USING hnsw (embedding vector_cosine_ops);

-- 4. DADOS AUXILIARES (Tipos e Atributos)
TRUNCATE TABLE TipoDado RESTART IDENTITY CASCADE;
INSERT INTO TipoDado (TipoDadoSybase, SiglaColuna, FaixaValor, EspacoOcupado) VALUES
('bit', 'b', '0 ou 1', '1 byte'),
('datetime, smalldatetime, bigdatetime', 'd', 'Data e hora', '8 ou 4 bytes'),
('text, image, binary, long', 'I', 'Binários ou texto longo', 'Variável'),
('money, smallmoney', 'm', 'Monetário', '8 ou 4 bytes'),
('numeric, int, smallint, tinyint, float', 'n', 'Numéricos', 'Variável'),
('char, varchar', 'S', 'Texto (String)', 'N bytes'),
('Time', 'T', 'Hora apenas', '-'),
('Booleano', 'bo', 'Lógico', '-');
TRUNCATE TABLE AtributoComum RESTART IDENTITY CASCADE;
INSERT INTO AtributoComum (Atributo, TipoDadoRecomendado) VALUES
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
CREATE INDEX ON RegraNomenclatura USING hnsw (embedding vector_cosine_ops);
