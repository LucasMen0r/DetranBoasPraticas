use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use pgvector::Vector;
use serde_json::json;
use std::error::Error;
use dotenv::dotenv;
use std::env;

// Estrutura para os dados processados (já auditados)
struct ExemploProcessado<'a> {
    foco: &'a str,
    texto: &'a str,
    is_bom: bool,
    explicacao: String, // String pois será gerada dinamicamente
}

//Revisão da nomenclatura
fn auditar_nomenclatura(foco: &str, texto: &str) -> (bool, String) {
    match foco {
        "View" => {
            if texto.starts_with("vw") {
                if !texto.contains('_') {
                    (true, "Correto: Inicia com prefixo 'vw' e usa PascalCase.".to_string())
                } else {
                    (false, "Erro: View inicia com 'vw' mas contem '_' (use PascalCase).".to_string())
                }
            } else if texto.starts_with("vm") {
                (true, "Correto: Inicia com prefixo 'vm' (View Materializada).".to_string())
            } else {
                (false, "Erro: Views devem iniciar obrigatoriamente com 'vw' ou 'vm'.".to_string())
            }
        },
        "Tabela" => {
            if texto.starts_with("tb") {
                (false, "Erro: Tabelas NÃO devem utilizar o prefixo 'tb'.".to_string())
            } else if texto.contains('_') {
                (false, "Erro: Tabelas devem usar PascalCase (sem underscores), não snake_case.".to_string())
            } else if texto.starts_with("Log") || texto.starts_with("tmp") {
                (true, "Correto: Uso aceito de prefixo especial (Log/tmp).".to_string())
            } else {
                // Checagem básica de plural (termina em 's' e não é exceção comum)
                if texto.ends_with("s") && !texto.ends_with("ss") && !texto.ends_with("is") { 
                    (false, "Atenção: Nome da tabela parece estar no plural (deve ser Singular).".to_string())
                } else {
                    (true, "Correto: Nome descritivo, no singular e em PascalCase.".to_string())
                }
            }
        },
        "Procedure" => {
            // Regra: Deve terminar com S, I, E, A, R
            let sufixos_validos = ['S', 'I', 'E', 'A', 'R'];
            let ultimo_char = texto.chars().last().unwrap_or(' ');
            
            if texto.starts_with("Batch") {
                (true, "Correto: Procedure de processamento em lote inicia com 'Batch'.".to_string())
            } else if sufixos_validos.contains(&ultimo_char) {
                 (true, format!("Correto: Termina com a sigla da operação '{}'.", ultimo_char))
            } else {
                 (false, "Erro: Procedures de CRUD devem terminar com a sigla da operação (S,I,E,A,R).".to_string())
            }
        },
        "PK" | "pk" => {
             // Aceita tanto "pk" quanto "PK" no foco, mas valida o texto
             if texto.starts_with("pk") && !texto.contains('_') {
                 (true, "Correto: Prefixo 'pk' + NomeTabela em PascalCase.".to_string())
             } else {
                 (false, "Erro: Chaves primárias devem ser 'pk' + NomeTabela.".to_string())
             }
        },
        "FK" | "fk" => {
             if texto.starts_with("fk") {
                 (true, "Correto: Prefixo 'fk' + NomeTabela.".to_string())
             } else {
                 (false, "Erro: Chaves estrangeiras devem iniciar com 'fk'.".to_string())
             }
        },
        _ => (true, "Validação genérica: formato aceito para fins de exemplo.".to_string()),
    }
}

async fn get_embedding(text: &str) -> Result<Vector, Box<dyn Error>> {
    let client = reqwest::Client::new();
    // Pega do .env ou usa o padrão.
    let ollama_url = env::var("OLLAMA_HOST").unwrap_or_else(|_| "http://localhost:11436".to_string());
    
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
    item: &ExemploProcessado<'_>
) -> Result<(), Box<dyn Error>> {
    
    let prompt_composto = format!("{} : {}", item.foco, item.texto);
    let embedding = get_embedding(&prompt_composto).await?;

    // ATENÇÃO: Nomes das colunas atualizados para PascalCase conforme seu banco novo
    sqlx::query(
        r#"
        INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, is_BomExemplo, Explicacao, embedding)
        VALUES ($1, $2, $3, $4, $5)
        "#
    )
    .bind(item.foco)
    .bind(item.texto)
    .bind(item.is_bom)
    .bind(&item.explicacao)
    .bind(embedding)
    .execute(pool)
    .await?;

    let status = if item.is_bom { "BOM" } else { "RUIM" };
    println!("Processado: [{}] {} -> {}", item.foco, status, item.texto);
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
    sqlx::query("CREATE EXTENSION IF NOT EXISTS vector;")
        .execute(&pool)
        .await?;
    println!("Iniciando R.A.G. revisor");
    println!("Recriando tabela ExemploPratico");
    
    // Criação da tabela com nomes PascalCase e PK correta
    sqlx::query("CREATE TABLE IF NOT EXISTS ExemploPratico (
        pkExemploPratico SERIAL PRIMARY KEY, 
        ObjetoFoco TEXT, 
        ExemploTexto TEXT, 
        is_BomExemplo BOOLEAN, 
        Explicacao TEXT, 
        embedding vector(768));")
        .execute(&pool)
        .await?;
        
    sqlx::query("TRUNCATE TABLE ExemploPratico RESTART IDENTITY;")
        .execute(&pool)
        .await?;

    // O Rust vai decidir se é bom ou ruim sem a necessidade de interferência externa.
    let dados_brutos = vec![
        // VIEWS
        ("View", "vwUsuarioProcesso"),      // Deve ser BOM
        ("View", "vmProcessoUsuario"),      // Deve ser BOM
        ("View", "ViewUsuarios"),           // Deve ser RUIM
        ("View", "vw_usuario_log"),         // Deve ser RUIM (snake_case)
        
        // TABELAS
        ("Tabela", "Veiculo"),              // Deve ser BOM
        ("Tabela", "tbVeiculo"),            // Deve ser RUIM
        ("Tabela", "tabela_veiculos"),      // Deve ser RUIM
        ("Tabela", "LogParcelaDebito"),     // Deve ser BOM
        ("Tabela", "Veiculos"),             // Deve ser RUIM (Plural)

        // PROCEDURES
        ("Procedure", "BatchConsumoServicoWebS"), // Deve ser BOM
        ("Procedure", "VerificaAdvertenciaS"),    // Deve ser BOM
        ("Procedure", "CalculaMulta"),            // Deve ser RUIM
        ("Procedure", "AtualizarDadosCliente"),   // Deve ser RUIM
        
        // CHAVES
        ("PK", "pkVeiculo"),                // Deve ser BOM
        ("PK", "id_veiculo"),               // Deve ser RUIM
        ("FK", "fkVeiculoCategoria"),       // Deve ser BOM
        ("FK", "FK_Carro"),                 // Deve ser RUIM
    ];

    println!("Iniciando carga e auditoria de {} exemplos.", dados_brutos.len());

    for (foco, texto) in dados_brutos {
        // 1. APLICA A REGRA (AUDITORIA)
        let (is_bom_auto, explicacao_auto) = auditar_nomenclatura(foco, texto);

        // 2. MONTA O OBJETO
        let item = ExemploProcessado {
            foco,
            texto,
            is_bom: is_bom_auto,
            explicacao: explicacao_auto,
        };

        // 3. INSERE NO BANCO
        if let Err(e) = inserir_exemplo(&pool, &item).await {
            eprintln!("Erro ao inserir '{}': {}", item.texto, e);
        }
    }
    
    println!("Carga concluída com sucesso!");
    Ok(())
}
