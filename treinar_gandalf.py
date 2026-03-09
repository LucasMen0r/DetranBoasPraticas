import pgvector
import psycopg2
from datetime import datetime
import os
import requests
from dotenv import load_dotenv
import pgvector.psycopg2

# Configurações com fallback para variáveis de ambiente (Segurança)
load_dotenv()
db_name = os.getenv('DB_NAME', 'DetranNorma')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASS', 'abc321')        
db_host = os.getenv('DB_HOST', 'localhost')     
db_port = os.getenv('DB_PORT', '5435')          

ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{db_host}:11436" 
ollama_api_embed = f"{ollama_base_url}/api/embeddings"

DIRETORIO_TESTES = "arquivos_teste"

def conectadb():
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port
        )
        pgvector.psycopg2.register_vector(conn)
        return conn
    except psycopg2.Error as e:
        print(f"[ERRO] Falha de Conexão com o Banco: {e}")
        return None

def embedtext(text): 
    try: 
        resposta = requests.post( 
            ollama_api_embed, 
            json={"model": ollama_embed_model, "prompt": text} 
        ) 
        resposta.raise_for_status() 
        return resposta.json()['embedding'] 
    except requests.RequestException as e: 
        print(f"[ERRO OLLAMA] Falha ao vetorizar: {e}") 
        return None

def criar_chunks(texto, tamanho_maximo=1000, sobreposicao=100):
    if sobreposicao >= tamanho_maximo:
        raise ValueError("A sobreposicao deve ser estritamente menor que o tamanho maximo do chunk.")
    palavras = texto.split()
    chunks = []
    i = 0
    while i < len(palavras):
        chunk = " ".join(palavras[i:i + tamanho_maximo])
        chunks.append(chunk)
        i += tamanho_maximo - sobreposicao
    return chunks

def sanitizartexto(texto_bruto):
    """Limpeza basica para evitar ruidos de formatacao nos arquivos txt."""
    if not texto_bruto:
        return ""
    linhas = texto_bruto.split('\n')
    linhas_limpas = [linha.strip() for linha in linhas if linha.strip()]
    return " ".join(linhas_limpas)

def processar_diretorio(conn):
    """Lê, limpa, vetoriza e salva todos os arquivos .txt do diretorio."""
    os.makedirs(DIRETORIO_TESTES, exist_ok=True)
    
    arquivos = [f for f in os.listdir(DIRETORIO_TESTES) if f.endswith('.txt')]
    if not arquivos:
        print(f"[INFO] Nenhum arquivo .txt encontrado em '{DIRETORIO_TESTES}'.")
        return

    cursor = conn.cursor()
    total_inseridos = 0

    for arquivo in arquivos:
        caminho_completo = os.path.join(DIRETORIO_TESTES, arquivo)
        print(f"Processando arquivo: {arquivo}...")
        
        try:
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                conteudo_bruto = f.read()
                
            texto_limpo = sanitizartexto(conteudo_bruto)
            if not texto_limpo:
                continue

            chunks = criar_chunks(texto_limpo, tamanho_maximo=400, sobreposicao=50)
            
            for chunk in chunks:
                vetor = embedtext(chunk)
                if vetor:
                    query = """
                    INSERT INTO ConhecimentoHistorico (nome_arquivo, conteudo_texto, embedding)
                    VALUES (%s, %s, %s)
                    """
                    cursor.execute(query, (arquivo, chunk, vetor))
                    total_inseridos += 1
                    
            conn.commit()
            print(f"  -> Sucesso. Chunks inseridos: {len(chunks)}")
            
        except Exception as e:
            conn.rollback()
            print(f"  -> [ERRO] Falha ao processar o arquivo {arquivo}: {e}")

    cursor.close()
    print(f"Processamento concluido. Total inserido: {total_inseridos}")

def autotreinar(conn):
    """Verifica dados sem memoria e corrige automaticamente."""
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT pkRegraNomenclatura, DescricaoRegra FROM RegraNomenclatura WHERE embedding IS NULL")
        regras_pendentes = cursor.fetchall()
        
        if regras_pendentes:
            print(f"\n[AUTO-TREINO] Processando {len(regras_pendentes)} regras pendentes...")
            for pk, texto in regras_pendentes:
                vetor = embedtext(texto)
                if vetor:
                    cursor.execute("UPDATE RegraNomenclatura SET embedding = %s WHERE pkRegraNomenclatura = %s", (vetor, pk))
            conn.commit()
            print("[AUTO-TREINO] Regras atualizadas.")

        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if cursor.fetchone()[0]:
            cursor.execute("SELECT pkExemploPratico, ExemploTexto, Explicacao FROM ExemploPratico WHERE embedding IS NULL")
            exemplos_pendentes = cursor.fetchall()
            
            if exemplos_pendentes:
                print(f"[AUTO-TREINO] Processando {len(exemplos_pendentes)} exemplos pendentes...")
                for pk, texto, explicacao in exemplos_pendentes:
                    texto_completo = f"Exemplo: {texto}. Explicacao: {explicacao}"
                    vetor = embedtext(texto_completo)
                    if vetor:
                        cursor.execute("UPDATE ExemploPratico SET embedding = %s WHERE pkExemploPratico = %s", (vetor, pk))
                conn.commit()
                print("[AUTO-TREINO] Exemplos atualizados.")
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Falha no auto-treino: {e}")
    finally:
        cursor.close()

def salvarrespostas(pergunta, categoria, resposta):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_arquivo = datetime.now().strftime("%d-%m-%Y")
    nome_arquivo = f"log_gandalf_{data_arquivo}.txt"
    
    # Define o diretório alvo
    diretorio_destino = "memoria_gandalf"
    
    # Prática de segurança: cria o diretório automaticamente caso ele não exista.
    os.makedirs(diretorio_destino, exist_ok=True)
    
    # Constrói o caminho completo de forma segura para qualquer sistema operacional.
    caminho_completo = os.path.join(diretorio_destino, nome_arquivo)
    
    conteudo = (
        f"========================================\n"
        f"DATA: {timestamp}\n"
        f"========================================\n"
        f"CATEGORIA: {categoria}\n"
        f"========================================\n"
        f"PERGUNTA: {pergunta}\n"
        f"========================================\n"
        f"RESPOSTA:\n{resposta}\n"
        f"========================================\n\n"
    )
    try:
        with open(caminho_completo, "a", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"\n[INFO] Resposta salva no log diário em: '{caminho_completo}'")
    except Exception as e:
        print(f"\n[ERRO] Não foi possível salvar o arquivo de log no caminho principal: {e}")
        
        # Fallback corrigido: cria o diretório e efetivamente grava o arquivo
        diretorio_fallback = os.path.join(os.getcwd(), "memoria_teste_n_supervisionado")
        os.makedirs(diretorio_fallback, exist_ok=True)
        caminho_fallback = os.path.join(diretorio_fallback, nome_arquivo)
        
        try:
            with open(caminho_fallback, "a", encoding="utf-8") as f:
                f.write(conteudo)
            print(f"[INFO] Resposta salva com sucesso no diretório de fallback: '{caminho_fallback}'")
        except Exception as ex:
            print(f"[ERRO CRITICO] Falha total ao tentar salvar log no fallback: {ex}")
def main():
    print("Iniciando rotina de manutencao da base de conhecimento do Gandalf.")
    conn = conectadb()
    if not conn: return
    
    autotreinar(conn)
    processar_diretorio(conn)
    
    conn.close()
    print("Rotina finalizada.")

if __name__ == "__main__":
    main()