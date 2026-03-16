-- 1. EXCLUSÃO DE TABELAS (Ordem reversa de dependência)
--DROP TABLE IF EXISTS ExemploPratico CASCADE;
--DROP TABLE IF EXISTS RegraNomenclatura CASCADE;
--DROP TABLE IF EXISTS CategoriaRegra CASCADE;
--DROP TABLE IF EXISTS ObjetoDb CASCADE;
--DROP TABLE IF EXISTS AtributoComum CASCADE;
--DROP TABLE IF EXISTS TipoDado CASCADE;

-- 2. EXTENSÃO VETORIAL
CREATE EXTENSION IF NOT EXISTS vector;

-- 2.1. CRIAÇÃO DE TABELAS (DDL Estrutural Completo)
CREATE TABLE ObjetoDb (
    pkObjetoDb SERIAL PRIMARY KEY,
    NomeObjeto VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE CategoriaRegra (
    pkCategoriaRegra SERIAL PRIMARY KEY,
    NomeCategoria VARCHAR(100) NOT NULL UNIQUE,
    DescricaoRegra TEXT
);
CREATE TABLE RegraNomenclatura (
    pkRegraNomenclatura SERIAL,
    pkCategoriaRegra INT NOT NULL,
    pkObjetoDb INT, 
    DescricaoRegra TEXT NOT NULL,
    embedding vector(768),
    UltimaVerificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pkRegraNomenclatura PRIMARY KEY (pkRegraNomenclatura),
    CONSTRAINT fkRegraNomenclaturaCategoriaRegra FOREIGN KEY (pkCategoriaRegra) REFERENCES CategoriaRegra(pkCategoriaRegra),
    CONSTRAINT fkRegraNomenclaturaObjetoDb FOREIGN KEY (pkObjetoDb) REFERENCES ObjetoDb(pkObjetoDb),
    CONSTRAINT ukRegraNomenclaturaUnica UNIQUE NULLS NOT DISTINCT (pkCategoriaRegra, pkObjetoDb, DescricaoRegra)
);

CREATE TABLE ExemploPratico (
    pkExemploPratico SERIAL,
    ObjetoFoco VARCHAR(100) NOT NULL,
    ExemploTexto TEXT NOT NULL,
    is_BomExemplo BOOLEAN NOT NULL,
    Explicacao TEXT NOT NULL,
    embedding vector(768),
    CONSTRAINT pkExemploPratico PRIMARY KEY (pkExemploPratico),
    CONSTRAINT ukExemploPraticoFocoTexto UNIQUE (ObjetoFoco, ExemploTexto)
);

CREATE TABLE AtributoComum (
    pkAtributoComum SERIAL,
    Atributo VARCHAR(100) NOT NULL,
    TipoDadoRecomendado VARCHAR(100),
    CONSTRAINT pkAtributoComum PRIMARY KEY (pkAtributoComum)
);

CREATE TABLE TipoDado (
    pkTipoDado SERIAL,
    TipoDadoSybase VARCHAR(50) NOT NULL,
    SiglaColuna VARCHAR(100), 
    FaixaValor VARCHAR(255),
    EspacoOcupado VARCHAR(50),
    CONSTRAINT pkTipoDado PRIMARY KEY (pkTipoDado),
    CONSTRAINT ukTipoDadoSiglaColuna UNIQUE (SiglaColuna)
);

-- 2.2. CARGA DE DOMÍNIOS BÁSICOS
INSERT INTO CategoriaRegra (NomeCategoria, DescricaoRegra) VALUES 
    ('Regras Gerais', 'Regras aplicáveis a todos os objetos'),
    ('Nomenclatura de Objetos', 'Padronização de nomes'),
    ('Boas Práticas', 'Diretrizes de desenvolvimento'),
    ('Tipos de Dados', 'Padrões de tipos'),
    ('Atributos Comuns', 'Campos recorrentes'),
    ('Regra especial', 'Regras específicas de sistemas (RENAVAM, etc)') 
ON CONFLICT DO NOTHING;

INSERT INTO ObjetoDb (NomeObjeto) VALUES 
    ('Banco'), ('Tabela'), ('Tabela Log'), ('Tabela Temp'), 
    ('Tabela "z"'), ('Proxy Table'), ('Coluna'), ('pk (Primary Key)'), 
    ('fk (Foreign Key)'), ('Unique'), ('Check'), ('View comum'), 
    ('View materializada'), ('Índice'), ('Procedure'), ('Trigger') 
ON CONFLICT DO NOTHING;

INSERT INTO TipoDado (TipoDadoSybase, SiglaColuna, FaixaValor, EspacoOcupado) VALUES
    ('bit', 'b', '0 ou 1', '1 byte'),
    ('datetime, smalldatetime, bigdatetime', 'd', 'Data e hora', '8 ou 4 bytes'),
    ('text, image, binary, long', 'I', 'Binários ou texto longo', 'Variável'),
    ('money, smallmoney', 'm', 'Monetário', '8 ou 4 bytes'),
    ('numeric, int, smallint, tinyint, float', 'n', 'Numéricos', 'Variável'),
    ('char, varchar', 'S', 'Texto (String)', 'N bytes'),
    ('Time', 'T', 'Hora apenas', '-'),
    ('Booleano', 'bo', 'Lógico', '-');

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
-- 3. INSERÇÃO DOS DADOS (POPULAÇÃO)
-- Inserindo Categorias e Objetos Básicos
INSERT INTO CategoriaRegra (NomeCategoria, DescricaoRegra) VALUES 
    ('Regras Gerais', 'Regras aplicáveis a todos os objetos'),
    ('Nomenclatura de Objetos', 'Padronização de nomes'),
    ('Boas Práticas', 'Diretrizes de desenvolvimento'),
    ('Tipos de Dados', 'Padrões de tipos'),
    ('Atributos Comuns', 'Campos recorrentes'),
    ('Regra especial', 'Regras específicas de sistemas (RENAVAM, etc)') 
ON CONFLICT DO NOTHING;

INSERT INTO ObjetoDb (NomeObjeto) VALUES ('Banco'), ('Tabela'), ('Tabela Log'), ('Tabela Temp'), ('Tabela "z"'), ('Proxy Table'), ('Coluna'), ('pk (Primary Key)'), ('fk (Foreign Key)'), ('Unique'), ('Check'), ('View comum'), ('View materializada'), ('Índice'), ('Procedure'), ('Trigger') ON CONFLICT DO NOTHING;
-- Limpeza preventiva
TRUNCATE TABLE RegraNomenclatura RESTART IDENTITY CASCADE;
-- >>> REGRAS GERAIS
INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra) VALUES
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Usar apenas letras (A-Z, a-z), números (0-9) e _ (underline).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar acentos, cedilha (ç), espaços.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar caracteres especiais (#, @, %, $, !, *, +, -, /, =).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Uso de Iniciais Maiúsculas em cada palavra [notação húngara.]".'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Usar termos em português e no singular.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Usar nomes curtos, claros e sem ambiguidade.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Evitar preposições (Ex.: "de", "da", "do").'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Regras Gerais'), null, 'Tabelas temporárias (Tabela Temp) vai seguir as mesmas regras de nomenclatura aplicadas às tabelas'), 
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Tabelas devem ser nomeadas usando o máximo de 30 caracteres (se ultrapassar, usar abreviações coerentes).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar palavras reservadas (INSERT, DELETE, SELECT...).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Não usar apenas números, verbos ou nomes próprios.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Regras Gerais'), NULL, 'Siglas oficiais: primeira letra maiúscula e demais minúsculas.'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Regra especial'), null, 'Em se tratando de sistema de Veículos, os nomes dos procedimentos RENAVAM e RENAINF ficarão iguais aos já existentes.'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Regra especial'), null, 'Se executada via batch, iniciar com Batch.'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Regra especial'), null, 'As procedures usadas pela FISEPE (SEFAZ) irão iniciar com as letras “FI” (maiúsculo).'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Regra especial'), null, 'Quando a procedure for de Habilitação e for executada em Veículo ou o contrário, deve-se colocar no início do nome da procedure a palavra “Rpc”.'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Regra especial'), null, 'Se acesso via internet, iniciar com "i", já as colunas serão nomeadas com "@" no início.');
-- >>> REGRAS DE OBJETOS
INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra) VALUES
-- Banco e Tabelas
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Banco'), 'O nome do banco deve identificar o negócio ou a sigla da aplicação.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela'), 'Nome no singular, claro, sem abreviação (exceto se >30 chars).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela Log'), 'Tabelas de log devem ter o prefixo Log.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela Temp'), 'Tabela temporária auxiliar.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Tabela "z"'), 'Tabelas que serão excluídas do banco de dados.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Proxy Table'), 'Tabelas espelho ou de referência externa.'),
-- Colunas
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Coluna'), 'Prefixo minúsculo indicando o tipo, seguido do nome em notação húngara.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Coluna'), 'Colunas usadas como parâmetro em procedures externas iniciam com underline.'),
-- Constraints 
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'pk (Primary Key)'), 'Chave primária natural ou sequencial.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'fk (Foreign Key)'), 'Padrão para Foreign Key (FK): Usar o prefixo fk mais os nomes das tabelas filha e pai.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Unique'), 'Restrição de unicidade.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Check'), 'Restrição de checagem.'),
-- Views e Índices
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'View comum'), 'View para consultas (SELECT apenas).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'View materializada'), 'View que armazena dados fisicamente.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Índice'), 'Nome da tabela seguido do nome da primeira coluna do índice.'),
-- Procedures & Triggers
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Objetivo + Complemento + Operação (S, I, E, A, R).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Se executada via batch, iniciar com Batch.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Procedure'), 'Se acesso via internet, iniciar com i; as colunas irão iniciar com @.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Nomenclatura de Objetos'), (SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = 'Trigger'), 'Prefixo tg + tabela + sigla evento (I, A, E).'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Nomenclatura de objetos'), (select pkObjetoDb from ObjetoDb where NomeObjeto = 'Procedure'), 'Em se tratando de sistema de Veículos, os nomes dos procedimentos RENAVAM e RENAINF ficarão iguais aos já existentes. Caso sejam banco RENAVAM todos os padrões serão mantidos, mas caso sejam em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos.'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Nomenclatura de objetos'), (select pkObjetoDb from ObjetoDb where NomeObjeto = 'Procedure'), 'As procedures usadas pela FISEPE (SEFAZ) irão iniciar com as letras “FI” (maiúsculo).'),
( (select pkCategoriaRegra from CategoriaRegra where NomeCategoria = 'Nomenclatura de objetos'), (select pkObjetoDb from ObjetoDb where NomeObjeto = 'Procedure'), 'Quando a procedure for de Habilitação e for executada em Veículo ou o contrário, deve-se colocar no início do nome da procedure a palavra “Rpc”.');
-- >>> BOAS PRÁTICAS
INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra) VALUES
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Todo comando sql deve ser feito via Stored Procedure (exceto update/insert de text/image).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Integridade referencial deve ser via constraints (pk, Unique, pk).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Preferencialmente não utilizar cursor.'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Evitar JOIN com mais de 4 tabelas (usar temporárias se necessário).'),
( (SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = 'Boas Práticas'), NULL, 'Evitar NOT EXISTS, NOT IN e NOT LIKE. Usar EXISTS, IN e LIKE.');

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

-- 5. SEGURANÇA E PERMISSÕES
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'Ollama_trainer') THEN
      CREATE USER Ollama_trainer WITH PASSWORD '123456';
   END IF;
END
$do$;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO Ollama_trainer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO Ollama_trainer;

-- 6. CRIAÇÃO DE ÍNDICES VETORIAIS (Nomenclatura Tabela_Coluna)
CREATE INDEX RegraNomenclatura_embedding ON RegraNomenclatura USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ExemploPratico_embedding ON ExemploPratico USING hnsw (embedding vector_cosine_ops);



DELETE FROM ExemploPratico a 
USING ExemploPratico b 
WHERE a.pkExemploPratico < b.pkExemploPratico 
  AND LOWER(a.ObjetoFoco) = LOWER(b.ObjetoFoco) 
  AND a.ExemploTexto = b.ExemploTexto;

UPDATE ExemploPratico SET ObjetoFoco = INITCAP(ObjetoFoco);




SELECT * FROM ExemploPratico;