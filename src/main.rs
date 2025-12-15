use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use pgvector::Vector;
use serde_json::json;
use std::error::Error;
use dotenv::dotenv;
use std::env;

struct ExemploInput<'a> {
    foco: &'a str,
    texto: &'a str,
    is_bom: bool,
    explicacao: &'a str,
}

async fn get_embedding(text: &str) -> Result<Vector, Box<dyn Error>> {
    let client = reqwest::Client::new();

    let ollama_url = env::var("OLLAMA_HOST").unwrap_or_else(|_| "http://localhost:11434".to_string());
    let url = format!("{}/api/embeddings", ollama_url);

    let res = client
        .post(&url)
        .json(&json!({
            "model": "nomic-embed-text:latest",
            "prompt": text
        }))
        .send()
        .await?;

    let json_body: serde_json::Value = res.json().await?;
    let vec_data: Vec<f32> = serde_json::from_value(json_body["embedding"].clone())?;
    Ok(Vector::from(vec_data))
}
async fn inserir_exemplo(
    pool: &Pool<Postgres>,
    item: &ExemploInput<'_>
) -> Result<(), Box<dyn Error>> {
    println!("Vetorizando: {}", item.texto);
    
    let prompt_composto = format!("{} : {}", item.foco, item.texto);
    let embedding = get_embedding(&prompt_composto).await?;

    sqlx::query(
        r#"
        INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, isBomExemplo, Explicacao, embedding)
        VALUES ($1, $2, $3, $4, $5)
        "#
    )
    .bind(item.foco)
    .bind(item.texto)
    .bind(item.is_bom)
    .bind(item.explicacao)
    .bind(embedding)
    .execute(pool)
    .await?;

    let status = if item.is_bom { "BOM" } else { "RUIM" };
    println!("Inserido [{}] -> {}", status, item.texto);
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    dotenv().ok();
    let database_url = env::var("DATABASE_URL").expect("DATABASE_URL deve estar no .env");

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    println!("Limpando tabela antiga.");
    // Cria a tabela se não existir
    sqlx::query("CREATE TABLE IF NOT EXISTS ExemploPratico (id SERIAL PRIMARY KEY, ObjetoFoco TEXT, ExemploTexto TEXT, isBomExemplo BOOLEAN, Explicacao TEXT, embedding vector(768));")
        .execute(&pool)
        .await?;
        
    sqlx::query("TRUNCATE TABLE ExemploPratico RESTART IDENTITY;")
        .execute(&pool)
        .await?;

       // --- DADOS ---
   let exemplos = vec![
        // VIEWS
        ExemploInput {
            foco: "View",
            texto: "vwUsuarioProcesso",
            is_bom: true,
            explicacao: "Prefixo 'vw' e notação húngara; deve-se usar a mesma semântica utilizada para as tabelas. Para views não materializadas deve ser prefixada a palavra “vw” seguido do nome da tabela.",
        },
        ExemploInput {
            foco: "View",
            texto: "vmProcessoUsuario",
            is_bom: true,
            explicacao: "Prefixo 'vm' aplica-se para Views materializadas, ou seja, Views que armazenam dados em disco para serem usadas em relatórios de BI e em análises, a título de exemplo; deve-se usar a mesma semântica utilizada para as tabelas.",
        },
        ExemploInput {
            foco: "View",
            texto: "ViewMatUsuario",
            is_bom: false,
            explicacao: "Views materializadas utilizam o prefixo 'vm' para descrever uma View materializada.",
        },
        ExemploInput {
            foco: "View",
            texto: "ViewUsuarios",
            is_bom: false,
            explicacao: "Prefixo 'View' por extenso (deve ser 'vw') e uso da palavra 'Usuarios' no plural, o que viola as regras de nomenclatura das tabelas.",
        },

        // PRIMARY KEYS
        ExemploInput {
            foco: "pk",
            texto: "pkVeiculo",
            is_bom: true,
            explicacao: "Prefixo 'pk' + NomeTabela. Utilização dos atributos considerados identificadores naturais das tabelas, acrescidos do nome da tabela; Ex.: a tabela Servico, terá como pkServico como chave primária. Quando a tabela for de relacionamento, os nomes dos campos que compõem a chave primária devem ser mantidos dos campos que foram trazidos das tabelas de origem. Esses campos serão ao mesmo tempo chaves primárias e estrangeiras; Ex.: Na tabela ServicoTaxa, a chave primária será a pk da tabela Servico(pkServico) bem como a pk da tabela Taxa (pkTaxa)",
        },
        ExemploInput {
            foco: "PK",
            texto: "id",
            is_bom: false,
            explicacao: "Nome genérico, deve identificar a tabela e a sigla 'pk' deve estar escrita em letras minúsculas",
        },

        // FOREIGN KEYS
        ExemploInput {
            foco: "FK",
            texto: "fkVeiculo",
            is_bom: true,
            explicacao: "Usar o prefixo fk mais os nomes das tabelas filha e pai. Veiculo é a tabela-pai, pkVeiculo é a sua chave primária, a tabela filha, Servico, tem a sua própria pk[pkServico], e a fk será 'fkServicoVeiculo'. Quando existir mais de uma “fk” para a mesma tabela pai, deve-se usar um número sequencial no final do nome da “fk”. Exemplo: fkVeiculoCategoriaVeiculo01",
        },
        ExemploInput {
            foco: "FK",
            texto: "FKveiculo",
            is_bom: false,
            explicacao: "O prefixo é fk, em letras minúsculas, semelhante à regra aplicável para as chaves primárias, a forma correta é: fk + [Nome da tabela-pai].",
        },

        // PROCEDURES
        ExemploInput {
            foco: "Procedure",
            texto: "BatchConsumoServicoWebS",
            is_bom: true,
            explicacao: "Usar sigla, em letra maiúscula, das operações básicas: Selecionar (S),Inserir (I), Excluir (E), Alterar (A), Relatório (R); Quando a procedure for executada via processamento batch, deve-se colocar no início do nome da procedure a palavra “Batch”.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "dbvcen..ProcEletronicoTransacaoListarS.scp",
            is_bom: true,
            explicacao: "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "BatchConsumoServicoWebA",
            is_bom: true,
            explicacao: "Usar sigla, em letra maiúscula, das operações básicas: Selecionar (S),Inserir (I), Excluir (E), Alterar (A), Relatório (R); Quando a procedure for executada via processamento batch, deve-se colocar no início do nome da procedure a palavra “Batch”.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "BatchConsumoServicoWebMover",
            is_bom: true,
            explicacao: "Usar sigla, em letra maiúscula, das operações básicas: Selecionar (S),Inserir (I), Excluir (E), Alterar (A), Relatório (R); Quando a procedure for executada via processamento batch, deve-se colocar no início do nome da procedure a palavra “Batch”.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "VeiculoRoubadoPopularSds.sco",
            is_bom: true,
            explicacao: "Inicia com verbo/ação, notação húngara.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "dbinfracao..ConsultaCancelamentoOrgaoS.scp",
            is_bom: true,
            explicacao: "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "dbinfracao..SitInfracaoE.scp",
            is_bom: true,
            explicacao: "o Manual pede objetivo[complemento]operacao e se as operações não for de S, I, E, A, R o verbo deve estar no infinitivo",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "VerificaAdvertenciaS.scp",
            is_bom: true,
            explicacao: "Inicia com verbo/ação, notação húngara.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "dbvcen.dbo.ProcessoEletroAberturaAnalisar",
            is_bom: true,
            explicacao: "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "Operacao..VeiculoRoubadoAtualizarSds.scp",
            is_bom: false,
            explicacao: "De acordo com o manual: Nome de procedure: Objetivo[Complemento]Operacao.",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "PopulaVeiculoRoubadoSDS",
            is_bom: false,
            explicacao: "o Manual pede objetivo[complemento]operacao e se as operações não for de S, I, E, A, R o verbo deve estar no infinitivo",
        },
        ExemploInput {
            foco: "Procedure",
            texto: "Operacao..VeiculoRoubadoPopularSDS.sco",
            is_bom: false,
            explicacao: "o Manual pede objetivo[complemento]operacao e se as operações não for de S, I, E, A, R o verbo deve estar no infinitivo",
        },
        // TABELAS
        ExemploInput {
            foco: "Tabela",
            texto: "Carro",
            is_bom: true,
            explicacao: "Sem prefixo 'tb' e foi utilizado o nome completo do termo que compõe a tabela.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "Veiculo",
            is_bom: true,
            explicacao: "O nome de uma tabela deverá ser sugestivo. Deve-se fazer o uso de nomenclatura orientado a objeto, por exemplo: se no departamento financeiro for necessário manter uma tabela de feriados, esta tabela deve ser nomeada identificando claramente seu conteúdo, isto significa que seu nome então deverá ser Feriado; O nome da tabela deve estar sempre no singular; Utilização dos nomes completos dos termos que compõem o nome da tabela, excetuando-se quando isto não for possível devido à limitação da quantidade de caracteres que o SGBD impõe (30 caracteres). Neste caso, os termos devem ser abreviados sem perder a coerência do entendimento;",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "MotoApreensao",
            is_bom: true,
            explicacao: "Notação Húngara é a diferenciação dos elementos de uma dada nomenclatura através do uso de letras maiúsculas e letras minúsculas. Tem a sua origem na codificação de programas. Para o nosso padrão de nomenclatura vamos utilizar uma versão adaptada desta notação que é o uso da letra maiúscula no início de cada elemento do nome.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "LogParcelaDebito",
            is_bom: true,
            explicacao: "Quando a tabela for de Log, deve-se usar o nome da tabela antecedida do termo “Log”. Obs.: Tabelas de Log não terão chave estrangeira (fk) no entanto terão chave primária(pk).",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "tmpRestricaoVeiculo",
            is_bom: true,
            explicacao: "Tabela temporária(tmp): É uma tabela que é usada de forma auxiliar, cujo conteúdo será excluído pela própria aplicação.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "pxProtLaudoToxicologico",
            is_bom: true,
            explicacao: "Tabela do tipo Proxy: As Proxy tables são tabelas “espelho” ou de referência que permite acessar dados que estão em outro banco de dados ou servidor, como se estivessem no banco local. Sua nomenclatura deverá ser composta por px<Origem><NomeDoObjeto>",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "tabela_veiculos",
            is_bom: false,
            explicacao: "Usa snake_case e a palavra 'veiculos' está no plural.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "TemporariaMotoRegistro",
            is_bom: false,
            explicacao: "Viola a nomenclatura padrão das tebelas temporárias ao desrespeitar a regra-padrão de iniciar tabelas temporárias com 'tmp' seguido do nome da tabela.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "LOGParcelaDeb",
            is_bom: false,
            explicacao: "Quando a tabela for de Log, deve-se usar o nome da tabela antecedida do termo “Log”. LOGParcelaDebito viola a regra de uso de notação húngara e a regra de nomenclatura das tabelas, ao usar 'Deb' no lugar de 'Debito', impedindo a rápida compreensão da sua funcionalidade.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "tbVeiculo",
            is_bom: false,
            explicacao: "Presença do prefixo 'tb' e e ausência da notação húngara.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "tabela_cnh",
            is_bom: false,
            explicacao: "Usa snake_case; A notação húngara é a utilização do 1o caracter de cada termo em maiúsculo, ou seja, primeira letra em maiúscula, demais em minúsculas. Para cada palavra interna, primeira letra em maiúscula, notação húngara; Siglas como IPVA, CNPJ, CNH, FEBRABAN obedecerá a mesma regra sendo a primeira letra maiúscula e as demais minúsculas.",
        },
        ExemploInput {
            foco: "Tabela",
            texto: "PXProt_Laudotoxicologico",
            is_bom: false,
            explicacao: "As Proxy tables são tabelas “espelho” ou de referência que permite acessar dados que estão em outro banco de dados ou servidor, como se estivessem no banco local. Sua nomenclatura deverá ser composta por px<Origem><NomeDoObjeto>; no caso está equivocado a nomenclatura por violar a regras das proxy table e o uso da notação húngara.",
        },
    ];

    println!("Iniciando carga de {} exemplos.", exemplos.len());

    for item in exemplos {
        if let Err(e) = inserir_exemplo(&pool, &item).await {
            eprintln!(" Erro ao inserir '{}': {}", item.texto, e);
        }
    }
    Ok(())
}
