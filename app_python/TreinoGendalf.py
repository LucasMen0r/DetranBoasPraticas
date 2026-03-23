import pgvector
import psycopg2
from psycopg2 import pool
from datetime import datetime
import os
import re
import requests
import time
import shutil
from dotenv import load_dotenv
import pgvector.psycopg2

diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.abspath(os.path.join(diretorio_atual, '..', '.env'))

load_dotenv(dotenv_path=caminho_env)

def get_env_or_raise(var_name):
    value = os.getenv(var_name)
    if not value:
        raise EnvironmentError(f"[CRÍTICO] Variável de ambiente {var_name} não configurada.")
    return value

try:
    DB_NAME = os.getenv('DB_NAME', 'DetranNorma')
    DB_USER = os.getenv('DB_USER', 'ollama_trainer')
    DB_PASS = os.getenv('DB_PASS', '123456')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5435')
except EnvironmentError as e:
    print(e)
    exit(1)

ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = os.getenv('OLLAMA_HOST', 'http://localhost:11436')
ollama_api_embed = f"{ollama_base_url}/api/embeddings"

DIRETORIO_TESTES = "perguntas_geradas"
DIRETORIO_PROCESSADOS = "arquivos_processados"

try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
    )
except psycopg2.Error as e:
    print(f"[ERRO] Falha ao criar pool de conexões: {e}")
    exit(1)

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

def criar_chunks(texto_bruto):
    """
    Fatia o texto de forma semântica. 
    Se o arquivo seguir o padrão do gerador, extrai blocos exatos de Q&A.
    Caso contrário, aplica um fallback genérico.
    """
    # Procura pelo padrão: Categoria, Pergunta e Resposta delimitados no seu .txt
    padrao = r"CATEGORIA:\s*(.*?)\n={40}\nPERGUNTA:\s*(.*?)\n={40}\nRESPOSTA:\n(.*?)\n={40}"
    matches = re.findall(padrao, texto_bruto, re.DOTALL)
    
    chunks = []
    
    # Se encontrou o formato esperado, cria os chunks lógicos
    if matches:
        for categoria, pergunta, resposta in matches:
            chunk = f"CATEGORIA: {categoria.strip()}\nPERGUNTA: {pergunta.strip()}\nRESPOSTA: {resposta.strip()}"
            chunks.append(chunk)
    else:
        # Fallback: Se for um texto solto, faz um fatiamento mais suave por parágrafos longos
        palavras = texto_bruto.split()
        if len(palavras) > 0:
            chunks = [" ".join(palavras[i:i + 350]) for i in range(0, len(palavras), 300)]
            
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
            falha_no_embedding = False
            
            for chunk in chunks:
                vetor = embedtext(chunk)
                if vetor:
                    cursor.execute("""
                        INSERT INTO ConhecimentoHistorico (nome_arquivo, conteudo_texto, embedding)
                        VALUES (%s, %s, %s)
                    """, (arquivo, chunk, vetor))
                    total_inseridos += 1
                else:
                    falha_no_embedding = True
                    break # Interrompe os chunks se a API do Ollama falhar
            
            if falha_no_embedding:
                conn.rollback()
                registrar_log(f"  -> [ERRO] Falha ao vetorizar um chunk de {arquivo}. Arquivo preservado para retentativa.")
            else:
                conn.commit()
                shutil.move(caminho_origem, caminho_destino)
                registrar_log(f"  -> Sucesso. Chunks: {len(chunks)}.")
            
        except Exception as e:
            conn.rollback()
            registrar_log(f"  -> [ERRO] Falha no arquivo {arquivo}: {e}")

    cursor.close()
    registrar_log(f"Processamento concluído. Inserções: {total_inseridos}")

def autotreinar(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT pkRegraNomenclatura, DescricaoRegra FROM RegraNomenclatura WHERE embedding IS NULL")
        regras = cursor.fetchall()
        if regras:
            registrar_log(f"[AUTO-TREINO] Atualizando {len(regras)} regras...")
            for pk, texto in regras:
                vetor = embedtext(texto)
                if vetor:
                    cursor.execute("UPDATE RegraNomenclatura SET embedding = %s WHERE pkRegraNomenclatura = %s", (vetor, pk))
            conn.commit()

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
            conn = db_pool.getconn()
            pgvector.psycopg2.register_vector(conn)
            
            autotreinar(conn)
            processardiretorio(conn)
            
            registrar_log("Ciclo concluído com sucesso.")
        except Exception as e:
            registrar_log(f"[ERRO CRÍTICO NO LOOP]: {e}")
        finally:
            if conn:
                db_pool.putconn(conn)
            
        registrar_log("Aguardando 30 minutos.")
        time.sleep(1800)

if __name__ == "__main__":
    main()