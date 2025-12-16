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
db_pass = 'abc321'        
db_host = 'localhost'     
db_port = '5433'    

ollama_chat_model = "deepseek-r1:14b" ##possivelmente mudar isso
ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{db_host}:11434" 
ollama_api_embed = f"{ollama_base_url}/api/embeddings"
ollama_api_chat = f"{ollama_base_url}/api/chat"

def limparrespostadeepseek(textobruto):
    """Remove o bloco de raciocínio <think>...</think> do DeepSeek."""
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
    print(f"[DEBUG] Vetorizando pergunta.") 
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
        "Nomenclatura de Objetos", "Boas Práticas", "Tipos de Dados", "Regras Gerais"
    ]
    prompt = f"""
    Analise a pergunta e responda APENAS com uma das categorias abaixo:
    - Os exemplos práticos que estão no arquivo Exemplo.py
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
    """Busca Regras Teóricas."""
    cursor = conn.cursor()
    print(f"[DEBUG SQL] Buscando regras. Categoria: '{nome_categoria}' | Foco: '{foco_usuario}'")

    sql_base = """
    SELECT r.descricao_regra, r.exemplo, r.padrao_sintaxe
    FROM regras_nomenclatura r
    JOIN categorias_regras c ON r.id_categoria = c.id_categoria
    """
    order_clause = """
    ORDER BY (CASE WHEN r.descricao_regra ILIKE %s THEN 0 ELSE 1 END) ASC, r.embedding <=> %s::vector LIMIT %s;
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

def buscarexemplos(conn, pergunta_vetor, foco_usuario, top_k=3):
    """Busca Exemplos homologados ou rejeitados na tabela nova."""
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT to_regclass('public.exemplos_praticos');")
        if not cursor.fetchone()[0]:
            print("[AVISO] Tabela 'exemplos_praticos' ainda não existe.")
            return []

        print(f"[DEBUG SQL] Buscando exemplos práticos similares...")
        sql = """
        SELECT is_bom_exemplo, exemplo_texto, explicacao
        FROM exemplos_praticos
        ORDER BY (CASE WHEN objeto_foco ILIKE %s THEN 0 ELSE 1 END) ASC, embedding <=> %s::vector LIMIT %s;
        """
        cursor.execute(sql, (f"%{foco_usuario}%", list(pergunta_vetor), top_k))
        return cursor.fetchall()
    except Exception as e:
        print(f"[ERRO SQL] Falha ao buscar exemplos: {e}")
        return []
    
def perguntaollama(pergunta, contexto_regras, exemplos_praticos):
    """
    Gera a resposta final com Streaming e mede performance.
    """
    contexto_str = "\n".join(
        f"- Regra: {regra} | Exemplo: {exemplo} | Padrão: {sintaxe}" 
        for regra, exemplo, sintaxe in contexto_regras
    )
    exemplos_str = ""
    if exemplos_praticos:
        exemplos_str = "\nExemplos de referência (Use como guia absoluto):\n"
        for is_bom, texto, explicacao in exemplos_praticos:
            tipo_txt = "BOM/APROVADO" if is_bom else "RUIM/PROIBIDO"
            exemplos_str += f"[{tipo_txt}]: {texto} ({explicacao})\n"

    print("\n" + "="*10)
    print(" RESPOSTA DO G.A.N.D.A.L.F:") 
    print("="*10)

    prompt_completo = f"""
    Você é um assistente especialista no manual do DETRAN-PE.
    Responda a pergunta baseando-se ESTRITAMENTE nas regras e exemplos abaixo.
    Se a regra proibir algo, diga claramente.
    
    Regras Oficiais:
    {contexto_str}
    
    {exemplos_str}

    Pergunta: {pergunta}
    Resposta:"""
    
    # --- CRONÔMETRO INICIAL ---
    inicio_real = datetime.now()

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

        dentro_think = False 
        metrics = {} # Armazena estatísticas do Ollama

        for line in resposta.iter_lines():
            if line:
                try:
                    json_data = json.loads(line.decode('utf-8'))
                    
                    # 1. Processa Texto
                    if 'message' in json_data:
                        content = json_data['message']['content']

                        if "<think>" in content: dentro_think = True
                        if "</think>" in content: dentro_think = False

                        # Só imprime no terminal se NÃO estiver pensando
                        if not dentro_think and "<think>" not in content and "</think>" not in content:
                            print(content, end='', flush=True) 
                        
                        resposta_completa += content
                    
                    # 2. Captura estatísticas finais (quando done: true)
                    if json_data.get('done') is True:
                        metrics = {
                            'total_duration': json_data.get('total_duration', 0),
                            'load_duration': json_data.get('load_duration', 0),
                            'eval_count': json_data.get('eval_count', 0),
                            'eval_duration': json_data.get('eval_duration', 0)
                        }

                except ValueError:
                    pass
        print("\n") 

        # --- RELATÓRIO DE PERFORMANCE ---
        fim_real = datetime.now()
        tempo_total_sec = (fim_real - inicio_real).total_seconds()
        
        # Conversão de nanosegundos para segundos
        ollama_eval  = metrics.get('eval_duration', 0) / 1e9
        tokens_gerados = metrics.get('eval_count', 0)
        tps = tokens_gerados / ollama_eval if ollama_eval > 0 else 0

        print("-" * 40)
        print(f"DIAGNÓSTICO DE VELOCIDADE:")
        print(f"Tempo Total (Relógio):   {tempo_total_sec:.2f}s")
        print(f"Tokens Gerados:          {tokens_gerados}")
        print(f"Velocidade de Escrita:   {tps:.2f} tokens/s")
        
        if tps < 5 and tps > 0:
            print("A geração está lenta (GPU sobrecarregada ou rodando na CPU).")
        print("-" * 10)

        return limparrespostadeepseek(resposta_completa)
        
    except Exception as e:
        return f"\n Erro técnico: {e}"
    

def salvarrespotas(pergunta, categoria, resposta, nome_arquivo="teste com scripts reais após ajustes no modelo de LLM e temperaturta-12-12-2025.txt"):
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

    print(f" Analisando a pergunta.")

    categoria = classificarpergunta(pergunta)
    foco = extrairfoco(pergunta) 
    vetor = embedtext(pergunta)
    
    if vetor:
        # Busca de REGRAS (Teoria)
        contexto_regras = encontrarregras(conn, vetor, categoria, foco)
        
        if not contexto_regras:
            print(" [i] Tentando busca global nas regras...")
            contexto_regras = encontrarregras(conn, vetor, "GERAL", foco)

        # Busca de EXEMPLOS (Prática)
        exemplos_praticos = buscarexemplos(conn, vetor, foco)

        # Geração
        resposta_final = perguntaollama(pergunta, contexto_regras, exemplos_praticos)
        
        salvarrespotas(pergunta, categoria, resposta_final)
    
    conn.close()

if __name__ == "__main__":
    main()
