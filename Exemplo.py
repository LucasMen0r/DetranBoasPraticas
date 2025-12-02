import psycopg2
import requests
import pgvector.psycopg2

db_params = {
    "dbname": "DetranNorma",
    "user": "postgres",
    "password": "abc321",
    "host": "localhost",
    "port": "5432"
}

def getembedding(text):
    url = "http://localhost:11434/api/embeddings"
    try:
        resp = requests.post(url, json={"model": "nomic-embed-text:latest", "prompt": text})
        return resp.json()['embedding']
    except Exception as e:
        print(f"Erro ao vetorizar: {e}")
        return None
    
def inserrirexemplo(conn, foco, texto, is_bom, explicacao):
    vec = getembedding(f"{foco} : {texto}")
    cursor = conn.cursor()
    cursor.execute("""
        insert into exemplos_praticos (objeto_foco, exemplo_texto, is_bom_exemplo, explicacao, embedding)
        values (%s, %s, %s, %s, %s)
    """, (foco, texto, is_bom, explicacao, vec))
    conn.commit()

    if is_bom:
        status = True
    else:
        status = False
    print(f"Exemplo inserido com sucesso: {status} -> {texto}")

##exemplos = [
    # TABELAS
    ("Tabela", "tbVeiculo", True, "Usa prefixo 'tb' e PascalCase."),
    ("Tabela", "tabela_veiculos", False, "Usa snake_case e prefixo longo."),
    ("Tabela", "Carros", False, "Sem prefixo 'tb'."),
    
    # PROCEDURES
    ("Procedure", "BatchProcessarMultas", True, "Inicia com verbo/ação, PascalCase."),
    ("Procedure", "proc_calcula_juros", False, "Usa snake_case e prefixo 'proc'."),
    
    # VIEWS
    ("View", "vwRelatorioDiario", True, "Prefixo 'vw' e PascalCase."),
    ("View", "ViewUsuarios", False, "Prefixo 'View' por extenso (deve ser 'vw')."),
    
    # PRIMARY KEYS
    ("PK", "pkVeiculo", True, "Prefixo 'pk' + NomeTabela."),
    ("PK", "id", False, "Nome genérico, deve identificar a tabela."),
##]

try:
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    cursor.execute("TRUNCATE TABLE exemplos_praticos RESTART IDENTITY;")
    conn.commit()
    
    print("Iniciando carga de exemplos.")
    for item in exemplos:
        inserir_exemplo(conn, item[0], item[1], item[2], item[3])

    conn.close()
    print("\nSucesso! Tabela de exemplos populada.")
except Exception as e:
    print(f"Erro: {e}")
