import pgvector
import psycopg2
import requests
import sys
import json
import pgvector.psycopg2
from datetime import datetime

db_name = 'DetranNorma'
db_user = 'postgres'
db_pass = 'abc321'
db_host = '172.30.151.166'
db_port = '5432'

ollama_chat_model = "qwen2.5:1.5b"
ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{db_host}:11435"
ollama_api_embed = f"{ollama_base_url}/api/embeddings"
ollama_api_chat = f"{ollama_base_url}/api/chat"

def conectadb():
    """conexão com o Postgre SQL"""
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
        )
        pgvector.psycopg2.register_vector(conn)

        print(conn)
        return conn
    except psycopg2.Error as e:
        print(f"Erro de Conexão com o Banco: {e}")
        return None
    
def embedtext(text): 
    print(f"[DEBUG] Tentando vetorizar com Ollama em: {ollama_api_embed}") 
    try: 
        resposta = requests.post( 
            ollama_api_embed, 
            json={"model": ollama_embed_model, "prompt": text} 
        ) 
        resposta.raise_for_status() 
        print("[DEBUG] Vetorização bem-sucedida.") 
        return resposta.json()['embedding'] 
    except requests.RequestException as e: 
        print(f"[ERRO DE REDE/OLLAMA] Falha ao vetorizar: {e}") 
        return None
    
def encontrarregras(conn, pergunta_vetor, top_k = 10):
    cursor = conn.cursor()
    """Busca as regras mais similares no banco. top_k=10 aumenta a precisão."""
    query = """
    SELECT descricao_regra, exemplo, padrao_sintaxe 
    FROM regras_nomenclatura
    ORDER BY embedding <=> %s::vector
    LIMIT %s;
    """
    cursor.execute(query, (list(pergunta_vetor), top_k))
    return cursor.fetchall()

def perguntaollama(pergunta, contexto):
    """Envia o contexto e a pergunta com resposta em TEMPO REAL (Streaming)."""
    contexto_str = "\n".join(

        f"- Regra: {regra} | Exemplo: {exemplo} | Padrão: {sintaxe}" 
        for regra, exemplo, sintaxe in contexto
    )
    print(f"\n[DEBUG - O QUE O BANCO ENCONTROU]:\n{contexto_str}\n")
    print("#"*10)

    print(" Resposta da ia:")
    print("#"*10)

    prompt_completo = f"""Você é um assistente especialista no manual do DETRAN-PE.
Use o contexto abaixo para responder a pergunta de forma direta e técnica.
Contexto:
{contexto_str}

Pergunta: {pergunta}
Resposta:"""
    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
                "model": ollama_chat_model,
                "messages": [
                    {"role": "system", "content": "Você é um assistente útil e técnico."},
                    {"role": "user", "content": prompt_completo}
                ],
                "stream": True
            },
            stream=True
        )
        resposta.raise_for_status()
        resposta_completa = ""

        for line in resposta.iter_lines():
            if line:
                try:
                    json_data = json.loads(line.decode('utf-8'))
                    if 'message' in json_data:
                        content = json_data['message']['content']

                        print(content, end='', flush=True) 
                        resposta_completa += content

                except ValueError:
                    pass
        print("\n") 
        return resposta_completa
    except Exception as e:
        return f"\n Erro técnico: {e}"

def classificarpergunta(pergunta):
    """
    Agente Vertical: Classifica a intenção técnica do desenvolvedor.
    """
    # Mapeamento exato das categorias do seu INSERT INTO categorias_regras
    prompt_classificador = f"""
    Você é um Tech Lead sênior do Detran.
    Classifique a pergunta técnica do desenvolvedor em uma das categorias abaixo.
    
    CATEGORIAS DISPONÍVEIS:
    - 'Nomenclatura de Objetos': Dúvidas sobre nomes de tabelas, colunas, prefixos (tb, vw, pk), sufixos.
    - 'Boas Práticas': Dúvidas sobre performance, uso de JOINs, cursores, procedures, integridade.
    - 'Tipos de Dados': Dúvidas sobre int, varchar, numeric, tamanhos de colunas.
    - 'Regras Gerais': Formatação, uso de acentos, caracteres especiais, maiúsculas/minúsculas.
    
    Pergunta: "{pergunta}"
    
    Responda APENAS com o nome exato da categoria (ex: Nomenclatura de Objetos).
    Caso não se encaixe, responda: GERAL
    """
    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
        "model": ollama_chat_model, 
        "messages": [
        {"role": "user", "content": prompt_classificador} 
    ],
    "stream": False,
    "options": {"temperature": 0}
}
        )
        resposta.raise_for_status() 
        categoria = resposta.json()['mensagem']['conteudo'].strip()
        return categoria.replace (" ' ", ""),('"', '')
    except Exception:
        return "Geral."

def encontrarregras(conn, pergunta_vetor, nome_categoria, top_k=10):
    cursor = conn.cursor()
    sql_base = """
    SELECT 
    r.descricao_regra, 
    r.exemplo, 
    r.padrao_sintaxe
    FROM regras_nomenclatura r
    JOIN categorias_regras c ON r.id_categoria = c.id_categoria
    """
    if nome_categoria == "GERAL":
        sql = sql_base + "order by r.embedding <=> %s::vector limit %s;"
        parametros = (list(pergunta_vetor), top_k)
    else:
        sql = sql_base + """
        where c.nome_categoria ilike %s 
        order by r.embedding <=> %s::vector 
        limit %s;
        """
        parametros = (f"%{nome_categoria}", list(pergunta_vetor), top_k)
    cursor.execute(sql, parametros)
    return cursor.fetchall()

def salvarrespotas(pergunta, categoria, resposta, nome_arquivo="historico_detran.txt"):
    """
    Salva a interação em um arquivo de texto (append mode).
    Cria o arquivo se não existir.
    """
    timestamp  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

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
        with open(nome_arquivo, "a", encoding= "utf-8") as f:
            f.write(conteudo)
        print(f"\n[INFO] Resposta salva em '{nome_arquivo}'")
    except Exception as e:
        print(f"\n[ERRO] Não foi possível salvar o arquivo: {e}")

def main():
    if len(sys.argv) < 2:
        print('Uso: python perguntar.py "Sua pergunta entre aspas"')
        return
    pergunta = sys.argv[1]

    conn = conectadb()
    if not conn: return

    print(f" Analisando a pergunta.")
    categoria = classificarpergunta(pergunta)
    print(f" Agente Especialista Acionado: [{categoria}]")

    vetor = embedtext(pergunta)
    
    contexto = encontrarregras(conn, vetor, categoria)
    
    if not contexto:
        
        print(" Nada encontrado na vertical. Tentando busca global...")
        contexto = encontrarregras(conn, vetor, "GERAL")

    perguntaollama(pergunta, contexto)
    conn.close()

if __name__ == "__main__":
    main()