import pgvector
import psycopg2
import os
import requests
import sys
import json
import pgvector.psycopg2
from datetime import datetime
import re
from dotenv import load_dotenv

# Identifica a pasta exata onde este script Python está localizado
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(diretorio_atual, '.env')

# Carrega o .env passando o caminho absoluto
load_dotenv(caminho_env)

# Restante do seu código (usando o método com fallback das imagens)
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
        sql_base = """
        SELECT r.DescricaoRegra
        FROM RegraNomenclatura r
        JOIN CategoriaRegra c ON r.pkCategoriaRegra = c.pkCategoriaRegra
        LEFT JOIN ObjetoDb o ON r.pkObjetoDb = o.pkObjetoDb
        """
        # A trava de segurança que barra regras muito distantes do contexto
        filtro_distancia = " r.embedding <=> %s::vector < 0.45 "
        
        # O SQL agora ordena primeiro pelo Objeto, depois pela proximidade semântica (distância vetorial), 
        # e como critério de desempate, traz os registros mais recentes (pk maior) primeiro.
        order_clause = """
        ORDER BY 
            (CASE WHEN o.NomeObjeto ILIKE %s THEN 0 ELSE 1 END) ASC, 
            r.embedding <=> %s::vector ASC,
            r.pkRegraNomenclatura DESC 
        LIMIT %s;
        """
        term_boost = f"%{foco_usuario}%"

        if "GERAL" in Nomecategoria.upper():
            sql = sql_base + " WHERE " + filtro_distancia + order_clause
            # O vetor é passado duas vezes para preencher os dois %s (do WHERE e do ORDER BY)
            parametros = (list(pergunta_vetor), term_boost, list(pergunta_vetor), top_k)
        else:
            sql = sql_base + " WHERE c.NomeCategoria ILIKE %s AND " + filtro_distancia + order_clause
            # O vetor também entra duas vezes aqui, respeitando a ordem do SQL
            parametros = (f"%{Nomecategoria}%", list(pergunta_vetor), term_boost, list(pergunta_vetor), top_k)
            
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao encontrar regras: {e}")
        return []
    finally:
        cursor.close()

def buscar_historico(conn, pergunta_vetor, top_k=3):
    """Busca no histórico de testes e aprendizados (Memória)."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT to_regclass('public.ConhecimentoHistorico');")
        if not cursor.fetchone()[0]:
            return []

        print("Buscando na memória de testes do Gandalf.")
        sql = """
        SELECT nome_arquivo, conteudo_texto
        FROM ConhecimentoHistorico
        WHERE embedding <=> %s::vector < 0.45
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        # O vetor é passado duas vezes: para o filtro WHERE e para a ordenação ORDER BY
        cursor.execute(sql, (list(pergunta_vetor), list(pergunta_vetor), top_k))
        return cursor.fetchall()
        
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao buscar histórico: {e}")
        return []
    finally:
        cursor.close()

def buscarexemplos(conn, pergunta_vetor, foco_usuario, top_k=4):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if not cursor.fetchone()[0]:
            return []

        print("Buscando exemplos praticos similares.")
        
        sql = """
        SELECT is_BomExemplo, ExemploTexto, Explicacao
        FROM ExemploPratico
        WHERE embedding <=> %s::vector < 0.45
        ORDER BY (CASE WHEN ObjetoFoco ILIKE %s THEN 0 ELSE 1 END) ASC, embedding <=> %s::vector LIMIT %s;
        """
        # Ajuste cuidadoso na ordem da tupla para casar exatamente com os %s da query
        cursor.execute(sql, (list(pergunta_vetor), f"%{foco_usuario}%", list(pergunta_vetor), top_k))
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao buscar exemplos: {e}")
        return []
    finally:
        cursor.close()

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
    
    INSTRUÇÃO MESTRA E HIERARQUIA DE REGRAS:
    Você receberá diferentes fontes de conhecimento. Siga ESTA ORDEM de prioridade absoluta para a sua decisão:
    PRIORIDADE 1 (MÁXIMA): [[ EXEMPLOS DE REFERÊNCIA ]]. Se o código do usuário seguir a mesma estrutura de um exemplo APROVADO, aprove imediatamente, mesmo que pareça violar uma regra geral. Se for semelhante a um REPROVADO, reprove.
    PRIORIDADE 2: [[ REGRAS VIGENTES ]]. Aplique as regras listadas para o objeto específico. 
    PRIORIDADE 3: [[ CONHECIMENTO ADQUIRIDO ]]. Use o histórico apenas como contexto de apoio.

    Siga estas diretrizes absolutas para emitir o seu parecer:
    1. PRECISÃO DE REGRAS: Quando aprovar um objeto, cite a regra ou o exemplo exato.
    2. CONTEXTO DO POSTGRESQL: Scripts DDL executados sem aspas duplas gerarão objetos inteiramente em minúsculas. Reprove tentativas de burlar as normas com variações de case.
    3. ZERO ALUCINAÇÃO: Nunca invente regras.
    4. PRECISÃO DA JUSTIFICATIVA: Transcreva a regra exata ou o exemplo que embasou a decisão.
    5. FILTRO DE RELEVÂNCIA: Ignore regras de outros objetos (ex: ignorar regras de Tabela ao avaliar Procedure).

    ESTRUTURA DE RESPOSTA OBRIGATÓRIA:
    Você deve formatar a sua resposta EXATAMENTE com os 4 tópicos abaixo, usando Markdown.
    **Objeto Analisado:** [Tipo do objeto e nome extraído]
    **Conformidade:** [APROVADO ou REPROVADO]
    **Justificativa:** [Explique o motivo citando o texto exato da regra ou o Exemplo Prático de Referência]
    **Recomendação:** [Orientação técnica final]
    """

    prompt_usuario = f"""
    [[ CONHECIMENTO ADQUIRIDO EM TESTES ANTERIORES ]]
    {historico_str if historico_str.strip() else "Nenhum histórico."}

    [[ REGRAS VIGENTES RECUPERADAS ]]
    {contexto_str if contexto_str.strip() else "Nenhuma regra encontrada."}
    
    [[ EXEMPLOS DE REFERÊNCIA (PRIORIDADE MÁXIMA - USE COMO GABARITO) ]]
    {exemplos_str if exemplos_str.strip() else "Nenhum exemplo prático homologado encontrado."}

    [[ SOLICITAÇÃO DO DESENVOLVEDOR ]]
    {pergunta}
    
    Responder somente com base nas informações acima, respeitando a Hierarquia de Regras.
    Se NÃO houver informações acima, responda apenas: "Não localizei regras específicas no meu banco de conhecimento para validar este objeto, entre em contato com a equipe de Administração de Dados."
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
                    "temperature": 0, 
                    "num_ctx": 4096     
                }
            },
            stream=True,
            timeout=360 # O script desiste e avisa o erro se o Ollama travar por 3 minutos
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
        
    except requests.exceptions.Timeout:
        return "\n[ERRO DE TIMEOUT] O modelo demorou muito para responder. Verifique se o Ollama está rodando e o uso de CPU/RAM."
    except Exception as e:
        print(f"\n[ERRO NA GERAÇÃO]: {e}")
        return f"Erro técnico ao consultar LLM: {e}"
        
    except Exception as e:
        print(f"\n[ERRO NA GERAÇÃO]: {e}")
        return f"Erro técnico ao consultar LLM: {e}"

def salvarrespostas(pergunta, categoria, resposta):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_arquivo = datetime.now().strftime("%d-%m-%Y")
    nome_arquivo = f"log_gandalf_{data_arquivo}.json"
    
    diretorio_destino = "memoria_gandalf"
    os.makedirs(diretorio_destino, exist_ok=True)
    caminho_completo = os.path.join(diretorio_destino, nome_arquivo)
    
    novo_registro = {
        "data_hora": timestamp,
        "categoria": categoria,
        "pergunta": pergunta,
        "resposta": resposta
    }
    
    registros = []
    
    # Lê o arquivo existente para manter a estrutura do array JSON válida
    if os.path.exists(caminho_completo):
        try:
            with open(caminho_completo, "r", encoding="utf-8") as f:
                # Se o arquivo estiver vazio, json.load lançará uma exceção
                conteudo = f.read()
                if conteudo.strip():
                    registros = json.loads(conteudo)
        except json.JSONDecodeError as e:
            print(f"\n[AVISO] Falha ao ler o JSON existente ({e}). Iniciando um novo array.")
            # Dependendo do nível de criticidade, você poderia fazer um backup do arquivo corrompido aqui
    
    registros.append(novo_registro)
    
    try:
        with open(caminho_completo, "w", encoding="utf-8") as f:
            # indent=4 formata o JSON para ser legível por humanos
            # ensure_ascii=False garante que acentos fiquem corretos (ex: "Aprovação" ao invés de "Aprova\u00e7\u00e3o")
            json.dump(registros, f, ensure_ascii=False, indent=4)
        print(f"\n[INFO] Resposta salva no log diário em: '{caminho_completo}'")
    except Exception as e:
        print(f"\n[ERRO] Não foi possível salvar o arquivo de log: {e}")
def main():
    if len(sys.argv) < 2:
        print('\nExemplo de uso: Pergunta: "Posso usar o nome "Cliente" para uma tabela?"')
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