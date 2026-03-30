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
from typing import List, Tuple, Optional, Any

diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(diretorio_atual, '.env')
load_dotenv(caminho_env)

db_name = os.getenv('DB_NAME', 'DetranNorma')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASS', 'abc321')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5435')
DIRETORIO_TESTES = "arquivos_teste" 

ollama_chat_model = "deepseek-r1:8b"
ollama_embed_model = "nomic-embed-text:latest"
ollama_base_url = f"http://{db_host}:11436" 
ollama_api_embed = f"{ollama_base_url}/api/embeddings"
ollama_api_chat = f"{ollama_base_url}/api/chat"

def limparrespostadeepseek(textobruto: str) -> str:
    if not textobruto:
        return " " 
    texto_limpo = re.sub(r'<think>.*?</think>', '', textobruto, flags=re.DOTALL)
    return texto_limpo.strip()

def conectadb() -> Optional[Any]:
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port
        )
        pgvector.psycopg2.register_vector(conn)
        return conn
    except psycopg2.Error as e:
        print(f"Erro de Conexão com o Banco: {e}")
        return None

def embedtext(text: str) -> Optional[List[float]]: 
    try: 
        resposta = requests.post( 
            ollama_api_embed, 
            json={"model": ollama_embed_model, "prompt": text},
            timeout=30
        ) 
        resposta.raise_for_status() 
        return resposta.json()['embedding'] 
    except requests.RequestException as e: 
        print(f"[ERRO OLLAMA] Falha ao vetorizar: {e}") 
        return None

def classificarpergunta(pergunta: str) -> str:
    categorias_validas = ["Nomenclatura de Objetos", "Boas Práticas", "Tipos de Dados", "Regras Gerais"]
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

def extrairfoco(pergunta: str) -> str:
    prompt = f"""
    Aja como um classificador de banco de dados.
    Sua tarefa: Identificar o objeto principal da pergunta e converter para o termo padrão do Detran.
    
    TABELA DE CONVERSÃO:
    - "table", "tabelas", "entidade" -> Tabela
    - "column", "field", "atributo", "campo" -> Coluna
    - "proc", "procedure" -> Procedure
    - "index", "indice" -> Índice
    - "trigger", "gatilho" -> Trigger
    
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
                "options": {"temperature": 0}
            }
        )
        resposta.raise_for_status() 
        texto_limpo = limparrespostadeepseek(resposta.json()['message']['content'])
        foco = texto_limpo.strip().split('\n')[0].replace(".", "").replace('"', "").replace("'", "")
        return foco
    except:
        return ""
    
def encontrarregras(conn, pergunta_vetor: List[float], Nomecategoria: str, foco_usuario: str, top_k: int = 5, limite_distancia: float = 0.5) -> List[Tuple]:
    cursor = conn.cursor()
    try:
        sql_base = """
        SELECT r.DescricaoRegra
        FROM RegraNomenclatura r
        JOIN CategoriaRegra c ON r.pkCategoriaRegra = c.pkCategoriaRegra
        LEFT JOIN ObjetoDb o ON r.pkObjetoDb = o.pkObjetoDb
        """
        filtro_distancia = " r.embedding <=> %s::vector < %s "
        order_clause = """
        ORDER BY 
            (CASE WHEN o.NomeObjeto ILIKE %s THEN 0 ELSE 1 END) ASC, 
            r.embedding <=> %s::vector ASC
        LIMIT %s;
        """
        term_boost = f"%{foco_usuario}%"

        if "GERAL" in Nomecategoria.upper():
            sql = sql_base + " WHERE " + filtro_distancia + order_clause
            parametros = (list(pergunta_vetor), limite_distancia, term_boost, list(pergunta_vetor), top_k)
        else:
            sql = sql_base + " WHERE c.NomeCategoria ILIKE %s AND " + filtro_distancia + order_clause
            parametros = (f"%{Nomecategoria}%", list(pergunta_vetor), limite_distancia, term_boost, list(pergunta_vetor), top_k)
            
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        print(f"[ERRO SQL] Falha ao encontrar regras: {e}")
        return []
    finally:
        cursor.close()

def buscar_historico(conn, pergunta_vetor: List[float], top_k: int = 3) -> List[Tuple]:
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT to_regclass('public.ConhecimentoHistorico');")
        if not cursor.fetchone()[0]:
            return []

        sql = """
        SELECT nome_arquivo, conteudo_texto
        FROM ConhecimentoHistorico
        WHERE embedding <=> %s::vector < 0.35
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        cursor.execute(sql, (list(pergunta_vetor), list(pergunta_vetor), top_k))
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        return []
    finally:
        cursor.close()

def buscarexemplos(conn, pergunta_vetor: List[float], foco_usuario: str, top_k: int = 4) -> List[Tuple]:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if not cursor.fetchone()[0]:
            return []

        sql = """
        SELECT is_BomExemplo, ExemploTexto, Explicacao
        FROM ExemploPratico
        WHERE embedding <=> %s::vector < 0.32
        ORDER BY (CASE WHEN ObjetoFoco ILIKE %s THEN 0 ELSE 1 END) ASC, embedding <=> %s::vector LIMIT %s;
        """
        cursor.execute(sql, (list(pergunta_vetor), f"%{foco_usuario}%", list(pergunta_vetor), top_k))
        return cursor.fetchall()
    except Exception as e:
        conn.rollback()
        return []
    finally:
        cursor.close()

def perguntaollama(pergunta: str, contexto_regras: List, ExemploPratico: List, historico_testes: List) -> str:
    print("\n" + "="*10)
    print(f"[DEBUG] Regras totais recuperadas do Banco: {len(contexto_regras)}")
    if not contexto_regras:
        print("[ALERTA] O Retrieval retornou lista vazia! O contexto sera nulo.")
    else:
        for i, dados_regra in enumerate(contexto_regras[:5]):
            regra = dados_regra[0]
            regra_curta = (regra[:80] + '..') if regra else "N/A"
            print(f"   {i+1}. {regra_curta}")
    print("="*10 + "\n")

    contexto_str = ""
    if contexto_regras:
        contexto_str = "\n".join(f"- Regra: {str(dados_regra[0] or '')}" for dados_regra in contexto_regras)
    
    exemplos_str = ""
    if ExemploPratico:
        exemplos_str = "\n[[ EXEMPLOS DE REFERENCIA (USE COMO GABARITO) ]]\n"
        for is_bom, texto, explicacao in ExemploPratico:
            tipo_txt = "APROVADO (Seguir este modelo)" if is_bom else "REPROVADO (Evitar este modelo)"
            exemplos_str += f"[{tipo_txt}]: {texto} -> Motivo: {explicacao}\n"

    historico_str = ""
    if historico_testes:
        historico_str = "\n[[ CONHECIMENTO ADQUIRIDO EM TESTES ANTERIORES ]]\n"
        for nome_arquivo, texto in historico_testes:
            historico_str += f"- (Referencia: {nome_arquivo}): {texto}\n"

    print(" RESPOSTA DO G.E.N.D.A.L.F:") 
    print("#"*15)

    prompt_sistema = """
    Voce e o G.E.N.D.A.L.F (Gestor de Analise de Normas do Detran).
    Sua funcao e atuar como um AUDITOR RIGIDO de banco de dados.
    
    INSTRUCAO MESTRA E HIERARQUIA DE REGRAS:
    PRIORIDADE 1: [[ EXEMPLOS DE REFERENCIA ]]. 
    PRIORIDADE 2: [[ REGRAS VIGENTES ]]. Aplique as regras listadas para o objeto especifico. 
    PRIORIDADE 3: [[ CONHECIMENTO ADQUIRIDO ]]. Use o historico como apoio.

    DIRETRIZES E REGRAS DE AVALIACAO:
    1. PRECISAO: Cite a regra ou exemplo exato na justificativa.
    2. ZERO ALUCINACAO E OBJETIVIDADE: Nunca invente regras ou avalie regras de objetos nao solicitados. Nao utilize emojis na formatacao da resposta.
    3. COBERTURA: Analise cada componente (Tabela, Indices, Triggers) que estiver presente na solicitacao do usuario.
    4. FORMATACAO ESTRITA (GABARITO OBRIGATORIO PARA RECOMENDACOES):
       - Para corrigir nomes de tabelas e colunas, o formato exigido e a Notacao Hungara do Detran: Primeira letra de cada palavra maiuscula, demais minusculas, SEM ESPACOS e SEM UNDERLINES.
       - CORRECAO PROIBIDA: data_entrega, tbl_documento, id_veiculo.
       - CORRECAO EXIGIDA: DataEntrega, DocumentoVeiculo, Veiculo.
       - Para corrigir indices, o formato exigido e: nomedatabela_primeiracoluna.
       - CORRECAO PROIBIDA: idx_data, index_2.
       - CORRECAO EXIGIDA: docveiculo_datainclusao.
    5. ANTI-ALUCINACAO SQL: 
       - NUNCA sugira o uso de espacos em branco em nomes de tabelas ou colunas.
       - NUNCA recomende o formato snake_case (separacao_por_underline) a menos que uma regra recem-recuperada exija explicitamente.
       - NUNCA recomende o uso de prefixos genericos como "tbl" ou "col" a menos que uma regra recem-recuperada exija explicitamente.
    6. SUPOSICOES: Se a pergunta for vaga ou ambigua, responda com base nas regras mais proximas, mas deixe claro na justificativa quais suposicoes voce fez.
    7. CONFLITOS: Caso haja conflito entre regras, priorize a regra mais especifica para o objeto em questao (ex: regra para "Tabela" tem prioridade sobre regra geral).
    8. AVALIACAO PARCIAL: Caso um objeto esteja parcialmente correto, indique claramente quais partes estao corretas e quais precisam de ajuste.

    ESTRUTURA DE RESPOSTA OBRIGATORIA (em Markdown):
    **Objeto Analisado:** [O que esta sendo analisado]
    **Conformidade:** [APROVADO ou REPROVADO]
    **Justificativa:** [Motivo baseado nas regras]
    **Recomendacao:** [Orientacao tecnica]
    """

    prompt_usuario = f"""
    [[ CONHECIMENTO ADQUIRIDO EM TESTES ANTERIORES ]]
    {historico_str if historico_str.strip() else "Nenhum historico."}

    [[ REGRAS VIGENTES RECUPERADAS ]]
    {contexto_str if contexto_str.strip() else "Nenhuma regra encontrada."}
    
    [[ EXEMPLOS DE REFERENCIA (PRIORIDADE MAXIMA) ]]
    {exemplos_str if exemplos_str.strip() else "Nenhum exemplo homologado encontrado."}

    [[ SOLICITACAO DO DESENVOLVEDOR (ANALISE ESTA DDL) ]]
    {pergunta}
    
    Se NAO houver regras aplicaveis acima, responda: "Nao localizei regras especificas no meu banco de conhecimento para validar este objeto, entre em contato com a equipe de Administracao de Dados."
    """

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
                "options": {"temperature": 0, "num_ctx": 4096}
            },
            stream=True,
            timeout=360
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
                except ValueError: pass
        print("\n") 
        
        fim_real = datetime.now()
        tempo_total_sec = (fim_real - inicio_real).total_seconds()
        ollama_eval  = metrics.get('eval_duration', 0) / 1e9
        tokens_gerados = metrics.get('eval_count', 0)
        tps = tokens_gerados / ollama_eval if ollama_eval > 0 else 0

        print("-" * 40)
        print(f"DIAGNOSTICO DE VELOCIDADE:")
        print(f"Tempo Total:             {tempo_total_sec:.2f}s")
        print(f"Velocidade de Escrita:   {tps:.2f} tokens/s")
        print("-" * 10)
        return limparrespostadeepseek(resposta_completa)
        
    except Exception as e:
        print(f"\n[ERRO NA GERACAO]: {e}")
        return f"Erro tecnico ao consultar LLM: {e}"

def salvarrespostas(pergunta: str, categoria: str, resposta: str) -> None:
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_arquivo = datetime.now().strftime("%d-%m-%Y")
    nome_arquivo = f"log_gandalf_{data_arquivo}.json"
    diretorio_destino = "memoria_gandalf"
    os.makedirs(diretorio_destino, exist_ok=True)
    caminho_completo = os.path.join(diretorio_destino, nome_arquivo)
    
    novo_registro = {"data_hora": timestamp, "categoria": categoria, "pergunta": pergunta, "resposta": resposta}
    registros = []
    if os.path.exists(caminho_completo):
        try:
            with open(caminho_completo, "r", encoding="utf-8") as f:
                conteudo = f.read()
                if conteudo.strip(): registros = json.loads(conteudo)
        except json.JSONDecodeError: pass
    
    registros.append(novo_registro)
    try:
        with open(caminho_completo, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=4)
    except Exception: pass

def main():
    if len(sys.argv) < 2:
        print('\nExemplo de uso: Pergunta: "Posso usar o nome Cliente para uma tabela?"')
        pergunta = input("Pergunta: ")
    else:
        pergunta = sys.argv[1]

    conn = conectadb()
    if not conn: return

    categoria = classificarpergunta(pergunta)
    foco = extrairfoco(pergunta)
    vetor_completo = embedtext(pergunta)
    
    if not vetor_completo:
        conn.close()
        return

    todas_regras = []
    
    if len(pergunta) > 800:
        print("\n[INFO] Modo Generalista acionado (Script longo detectado).")
        distancia = 0.48
        limite_regras = 15
    else:
        print("\n[INFO] Modo Precisão acionado (Pergunta direta).")
        distancia = 0.32
        limite_regras = 5

    regras_principais = encontrarregras(conn, vetor_completo, categoria, foco, top_k=limite_regras, limite_distancia=distancia)
    
    regras_extras = []
    if foco in ['Tabela', 'Coluna', 'Table', 'Column']:
        regras_extras = encontrarregras(conn, vetor_completo, "Tipos de Dados", foco, top_k=limite_regras, limite_distancia=distancia)
        regras_extras += encontrarregras(conn, vetor_completo, "Nomenclatura de Objetos", foco, top_k=limite_regras, limite_distancia=distancia)
    
    todas_regras.extend(regras_principais + regras_extras)
    
    if not todas_regras:
        todas_regras = encontrarregras(conn, vetor_completo, "GERAL", foco, top_k=limite_regras, limite_distancia=distancia)

    todas_regras = list(dict.fromkeys(todas_regras))
    
    ExemploPratico = buscarexemplos(conn, vetor_completo, foco)
    historico_testes = buscar_historico(conn, vetor_completo)

    resposta_final = perguntaollama(pergunta, todas_regras, ExemploPratico, historico_testes)
    salvarrespostas(pergunta, categoria, resposta_final)
    
    conn.close()

if __name__ == "__main__":
    main()