import os
import re
import requests
import psycopg2
import pgvector.psycopg2

# Configuracoes do Banco de Dados
DB_NAME = 'DetranNorma'
DB_USER = 'postgres'
DB_PASS = 'abc321'
DB_HOST = 'localhost'
DB_PORT = '5435'

# Configuracoes do Ollama
OLLAMA_BASE_URL = f"http://{DB_HOST}:11436"
OLLAMA_API_EMBED = f"{OLLAMA_BASE_URL}/api/embeddings"
OLLAMA_EMBED_MODEL = "nomic-embed-text:latest"

# Diretorio alvo
DIRETORIO_TESTES = "memoria_testes"

def conectar_db():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        pgvector.psycopg2.register_vector(conn)
        return conn
    except psycopg2.Error as e:
        print(f"[ERRO DB] Falha na conexao: {e}")
        return None

def criar_tabela_se_nao_existir(conn):
    cursor = conn.cursor()
    query = """
    CREATE TABLE IF NOT EXISTS ConhecimentoHistorico (
        id SERIAL PRIMARY KEY,
        nome_arquivo VARCHAR(255),
        conteudo_texto TEXT,
        embedding vector(768)
    );
    """
    try:
        cursor.execute(query)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERRO DB] Falha ao criar tabela: {e}")
        raise
    finally:
        cursor.close()

def arquivo_ja_processado(conn, nome_arquivo):
    cursor = conn.cursor()
    query = "SELECT EXISTS(SELECT 1 FROM ConhecimentoHistorico WHERE nome_arquivo = %s)"
    cursor.execute(query, (nome_arquivo,))
    existe = cursor.fetchone()[0]
    cursor.close()
    return existe

def sanitizar_texto(texto_bruto):
    if not texto_bruto:
        return ""
    
    texto = re.sub(r'\[\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\]', '', texto_bruto)
    texto = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '', texto)
    texto = re.sub(r'\[INFO\]|\[ERRO\]|\[DEBUG\]', '', texto)
    texto = re.sub(r'={3,}|-{3,}|#{3,}', '', texto)
    texto = re.sub(r'\n\s*\n', '\n', texto)
    
    return texto.strip()

def criar_chunks(texto, tamanho_maximo=400, sobreposicao=50):
    palavras = texto.split()
    chunks = []
    i = 0
    while i < len(palavras):
        chunk = " ".join(palavras[i:i + tamanho_maximo])
        chunks.append(chunk)
        i += tamanho_maximo - sobreposicao
    return chunks

def gerar_embedding(texto):
    try:
        resposta = requests.post(
            OLLAMA_API_EMBED,
            json={"model": OLLAMA_EMBED_MODEL, "prompt": texto}
        )
        resposta.raise_for_status()
        return resposta.json().get('embedding')
    except requests.RequestException as e:
        print(f"[ERRO OLLAMA] Falha ao vetorizar chunk: {e}")
        return None

def processar_diretorio(conn):
    if not os.path.exists(DIRETORIO_TESTES):
        print(f"[ERRO] O diretorio '{DIRETORIO_TESTES}' nao foi encontrado.")
        return

    arquivos = [f for f in os.listdir(DIRETORIO_TESTES) if f.endswith('.txt')]
    
    if not arquivos:
        print(f"[INFO] Nenhum arquivo .txt encontrado em '{DIRETORIO_TESTES}'.")
        return

    cursor = conn.cursor()
    total_inseridos = 0

    for arquivo in arquivos:
        print(f"Processando arquivo: {arquivo}...")
        
        if arquivo_ja_processado(conn, arquivo):
            print(f"  -> Arquivo ja existente no banco de dados. Ignorado para evitar duplicidade.")
            continue

        caminho_completo = os.path.join(DIRETORIO_TESTES, arquivo)
        
        try:
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                conteudo_bruto = f.read()
                
            texto_limpo = sanitizar_texto(conteudo_bruto)
            
            if not texto_limpo:
                print(f"  -> Arquivo vazio ou continha apenas ruido. Ignorado.")
                continue

            chunks = criar_chunks(texto_limpo)
            chunks_inseridos_arquivo = 0
            
            for chunk in chunks:
                vetor = gerar_embedding(chunk)
                if vetor:
                    query = """
                    INSERT INTO ConhecimentoHistorico (nome_arquivo, conteudo_texto, embedding)
                    VALUES (%s, %s, %s)
                    """
                    cursor.execute(query, (arquivo, chunk, vetor))
                    chunks_inseridos_arquivo += 1
                    total_inseridos += 1
                    
            conn.commit()
            print(f"  -> Sucesso. Chunks inseridos: {chunks_inseridos_arquivo}")
            
        except Exception as e:
            conn.rollback()
            print(f"  -> [ERRO] Falha ao processar o arquivo {arquivo}: {e}")

    cursor.close()
    print("-" * 40)
    print(f"Processamento concluido. Total de registros inseridos no banco: {total_inseridos}")

def main():
    print("Iniciando pipeline de ingestao de dados...")
    conn = conectar_db()
    if not conn:
        return
        
    try:
        criar_tabela_se_nao_existir(conn)
        processar_diretorio(conn)
    finally:
        conn.close()
        print("Conexao com o banco de dados encerrada.")

if __name__ == "__main__":
    main()
