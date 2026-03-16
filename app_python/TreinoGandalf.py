import pgvector
import psycopg2
from psycopg2 import pool
import hashlib
from datetime import datetime
import os
import requests
import time
import shutil
from dotenv import load_dotenv
import pgvector.psycopg2

# Configurações estritas via variáveis de ambiente
load_dotenv()

def get_env_or_raise(var_name):
    value = os.getenv(var_name)
    if not value:
        raise EnvironmentError(f"[CRÍTICO] Variável de ambiente {var_name} não configurada.")
    return value

try:
    DB_NAME = get_env_or_raise('DB_NAME')
    DB_USER = get_env_or_raise('DB_USER')
    DB_PASS = get_env_or_raise('DB_PASS')
    DB_HOST = get_env_or_raise('DB_HOST')
    DB_PORT = get_env_or_raise('DB_PORT')
except EnvironmentError as e:
    print(e)
    exit(1)

# Configurações de IA
ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{DB_HOST}:11436" 
ollama_api_embed = f"{ollama_base_url}/api/embeddings"

DIRETORIO_TESTES = "arquivos_teste"
DIRETORIO_PROCESSADOS = "arquivos_processados"

# Inicialização do Pool de Conexões para maior resiliência [cite: 1]
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
    )
except psycopg2.Error as e:
    print(f"[ERRO] Falha ao criar pool de conexões: {e}")
    exit(1)

def calcular_hash_arquivo(caminho):
    """Gera um hash SHA256 para evitar reprocessamento de arquivos idênticos."""
    sha256_hash = hashlib.sha256()
    with open(caminho, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def embedtext(text): 
    try: 
        resposta = requests.post( 
            ollama_api_embed, 
            json={"model": ollama_embed_model, "prompt": text},
            timeout=30
        ) 
        resposta.raise_for_status() 
        return resposta.json()['embedding'] 
    except requests.RequestException as e: 
        registrar_log(f"[ERRO OLLAMA] Falha ao vetorizar: {e}") 
        return None

def criar_chunks(texto, tamanho_maximo=400, sobreposicao=50):
    if sobreposicao >= tamanho_maximo:
        raise ValueError("A sobreposição deve ser menor que o tamanho máximo do chunk.")
    palavras = texto.split()
    chunks = []
    i = 0
    while i < len(palavras):
        chunk = " ".join(palavras[i:i + tamanho_maximo])
        chunks.append(chunk)
        i += (tamanho_maximo - sobreposicao)
    return chunks

def sanitizartexto(texto_bruto):
    if not texto_bruto:
        return ""
    linhas = texto_bruto.split('\n')
    linhas_limpas = [linha.strip() for linha in linhas if linha.strip()]
    return " ".join(linhas_limpas)

def processardiretorio(conn):
    os.makedirs(DIRETORIO_TESTES, exist_ok=True)
    os.makedirs(DIRETORIO_PROCESSADOS, exist_ok=True)
    
    arquivos = [f for f in os.listdir(DIRETORIO_TESTES) if f.endswith('.txt')]
    if not arquivos:
        registrar_log(f"[INFO] Nenhum arquivo .txt encontrado em '{DIRETORIO_TESTES}'.")
        return

    cursor = conn.cursor()
    total_inseridos = 0

    for arquivo in arquivos:
        caminho_origem = os.path.join(DIRETORIO_TESTES, arquivo)
        caminho_destino = os.path.join(DIRETORIO_PROCESSADOS, arquivo)
        
        # Lógica de Hash para evitar duplicidade [cite: 1]
        hash_arquivo = calcular_hash_arquivo(caminho_origem)
        cursor.execute("SELECT 1 FROM ConhecimentoHistorico WHERE nome_arquivo = %s LIMIT 1", (arquivo,))
        
        if cursor.fetchone():
            registrar_log(f"[PULADO] Arquivo '{arquivo}' já processado anteriormente.")
            shutil.move(caminho_origem, caminho_destino)
            continue

        registrar_log(f"Processando arquivo: {arquivo}...")
        try:
            with open(caminho_origem, 'r', encoding='utf-8') as f:
                conteudo_bruto = f.read()
                
            texto_limpo = sanitizartexto(conteudo_bruto)
            if not texto_limpo:
                shutil.move(caminho_origem, caminho_destino)
                continue

            chunks = criar_chunks(texto_limpo)
            for chunk in chunks:
                vetor = embedtext(chunk)
                if vetor:
                    cursor.execute("""
                        INSERT INTO ConhecimentoHistorico (nome_arquivo, conteudo_texto, embedding)
                        VALUES (%s, %s, %s)
                    """, (arquivo, chunk, vetor))
                    total_inseridos += 1
            
            conn.commit()
            shutil.move(caminho_origem, caminho_destino)
            registrar_log(f"  -> Sucesso. Chunks: {len(chunks)}.")
            
        except Exception as e:
            conn.rollback()
            registrar_log(f"  -> [ERRO] Falha no arquivo {arquivo}: {e}")

    cursor.close()
    registrar_log(f"Processamento concluído. Inserções: {total_inseridos}")

def autotreinar(conn):
    """Processa regras e exemplos pendentes (sem embedding). [cite: 1]"""
    cursor = conn.cursor()
    try:
        # Regras de Nomenclatura
        cursor.execute("SELECT pkRegraNomenclatura, DescricaoRegra FROM RegraNomenclatura WHERE embedding IS NULL")
        regras = cursor.fetchall()
        if regras:
            registrar_log(f"[AUTO-TREINO] Atualizando {len(regras)} regras...")
            for pk, texto in regras:
                vetor = embedtext(texto)
                if vetor:
                    cursor.execute("UPDATE RegraNomenclatura SET embedding = %s WHERE pkRegraNomenclatura = %s", (vetor, pk))
            conn.commit()

        # Exemplos Práticos
        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if cursor.fetchone()[0]:
            cursor.execute("SELECT pkExemploPratico, ExemploTexto, Explicacao FROM ExemploPratico WHERE embedding IS NULL")
            exemplos = cursor.fetchall()
            if exemplos:
                registrar_log(f"[AUTO-TREINO] Atualizando {len(exemplos)} exemplos...")
                for pk, texto, explicacao in exemplos:
                    vetor = embedtext(f"Exemplo: {texto}. Explicação: {explicacao}")
                    if vetor:
                        cursor.execute("UPDATE ExemploPratico SET embedding = %s WHERE pkExemploPratico = %s", (vetor, pk))
                conn.commit()
    except Exception as e:
        conn.rollback()
        registrar_log(f"[ERRO] Falha no auto-treino: {e}")
    finally:
        cursor.close()

def registrar_log(mensagem):
    diretorio = "memoria_teste_n_supervisionado"
    os.makedirs(diretorio, exist_ok=True)
    caminho_arquivo = os.path.join(diretorio, "log_fim_de_semana.txt")
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    with open(caminho_arquivo, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {mensagem}\n")
    print(mensagem)

def main():
    registrar_log("Iniciando rotina profissional de manutenção do Gandalf.")
    
    while True:
        conn = None
        try:
            conn = db_pool.getconn() # Obtém conexão do pool [cite: 1]
            pgvector.psycopg2.register_vector(conn)
            
            autotreinar(conn)
            processardiretorio(conn)
            
            registrar_log("Ciclo concluído com sucesso.")
        except Exception as e:
            registrar_log(f"[ERRO CRÍTICO NO LOOP]: {e}")
        finally:
            if conn:
                db_pool.putconn(conn) # Devolve a conexão ao pool
            
        registrar_log("Aguardando 30 minutos...")
        time.sleep(1800)

if __name__ == "__main__":
    main()