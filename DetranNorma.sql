-- 1. PREPARAÇÃO DO AMBIENTE
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. CRIAÇÃO DAS TABELAS (SCHEMA)
CREATE TABLE IF NOT EXISTS categorias_regras (
    id_categoria SERIAL PRIMARY KEY,
    nome_categoria VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS objetos_db (
    id_objeto SERIAL PRIMARY KEY,
    nome_objeto VARCHAR(100) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS regras_nomenclatura (
    id_regra SERIAL PRIMARY KEY,
    id_categoria INT REFERENCES categorias_regras(id_categoria),
    id_objeto INT REFERENCES objetos_db(id_objeto),
    descricao_regra TEXT NOT NULL,
    padrao_sintaxe TEXT,
    exemplo TEXT,
    contexto_adicional TEXT,
    fonte_pagina INT,
    embedding vector(768)
);
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
INSERT INTO categorias_regras (nome_categoria) VALUES ('Regras Gerais'), ('Nomenclatura de Objetos'), ('Boas Práticas'), ('Tipos de Dados'), ('Atributos Comuns') ON CONFLICT DO NOTHING;
INSERT INTO objetos_db (nome_objeto) VALUES ('Banco'), ('Tabela'), ('Tabela Log'), ('Tabela Temp'), ('Tabela "z"'), ('Proxy Table'), ('Coluna'), ('PK (Primary Key)'), ('FK (Foreign Key)'), ('Unique'), ('Check'), ('View comum'), ('View materializada'), ('Índice'), ('Procedure'), ('Trigger') ON CONFLICT DO NOTHING;

-- Limpeza preventiva
TRUNCATE TABLE regras_nomenclatura RESTART IDENTITY CASCADE;

-- >>> REGRAS GERAIS
INSERT INTO regras_nomenclatura (id_categoria, id_objeto, descricao_regra, contexto_adicional, fonte_pagina) VALUES
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Usar apenas letras (A-Z, a-z), números (0-9) e _ (underline).', 'Caracteres permitidos', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Não usar acentos, cedilha (ç), espaços.', 'Caracteres permitidos', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Uso obrigatório de PascalCase (Primeira letra de cada palavra interna em maiúscula).', 'Forma dos nomes', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Uso de Notação Húngara (Prefixos indicando tipo ou objeto) é mandatório.', 'Padrão Geral', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Usar termos em português e no singular.', 'Ex.: "tbVeiculo" no lugar de "Veiculos"', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Máximo de 30 caracteres (se ultrapassar, usar abreviações coerentes).', 'Limite de tamanho', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Não usar palavras reservadas (INSERT, DELETE, SELECT...).', 'Restrições', 4),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Regras Gerais'), NULL, 'Siglas oficiais: primeira letra maiúscula e demais minúsculas (CamelCase/Pascal).', 'Ex.: Ipva, Cnh', 4);

-- >>> REGRAS DE OBJETOS (COM NOTAÇÃO HÚNGARA)
INSERT INTO regras_nomenclatura (id_categoria, id_objeto, descricao_regra, padrao_sintaxe, exemplo, fonte_pagina) VALUES
-- Banco e Tabelas
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Banco'), 'O nome do banco deve identificar o negócio (Notação Húngara: prefixo db).', 'db + área + seq', 'dbhbio01, dbhpop01', 6),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela'), 'Notação Húngara: Prefixo "tb" seguido do nome em PascalCase (Singular).', 'tb + NomeTabela', 'tbVeiculo, tbParcelaDebito', 5),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela Log'), 'Tabelas de log devem ter o prefixo log (Notação Húngara).', 'log + NomeTabela', 'logParcelaDebito', 7),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Tabela Temp'), 'Tabela temporária auxiliar com prefixo tmp ou #.', 'tmp + NomeTabela', 'tmpVeiculo', 7),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Proxy Table'), 'Tabelas espelho externas (Notação Húngara: px).', 'px + Origem + NomeObjeto', 'pxProtLaudoToxicologico', 8),

-- Colunas (Onde a Húngara é mais forte)
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Coluna'), 'Notação Húngara Obrigatória: Prefixo minúsculo do tipo de dado + Nome PascalCase.', 'tipo (n, s, d...) + NomeColuna', 'nValorPagar, sNome, dDataVencimento', 8),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Coluna'), 'Parâmetros de procedures externas iniciam com underline.', '_ + tipo + NomeColuna', '_sNome, _nId', 9),

-- Constraints 
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'PK (Primary Key)'), 'Chave primária (Notação Húngara: pk).', 'pk + NomeTabela', 'pkVeiculo, pkFeriado', 10),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'FK (Foreign Key)'), 'Chave Estrangeira (Notação Húngara: fk).', 'fk + TabelaFilha + TabelaPai', 'fkProcessoUsuario', 11),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Unique'), 'Restrição de unicidade (u).', 'u + NomeTabela + Coluna', 'uUsuarioEmail', 11),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Check'), 'Restrição de checagem (chk).', 'chk + NomeTabela + Coluna', 'chkUsuarioSexo', 11),

-- Views e Índices
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'View comum'), 'View para consultas (Notação Húngara: vw).', 'vw + NomeTabela', 'vwUsuarioProcesso', 12),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'View materializada'), 'View materializada (Notação Húngara: vm).', 'vm + Objetivo', 'vmProcessoUsuario', 12),

-- Procedures & Triggers
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Procedure'), 'Procedures de negócio (PascalCase, verbos).', 'Verbo + Substantivo', 'RegistrarCfc, CalcularDebito', 13),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Procedure'), 'Procedures Batch (Prefixo Batch).', 'Batch + Nome', 'BatchProcessarMultas', 14),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Nomenclatura de Objetos'), (SELECT id_objeto FROM objetos_db WHERE nome_objeto = 'Trigger'), 'Triggers (Notação Húngara: tg).', 'tg + Tabela + Evento', 'tgTabelaI, tgTabelaA', 16);

-- >>> BOAS PRÁTICAS
INSERT INTO regras_nomenclatura (id_categoria, id_objeto, descricao_regra, contexto_adicional, fonte_pagina) VALUES
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Todo comando SQL deve ser feito via Stored Procedure.', 'Programação', 18),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Integridade referencial deve ser via constraints (PK, Unique, FK).', 'Programação', 18),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Preferencialmente não utilizar cursor.', 'Programação', 18),
( (SELECT id_categoria FROM categorias_regras WHERE nome_categoria = 'Boas Práticas'), NULL, 'Evitar JOIN com mais de 4 tabelas (usar temporárias se necessário).', 'Programação', 19);

-- 3.1 Criação da tabela de exemplos práticos
DROP TABLE IF EXISTS exemplos_praticos;

CREATE TABLE exemplos_praticos (     --a ideia aqui é usar o maior nº possível de exemplos para ajudar a treinar G.A.N.D.A.L.F(Geração Automatizada de Normas do Detran-PE usando LLM para Fiscalização de boas práticas)
    id SERIAL PRIMARY KEY,
    objeto_foco VARCHAR(50),  
    exemplo_texto TEXT,       
    is_bom_exemplo BOOLEAN,   -- TRUE = Bom, FALSE = Ruim
    explicacao TEXT,
    embedding vector(768)
);
CREATE INDEX ON exemplos_praticos USING ivfflat (embedding vector_cosine_ops);

-- 4. DADOS AUXILIARES
TRUNCATE TABLE tipos_dados RESTART IDENTITY CASCADE;
INSERT INTO tipos_dados (tipo_dado_sybase, sigla_coluna, faixa_valores, espaco_ocupado) VALUES
('bit', 'b', '0 ou 1', '1 byte'),
('datetime, smalldatetime', 'd', 'Data e hora', '8 bytes'),
('text, image', 'I', 'Binários', 'Variável'),
('money', 'm', 'Monetário', '8 bytes'),
('numeric, int', 'n', 'Numéricos', 'Variável'),
('char, varchar', 's', 'String (Texto)', 'N bytes'), -- Ajustado sigla para 's' minusculo (hungara)
('Time', 't', 'Hora apenas', '-'),
('Booleano', 'bo', 'Lógico', '-');

TRUNCATE TABLE atributos_comuns RESTART IDENTITY CASCADE;
INSERT INTO atributos_comuns (atributo, tipo_dado_recomendado) VALUES
('Pessoas', 'Varchar(50)'),
('E-mail', 'Varchar(60)'),
('Telefone', 'Varchar(10)'),
('CEP', 'Numeric(8)'),
('Bairro', 'Varchar(60)'),
('CPF', 'Char(11)'),
('Login', 'Varchar(30)');

-- 5. USUÁRIOS (Safe Block para não dar erro se já existe)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'ollama_trainer') THEN
      CREATE ROLE ollama_trainer LOGIN PASSWORD '123456';
   END IF;
END
$do$;

GRANT ALL PRIVILEGES ON SCHEMA public TO ollama_trainer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO ollama_trainer;

-- 6. ÍNDICE FINAL
CREATE INDEX ON regras_nomenclatura USING hnsw (embedding vector_cosine_ops);
