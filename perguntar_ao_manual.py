import pgvector
import psycopg2
import requests
import sys
import json
import pgvector.psycopg2
from datetime import datetime
import re

db_name = 'DetranNorma'
db_user = 'postgres'
db_pass = '654321'
db_host = 'localhost'     
db_port = '5432'          

ollama_chat_model = "deepseek-r1:8b"
ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{db_host}:11434" 
ollama_api_embed = f"{ollama_base_url}/api/embeddings"
ollama_api_chat = f"{ollama_base_url}/api/chat"

def limparrespostadeepseek(textobruto):
    """
    Remove o bloco de raciocínio <think>...</think> do DeepSeek
    para retornar apenas a resposta final limpa.
    """
    if not textobruto:
        return " " 
    texto_limpo = re.sub(r'<think>.*?</think>', '', textobruto, flags=re.DOTALL)
    return texto_limpo.strip()

def conectadb():
    """Conexão com o Postgre SQL"""
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
        )
        pgvector.psycopg2.register_vector(conn)
        return conn
    except psycopg2.Error as e:
        print(f"Erro de Conexão com o Banco: {e}")
        return None
    
def embedtext(text): 
    print(f"[DEBUG] Vetorizando pergunta...") 
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

def classificarpergunta(pergunta):
    """Agente Vertical: Classifica a intenção com validação rígida."""
    categorias_validas = [
        "Nomenclatura de Objetos", 
        "Boas Práticas", 
        "Tipos de Dados", 
        "Regras Gerais"
    ]
    
    prompt = f"""
    Analise a pergunta e responda APENAS com uma das categorias abaixo:
    - Nomenclatura de Objetos
    - Boas Práticas
    - Tipos de Dados
    - Regras Gerais
    
    Pergunta: "{pergunta}"
    Resposta (apenas o nome):
    """
    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
                "model": ollama_chat_model, 
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0}
            }
        )
        resposta.raise_for_status() 
        conteudo = limparrespostadeepseek(resposta.json()['message']['content'])
        
        for cat in categorias_validas:
            if cat.lower() in conteudo.lower():
                return cat
        
        print(f"[AVISO] Categoria '{conteudo}' inválida. Usando GERAL.")
        return "GERAL"

    except Exception:
        return "GERAL"

def extrairfoco(pergunta):
    """Extrai o objeto técnico principal (Procedure, Tabela, View, etc)."""
    prompt = f"""
    Extraia APENAS o substantivo técnico principal da pergunta.
    Ex: "Validar procedure X" -> Procedure
    Ex: "Tabela temporária" -> Tabela
    
    Pergunta: "{pergunta}"
    Resposta (uma palavra):
    """
    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
                "model": ollama_chat_model, 
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0}
            }
        )
        resposta.raise_for_status() 
        texto_limpo = limparrespostadeepseek(resposta.json()['message']['content'])
        foco = texto_limpo.strip().split()[0]

        return foco.replace(".", "").replace('"', "").replace("'", "")
    except:
        return ""

def encontrarregras(conn, pergunta_vetor, nome_categoria, foco_usuario, top_k=5):
    """Busca Híbrida: Vetor + Boost por Palavra-Chave"""
    cursor = conn.cursor()
    print(f"[DEBUG SQL] Categoria: '{nome_categoria}' | Foco: '{foco_usuario}'")

    sql_base = """
    SELECT r.descricao_regra, r.exemplo, r.padrao_sintaxe
    FROM regras_nomenclatura r
    JOIN categorias_regras c ON r.id_categoria = c.id_categoria
    """
    
    order_clause = """
    ORDER BY 
        (CASE WHEN r.descricao_regra ILIKE %s THEN 0 ELSE 1 END) ASC, 
        r.embedding <=> %s::vector 
    LIMIT %s;
    """
    
    term_boost = f"%{foco_usuario}%"

    if "GERAL" in nome_categoria.upper():
        sql = sql_base + order_clause
        parametros = (term_boost, list(pergunta_vetor), top_k)
    else:
        sql = sql_base + f" WHERE c.nome_categoria ILIKE %s " + order_clause
        parametros = (f"%{nome_categoria}%", term_boost, list(pergunta_vetor), top_k)
        
    cursor.execute(sql, parametros)
    return cursor.fetchall()

def perguntaollama(pergunta, contexto):
    """Gera a resposta final com Streaming."""
    contexto_str = "\n".join(
        f"- Regra: {regra} | Exemplo: {exemplo} | Padrão: {sintaxe}" 
        for regra, exemplo, sintaxe in contexto
    )
    
    print("\n" + "="*10)
    print(" RESPOSTA DO G.A.N.D.A.L.F:")  #Gerador Automatizado de Normas Do Detran-PE por LLM para Fiscalização de boas práticas [G.A.N.D.A.L.F]
    print("="*10)

    prompt_completo = f"""
    Você é um assistente especialista no manual do DETRAN-PE.
    Responda a pergunta baseando-se ESTRITAMENTE nas regras abaixo.
    Se a regra proibir algo, diga claramente.
    
    Regras Oficiais:
    {contexto_str}

    Pergunta: {pergunta}
    Resposta:"""
    
    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
                "model": ollama_chat_model,
                "messages": [
                    {"role": "system", "content": "Seja técnico, direto e cite as regras."},
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
        return limparrespostadeepseek(resposta_completa)
    except Exception as e:
        return f"\n Erro técnico: {e}"

def salvarrespotas(pergunta, categoria, resposta, nome_arquivo="historico_detran-1-12-2025.txt"):
    """Salva a interação em um arquivo de texto."""
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
        print('Uso: python3 perguntar_ao_manual.py "Sua pergunta entre aspas"')
        return 

    pergunta = sys.argv[1]

    conn = conectadb()
    if not conn: return

    categoria = classificarpergunta(pergunta)
    foco = extrairfoco(pergunta)
    vetor = embedtext(pergunta)
    
    if vetor:
        contexto = encontrarregras(conn, vetor, categoria, foco)
        
        if not contexto:
            print(" [i] Tentando busca global.")
            contexto = encontrarregras(conn, vetor, "GERAL", foco)

        resposta_final = perguntaollama(pergunta, contexto)
        salvarrespotas(pergunta, categoria, resposta_final)
    
    conn.close()

if __name__ == "__main__":
    main()
