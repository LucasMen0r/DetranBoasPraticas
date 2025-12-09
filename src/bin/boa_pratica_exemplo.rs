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
        INSERT INTO exemplos_praticos (objeto_foco, exemplo_texto, is_bom_exemplo, explicacao, embedding)
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
    sqlx::query("CREATE TABLE IF NOT EXISTS exemplos_praticos (id SERIAL PRIMARY KEY, objeto_foco TEXT, exemplo_texto TEXT, is_bom_exemplo BOOLEAN, explicacao TEXT, embedding vector(768));")
        .execute(&pool)
        .await?;
        
    sqlx::query("TRUNCATE TABLE exemplos_praticos RESTART IDENTITY;")
        .execute(&pool)
        .await?;

    // --- DADOS ---
    let exemplos = vec![
        //Views
        ExemploInput { foco: "View", texto: "vwUsuarioProcesso", is_bom: true, explicacao: "Prefixo 'vw' e notação húngara corretos." },
        ExemploInput { foco: "View", texto: "vmProcessoUsuario", is_bom: true, explicacao: "Prefixo 'vm' correto para Materialized Views." },
        ExemploInput { foco: "View", texto: "ViewUsuarios", is_bom: false, explicacao: "Prefixo incorreto e plural proibido." },
        //pk e fk
        ExemploInput { foco: "PK", texto: "pkVeiculo", is_bom: true, explicacao: "Prefixo 'pk' + NomeTabela correto." },
        ExemploInput { foco: "PK", texto: "id", is_bom: false, explicacao: "Nome genérico proibido." },
        ExemploInput { foco: "FK", texto: "fkVeiculo", is_bom: true, explicacao: "Prefixo 'fk' + TabelaPai correto." },
        ExemploInput { foco: "FK", texto: "FKveiculo", is_bom: false, explicacao: "Prefixo deve ser minúsculo 'fk'." },
        //tabelas
        ExemploInput { foco: "Tabela", texto: "Veiculo", is_bom: true, explicacao: "Singular e deve ser usada notação húngara." },
        ExemploInput { foco: "Tabela", texto: "tabela_veiculos", is_bom: false, explicacao: "Snake_case e plural proibidos." },
        ExemploInput { foco: "Tabela", texto: "LogParcelaDebito", is_bom: true, explicacao: "Tabelas de Log iniciam com 'Log'." },
        ExemploInput { foco: "Tabela", texto: "tmpRestricaoVeiculo", is_bom: true, explicacao: "Tabelas temp iniciam com 'tmp'." },
        //procedures
        ExemploInput { foco: "Procedure", texto: "BatchConsumoServicoWebS", is_bom: true, explicacao: "Prefixo 'Batch' correto." },
        ExemploInput { foco: "Procedure", texto: "VerificaAdvertenciaS.scp", is_bom: true, explicacao: "Verbo infinitivo + Sufixo." },
        ExemploInput { foco: "Procedure", texto: "PopulaVeiculoRoubadoSDS", is_bom: false, explicacao: "Falta sufixo padrão e verbo errado." },
    ];

    println!("Iniciando carga de {} exemplos.", exemplos.len());

    for item in exemplos {
        if let Err(e) = inserir_exemplo(&pool, &item).await {
            eprintln!(" Erro ao inserir '{}': {}", item.texto, e);
        }
    }
    Ok(())
}
