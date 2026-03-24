import pgvector
import psycopg2
from psycopg2 import pool
from datetime import datetime
import os
import re
import json
import requests
import time
import shutil
from dotenv import load_dotenv
import pgvector.psycopg2

diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.abspath(os.path.join(diretorio_atual, '..', '.env'))

load_dotenv(dotenv_path=caminho_env)

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
    # 1. Primeiro mapeia os arquivos disponíveis no diretório
    arquivos = [f for f in os.listdir(DIRETORIO_TESTES) if f.endswith('.txt') or f.endswith('.json')]
    
    if not arquivos:
        registrar_log(f"[INFO] Nenhum arquivo para processar em '{DIRETORIO_TESTES}'.")
        return

    cursor = conn.cursor()
    total_inseridos = 0

    # 2. Inicia o loop sobre a lista correta
    for arquivo in arquivos:
        caminho_origem = os.path.join(DIRETORIO_TESTES, arquivo)
        caminho_destino = os.path.join(DIRETORIO_PROCESSADOS, arquivo)
        
        # Checagem para evitar duplicidade de carga
        cursor.execute("SELECT 1 FROM ConhecimentoHistorico WHERE nome_arquivo = %s LIMIT 1", (arquivo,))
        if cursor.fetchone():
            registrar_log(f"[PULADO] Arquivo '{arquivo}' já processado anteriormente.")
            shutil.move(caminho_origem, caminho_destino)
            continue

        registrar_log(f"Processando arquivo: {arquivo}.")
        try:
            chunks = []
            
            # 3. Todo o processamento agora ocorre dentro do escopo do arquivo atual
            if arquivo.endswith('.json'):
                with open(caminho_origem, 'r', encoding='utf-8') as f:
                    dados_json = json.load(f)
                    for item in dados_json:
                        # Se a flag existir e for explicitamente False, pula a inserção
                        if item.get("valido", True) == False:
                            continue
                            
                        chunk = f"CATEGORIA: {item.get('categoria', '')}\nPERGUNTA: {item.get('pergunta', '')}\nRESPOSTA: {item.get('resposta', '')}"
                        chunks.append(chunk)
            
            elif arquivo.endswith('.txt'):
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
                    cursor.execute(
                        "INSERT INTO ConhecimentoHistorico (nome_arquivo, conteudo_texto, embedding) VALUES (%s, %s, %s)",
                        (arquivo, chunk, vetor)
                    )
                    total_inseridos += 1
                else:
                    falha_no_embedding = True
                    break
            
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

def registrar_log(mensagem):
    diretorio = "memoria_teste_n_supervisionado"
    os.makedirs(diretorio, exist_ok=True)
    caminho_arquivo = os.path.join(diretorio, "log_fim_de_semana.txt")
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    with open(caminho_arquivo, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {mensagem}\n")
    print(mensagem)

def main():
    registrar_log("Iniciando rotina profissional de manutenção do Gandalf (Modo Lote/Batch).")
    
    conn = None
    try:
        conn = db_pool.getconn()
        pgvector.psycopg2.register_vector(conn)
        
        processardiretorio(conn)
        
        registrar_log("Processamento concluído com sucesso. Encerrando execução.")
    except Exception as e:
        registrar_log(f"[ERRO CRÍTICO NA EXECUÇÃO]: {e}")
    finally:
        if conn:
            db_pool.putconn(conn)

if __name__ == "__main__":
    main()