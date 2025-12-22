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
db_port = '5432'          

ollama_chat_model = "deepseek-r1:8b" ##o modelo anterior, o 14b, foi removido por ser muito pesado; o 8b pode fazer as suas funções sem muitos problemas.
ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{db_host}:11436" 
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
                "options": {"temperature": 0.15}
            }
        )
        resposta.raise_for_status() 

        conteudo = limparrespostadeepseek(resposta.json()['message']['content'])
        
        for cat in categorias_validas:
            if cat.lower() in conteudo.lower():
                return cat
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
    print(f"Buscando regras. Categoria: '{nomecategoria}' | Foco: '{foco_usuario}'")

    sql_base = """
    SELECT r.DescricaoRegra, r.ContextoAdicional, r.PadraoSintaxe 
    FROM RegraNomenclatura r
    JOIN CategoriaRegra c ON r.pkCategoriaRegra = c.pkCategoriaRegra
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

def buscarexemplos(conn, pergunta_vetor, foco_usuario, top_k=4):
    """Busca Exemplos homologados ou rejeitados na tabela nova."""
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if not cursor.fetchone()[0]:
            print("[AVISO] Tabela 'ExemploPratico' ainda não existe.")
            return []

        print(f"Buscando exemplos práticos similares.")
        sql = """
    SELECT is_BomExemplo, ExemploTexto, Explicacao
    FROM ExemploPratico
    ORDER BY (CASE WHEN ObjetoFoco ILIKE %s THEN 0 ELSE 1 END) ASC, embedding <=> %s::vector LIMIT %s;
    """
        cursor.execute(sql, (f"%{foco_usuario}%", list(pergunta_vetor), top_k))
        return cursor.fetchall()
    except Exception as e:
        print(f"[ERRO SQL] Falha ao buscar exemplos: {e}")
        return []
    
def perguntaollama(pergunta, contexto_regras, ExemploPratico):
    """
    Gera a resposta final com Streaming, usando Regras + Exemplos Práticos.
    Versão aprimorada com Debug de Contexto e Prompt de Auditoria.
    """
    # --- 1. DEBUG VISUAL (Para você ver o que o Gandalf está "lendo") ---
    print("\n" + "="*10)
    print(f"[DEBUG] Regras recuperadas do Banco: {len(contexto_regras)}")
    
    if not contexto_regras:
        print("[ALERTA] O Retrieval retornou lista vazia! O contexto será nulo.")
    else:
        # Mostra uma prévia das primeiras 3 regras para conferência
        for i, (regra, ctx, sintaxe) in enumerate(contexto_regras[:3]):
            regra_curta = (regra[:60] + '..') if regra else "N/A"
            print(f"   {i+1}. {regra_curta}")
    print("="*10 + "\n")
    # Montagem do Contexto de Regras (Tratando None como string vazia)
    contexto_str = ""
    if contexto_regras:
        contexto_str = "\n".join(
            f"- Regra: {str(regra or '')} | Detalhes: {str(ctx or '')} | Sintaxe Obrigatória: {str(sintaxe or '')}" 
            for regra, ctx, sintaxe in contexto_regras
        )
    
    # Montagem do Contexto de Exemplos
    exemplos_str = ""
    if ExemploPratico:
        exemplos_str = "\n[[ EXEMPLOS DE REFERÊNCIA (USE COMO GABARITO) ]]\n"
        for is_bom, texto, explicacao in ExemploPratico:
            tipo_txt = "APROVADO (Seguir este modelo)" if is_bom else "REPROVADO (Evitar este modelo)"
            exemplos_str += f"[{tipo_txt}]: {texto} -> Motivo: {explicacao}\n"

    print(" RESPOSTA DO G.A.N.D.A.L.F:") 
    print("#"*15)

    # --- 2. PROMPT DE AUDITORIA (Engenharia de Prompt Refinada) ---
    prompt_sistema = """
    Você é o G.A.N.D.A.L.F (Gerenciador de Análise de Normas do Detran).
    Sua função é atuar como um AUDITOR RÍGIDO.
    
    INSTRUÇÃO MESTRA:
    Você deve responder baseando-se EXCLUSIVAMENTE nos trechos de regras e exemplos fornecidos abaixo.
    Considere que o contexto fornecido contém TODA a verdade necessária.
    NÃO assuma que faltam informações. Trabalhe com o que tem.
    NÃO recomende consultar manuais externos.
    """

    prompt_usuario = f"""
    [[ REGRAS VIGENTES RECUPERADAS ]]
    {contexto_str if contexto_str.strip() else "NENHUMA REGRA ESPECÍFICA FOI ENCONTRADA NO BANCO DE DADOS PARA ESTE TERMO."}
    
    {exemplos_str}

    [[ SOLICITAÇÃO DO DESENVOLVEDOR ]]
    {pergunta}
    
    Se houver regras acima, valide a solicitação contra elas.
    Se NÃO houver regras acima, responda apenas: "Não localizei regras específicas no meu banco de conhecimento para validar este objeto."
    """
    
    # --- CRONÔMETRO INICIAL ---
    inicio_real = datetime.now()

    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
                "model": ollama_chat_model,
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario}
                ],
                "stream": True,
                "options": {
                    "temperature": 0.2, # Baixa temperatura para ser mais fiel aos dados
                    "num_ctx": 4096     # Garante janela de contexto suficiente
                }
            },
            stream=True
        )
        resposta.raise_for_status()
        resposta_completa = ""

        dentro_think = False 
        metrics = {} 

        for line in resposta.iter_lines():
            if line:
                try:
                    json_data = json.loads(line.decode('utf-8'))
                    
                    if 'message' in json_data:
                        content = json_data['message']['content']

                        # Lógica para ocultar o <think> do DeepSeek R1 no terminal
                        if "<think>" in content: dentro_think = True
                        
                        if not dentro_think and "<think>" not in content and "</think>" not in content:
                            print(content, end='', flush=True) 
                        
                        if "</think>" in content: dentro_think = False
                        
                        resposta_completa += content
                    
                    if json_data.get('done') is True:
                        metrics = {
                            'total_duration': json_data.get('total_duration', 0),
                            'eval_count': json_data.get('eval_count', 0),
                            'eval_duration': json_data.get('eval_duration', 0)
                        }

                except ValueError:
                    pass
        print("\n") 

        # --- RELATÓRIO DE PERFORMANCE ---
        fim_real = datetime.now()
        tempo_total_sec = (fim_real - inicio_real).total_seconds()
        
        ollama_eval  = metrics.get('eval_duration', 0) / 1e9
        tokens_gerados = metrics.get('eval_count', 0)
        tps = tokens_gerados / ollama_eval if ollama_eval > 0 else 0

        print("-" * 40)
        print(f"DIAGNÓSTICO DE VELOCIDADE:")
        print(f"Tempo Total (Relógio):   {tempo_total_sec:.2f}s")
        print(f"Tokens Gerados:          {tokens_gerados}")
        print(f"Velocidade de Escrita:   {tps:.2f} tokens/s")
        print("-" * 10)

        return limparrespostadeepseek(resposta_completa)
        
    except Exception as e:
        print(f"\n[ERRO NA GERAÇÃO]: {e}")
        return f"Erro técnico ao consultar LLM: {e}"

def salvarrespotas(pergunta, categoria, resposta, nome_arquivo="continuação dos testes e inserção de mais exemplos reais-19-12-2025.txt"):
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
        # Busca de REGRAS (Teoria)
        contexto_regras = encontrarregras(conn, vetor, categoria, foco)
        
        if not contexto_regras:
            contexto_regras = encontrarregras(conn, vetor, "GERAL", foco)

        # Busca de EXEMPLOS (Prática)
        ExemploPratico = buscarexemplos(conn, vetor, foco)

        # Geração
        resposta_final = perguntaollama(pergunta, contexto_regras, ExemploPratico)
        
        salvarrespotas(pergunta, categoria, resposta_final)
    
    conn.close()

if __name__ == "__main__":
    main()
