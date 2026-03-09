import pgvector
import psycopg2
import os
import requests
import sys
import json
import pgvector.psycopg2
from datetime import datetime
import re

# Configurações com fallback para variáveis de ambiente (Segurança)
db_name = os.getenv('DB_NAME', 'DetranNorma')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASS', 'abc321')        
db_host = os.getenv('DB_HOST', 'localhost')     
db_port = os.getenv('DB_PORT', '5435')    
DIRETORIO_TESTES = "arquivos_teste" 

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

def buscar_historico(conn, pergunta_vetor, top_k=3):
    """Busca no histórico de testes e aprendizados (Memória)."""
    try:
        cursor = conn.cursor()
        
        # Verifica se a tabela existe para evitar erros
        cursor.execute("SELECT to_regclass('public.ConhecimentoHistorico');")
        if not cursor.fetchone()[0]:
            return []

        print(f"Buscando na memória de testes do Gandalf.")
        
        # Busca os chunks mais parecidos com a pergunta atual
        sql = """
        SELECT nome_arquivo, conteudo_texto
        FROM ConhecimentoHistorico
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        cursor.execute(sql, (list(pergunta_vetor), top_k))
        return cursor.fetchall()
        
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao buscar histórico: {e}")
        return []
    finally:
        cursor.close()

def criar_chunks(texto, tamanho_maximo=1000, sobreposicao=100):
    """
    Divide o texto em blocos menores (chunks) para não estourar o limite de tokens do modelo de embedding.
    Usa sobreposicao (overlap) para não perder o contexto entre os cortes.
    """
    palavras = texto.split()
    chunks = []
    i = 0
    while i < len(palavras):
        chunk = " ".join(palavras[i:i + tamanho_maximo])
        chunks.append(chunk)
        i += tamanho_maximo - sobreposicao
    return chunks

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
    - Regras especiais
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
        return "GERAL"

    except Exception:
        return "GERAL"

def extrairfoco(pergunta):
    """Extrai o objeto técnico e PADRONIZA para o vocabulário do banco (Português)."""
    prompt = f"""
    Aja como um classificador de banco de dados.
    Sua tarefa: Identificar o objeto principal da pergunta e converter para o termo padrão do Detran.
    
    TABELA DE CONVERSÃO (Use isto como guia):
    - "table", "tabelas", "entidade" -> Tabela
    - "column", "field", "atributo", "campo" -> Coluna
    - "proc", "procedure", "stored procedure" -> Procedure
    - "view", "visao" -> View comum
    - "index", "indice" -> Índice
    - "fk", "foreign key", "chave estrangeira" -> fk (Foreign Key)
    - "pk", "primary key", "chave primaria" -> pk (Primary Key)
    
    Se não for nenhum desses, retorne apenas o substantivo principal em português.
    
    Pergunta: "{pergunta}"
    Resposta (apenas uma palavra/termo):
    """
    try:
        resposta = requests.post(
            ollama_api_chat,
            json={
                "model": ollama_chat_model, 
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0} # Temperatura 0 para ser robótico e preciso
            }
        )
        resposta.raise_for_status() 
        texto_limpo = limparrespostadeepseek(resposta.json()['message']['content'])
        # Remove pontuações extras que o LLM possa colocar
        foco = texto_limpo.strip().split('\n')[0].replace(".", "").replace('"', "").replace("'", "")
        return foco
    except:
        return ""
    
def encontrarregras(conn, pergunta_vetor, Nomecategoria, foco_usuario, top_k=5):
    cursor = conn.cursor()
    print(f"Buscando regras. Categoria: '{Nomecategoria}' | Foco: '{foco_usuario}'")
    try:
        # Adicionado o LEFT JOIN com a tabela ObjetoDb para filtrar pelo objeto real
        sql_base = """
        SELECT r.DescricaoRegra
        FROM RegraNomenclatura r
        JOIN CategoriaRegra c ON r.pkCategoriaRegra = c.pkCategoriaRegra
        LEFT JOIN ObjetoDb o ON r.pkObjetoDb = o.pkObjetoDb
        """
        # A prioridade agora é dada pela correspondência com o NomeObjeto, não com o texto da regra
        order_clause = """
        ORDER BY (CASE WHEN o.NomeObjeto ILIKE %s THEN 0 ELSE 1 END) ASC, r.embedding <=> %s::vector LIMIT %s;
        """
        term_boost = f"%{foco_usuario}%"

        if "GERAL" in Nomecategoria.upper():
            sql = sql_base + order_clause
            parametros = (term_boost, list(pergunta_vetor), top_k)
        else:
            sql = sql_base + " WHERE c.NomeCategoria ILIKE %s " + order_clause
            parametros = (f"%{Nomecategoria}%", term_boost, list(pergunta_vetor), top_k)
            
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao encontrar regras: {e}")
        return []
    finally:
        cursor.close()

def buscarexemplos(conn, pergunta_vetor, foco_usuario, top_k=4):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if not cursor.fetchone()[0]:
            return []

        print(f"Buscando exemplos praticos similares.")
        sql = """
        SELECT is_BomExemplo, ExemploTexto, Explicacao
        FROM ExemploPratico
        ORDER BY (CASE WHEN ObjetoFoco ILIKE %s THEN 0 ELSE 1 END) ASC, embedding <=> %s::vector LIMIT %s;
        """
        cursor.execute(sql, (f"%{foco_usuario}%", list(pergunta_vetor), top_k))
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao buscar exemplos: {e}")
        return []
    finally:
        cursor.close()

def processar_diretorio(conn, sanitizar_texto, gerar_embedding):
    """Lê, limpa, vetoriza e salva todos os arquivos .txt do diretório."""
    
    os.makedirs(DIRETORIO_TESTES, exist_ok=True) #cria o diretório automaticamente caso ele não exista, para evitar erros de caminho
    
    if not os.path.exists(DIRETORIO_TESTES):
        print(f"[ERRO] O diretório '{DIRETORIO_TESTES}' não foi encontrado.")
        return

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
                
            texto_limpo = sanitizar_texto(conteudo_bruto)
            
            if not texto_limpo:
                print(f"  -> Arquivo vazio ou continha apenas ruído. Ignorado.")
                continue

            chunks = criar_chunks(texto_limpo, tamanho_maximo=400, sobreposicao=50)
            
            for chunk in chunks:
                vetor = gerar_embedding(chunk)
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
    print("-" * 40)
    print(f"Processamento concluído. Total de registros inseridos no banco: {total_inseridos}")

def perguntaollama(pergunta, contexto_regras, ExemploPratico, historico_testes):
    """
    Gera a resposta final com Streaming, usando Regras + Exemplos Práticos.
    Versão ajustada para estrutura enxuta do banco (apenas Regra, sem contexto/sintaxe na tupla).
    """
    # --- 1. DEBUG VISUAL (Para você ver o que o Gandalf está "lendo") ---
    print("\n" + "="*10)
    print(f"[DEBUG] Regras recuperadas do Banco: {len(contexto_regras)}")
    
    if not contexto_regras:
        print("[ALERTA] O Retrieval retornou lista vazia! O contexto será nulo.")
    else:
        # Mostra uma prévia das primeiras 3 regras para conferência
        # ALTERAÇÃO: Lemos a tupla como um item só e pegamos o índice [0]
        for i, dados_regra in enumerate(contexto_regras[:3]):
            regra = dados_regra[0]
            regra_curta = (regra[:60] + '..') if regra else "N/A"
            print(f"   {i+1}. {regra_curta}")
    print("="*10 + "\n")

    # Montagem do Contexto de Regras (Tratando None como string vazia)

# 1. Montagem do Contexto de Regras
    contexto_str = ""
    if contexto_regras:
        contexto_str = "\n".join(
            f"- Regra: {str(dados_regra[0] or '')}" 
            for dados_regra in contexto_regras
        )
    
    # 2. Montagem do Contexto de Exemplos
    exemplos_str = ""
    if ExemploPratico:
        exemplos_str = "\n[[ EXEMPLOS DE REFERÊNCIA (USE COMO GABARITO) ]]\n"
        for is_bom, texto, explicacao in ExemploPratico:
            tipo_txt = "APROVADO (Seguir este modelo)" if is_bom else "REPROVADO (Evitar este modelo)"
            exemplos_str += f"[{tipo_txt}]: {texto} -> Motivo: {explicacao}\n"

    # 3. Montagem do Contexto Histórico
    historico_str = ""
    if historico_testes:
        historico_str = "\n[[ CONHECIMENTO ADQUIRIDO EM TESTES ANTERIORES ]]\n"
        for nome_arquivo, texto in historico_testes:
            historico_str += f"- (Referência: {nome_arquivo}): {texto}\n"

    print(" RESPOSTA DO G.A.N.D.A.L.F:") 
    print("#"*15)

    # 4. Prompts do LLM
    prompt_sistema = """
    Você é o G.A.N.D.A.L.F (Gerenciador de Análise de Normas do Detran).
    Sua função é atuar como um AUDITOR RÍGIDO.
    
    INSTRUÇÃO MESTRA:
    Você deve responder baseando-se EXCLUSIVAMENTE nos trechos de regras e exemplos fornecidos abaixo.
    Considere que o contexto fornecido contém TODA a verdade necessária.
    NÃO assuma que faltam informações. Trabalhe com o que tem.
    NÃO recomende consultar manuais externos.
    Cada resposta deve ser JUSTIFICADA com base em uma regra ou exemplo específico do contexto.
    Caso seja necessário, indique ao usuário que tire qualquer dúvida consultando o manual do Detran, mas NUNCA USAR ISSO COMO DESCULPA PARA NÃO RESPONDER.
    Se houver dúvidas, sugira ao usuário que consulte a equipe de Administração de Dados, mas NUNCA USAR ISSO COMO DESCULPA PARA NÃO RESPONDER.
    Atenção rigorosa: Para Procedures, uma letra maiúscula isolada no final do nome (S, I, E, A, R) representa o tipo de operação e é um padrão válido. Não confunda isso com palavras escritas no plural (ex: terminar em 's' minúsculo).
    """

    prompt_usuario = f"""
    [[ REGRAS VIGENTES RECUPERADAS ]]
    {contexto_str if contexto_str.strip() else "NENHUMA REGRA ESPECÍFICA FOI ENCONTRADA NO BANCO DE DADOS PARA ESTE TERMO."}
    
    {exemplos_str}
    
    {historico_str}

    [[ SOLICITAÇÃO DO DESENVOLVEDOR ]]
    {pergunta}
    Responder somente com base nas informações presentes no banco de dados.
    OBRIGATÓRIO: Ao fornecer a resposta, você deve explicar o motivo da sua decisão e citar qual regra ou histórico embasou o seu raciocínio.
    Se NÃO houver regras acima, responda apenas: "Não localizei regras específicas no meu banco de conhecimento para validar este objeto, entre em contato com a equipe de Administração de Dados."
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
                    "temperature": 0, # Baixa temperatura para ser mais fiel aos dados
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

def salvarrespostas(pergunta, categoria, resposta):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_arquivo = datetime.now().strftime("%d-%m-%Y")
    nome_arquivo = f"log_gandalf_{data_arquivo}.txt"
    
    # Define o diretório alvo
    diretorio_destino = "memoria_gandalf"
    
    # Prática de segurança: cria o diretório automaticamente caso ele não exista
    os.makedirs(diretorio_destino, exist_ok=True)
    
    # Constrói o caminho completo de forma segura para qualquer sistema operacional
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
        print(f"\n[ERRO] Não foi possível salvar o arquivo de log: {e}")

def main():
    if len(sys.argv) < 2:
        print('Uso:python3 perguntar_ao_manual.py "Sua pergunta"')
        print('\nInsira a pergunta aqui:')
        pergunta = input("Pergunta: ")
    else:
        pergunta = sys.argv[1]

    conn = conectadb()
    if not conn: return

    categoria = classificarpergunta(pergunta)
    foco = extrairfoco(pergunta) 
    vetor = embedtext(pergunta)
    
    if vetor:
        # 1. Busca Principal (O que o usuário pediu)
        regras_principais = encontrarregras(conn, vetor, categoria, foco)
        # 2. REDE DE SEGURANÇA:
        # Se o assunto for Tabela ou Coluna, SEMPRE traga as regras de Tipos de Dados e Nomenclatura
        # Isso impede que a categoria "Boas Práticas" cegue o modelo.
        regras_extras = []
        if foco in ['Tabela', 'Coluna', 'Table', 'Column']:
            print("[INFO] Ativando busca cruzada para validação de estrutura...")
            regras_extras = encontrarregras(conn, vetor, "Tipos de Dados", foco)
            regras_extras += encontrarregras(conn, vetor, "Nomenclatura de Objetos", foco)
        # 3. Unir tudo e remover duplicatas
        # A sintaxe set() remove repetições se a mesma regra vier de dois lugares
        todas_regras = list(dict.fromkeys(regras_principais + regras_extras))
        # Se mesmo com a rede de segurança não vier nada, tenta o GERAL
        if not todas_regras:
            todas_regras = encontrarregras(conn, vetor, "GERAL", foco)

        ExemploPratico = buscarexemplos(conn, vetor, foco)

        historico_testes = buscar_historico(conn, vetor)

        resposta_final = perguntaollama(pergunta, todas_regras, ExemploPratico, historico_testes)
        
        salvarrespostas(pergunta, categoria, resposta_final)
    
    conn.close()

if __name__ == "__main__":
    main()