import psycopg2
from psycopg2 import pool
from datetime import datetime
import os
import json
import time
import requests
import re
import pgvector
import pgvector.psycopg2
import sys
import subprocess
import time
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# Configuração de ambiente (igual ao TreinoGendalf)
# ─────────────────────────────────────────────
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.abspath(os.path.join(diretorio_atual, '..', '.env'))
load_dotenv(dotenv_path=caminho_env)

DB_NAME = os.getenv('DB_NAME', 'DetranNorma')
DB_USER = os.getenv('DB_USER', 'ollama_trainer')
DB_PASS = os.getenv('DB_PASS', '123456')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5435')

ollama_base_url = os.getenv('OLLAMA_HOST', 'http://localhost:11436')
ollama_embed_model  = "nomic-embed-text:latest"
ollama_gen_model    = "deepseek-r1:8b"
ollama_api_embed    = f"{ollama_base_url}/api/embeddings"
ollama_api_generate = f"{ollama_base_url}/api/generate"

# Quantas perguntas gerar por ciclo
PERGUNTAS_POR_LOTE = 5

DIRETORIO_SAIDA = "perguntas_geradas"
ARQUIVO_LOG     = "memoria_teste_n_supervisionado/log_gerador_perguntas.txt"

CATEGORIAS_VALIDAS = [
    "Nomenclatura de Objetos",
    "Boas Práticas",
    "Integridade Referencial",
    "Stored Procedures",
    "Performance",
]
# ─────────────────────────────────────────────
# Pool de conexões
# ─────────────────────────────────────────────
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 5,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS,
        host=DB_HOST, port=DB_PORT
    )
except psycopg2.Error as e:
    print(f"[ERRO] Falha ao criar pool de conexões: {e}")
    exit(1)

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
def registrar_log(mensagem: str):
    os.makedirs(os.path.dirname(ARQUIVO_LOG), exist_ok=True)
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {mensagem}\n")
    print(mensagem)

# ─────────────────────────────────────────────
# Embedding (Ollama)
# ─────────────────────────────────────────────
def embedtext(text: str):
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

# ─────────────────────────────────────────────
# Buscar contexto do banco (ExemploPratico)
# ─────────────────────────────────────────────
def buscar_exemplos(conn, limite: int = 20) -> list[dict]:
    """Retorna exemplos práticos da tabela ExemploPratico como contexto para geração."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if not cursor.fetchone()[0]:
            registrar_log("[AVISO] Tabela ExemploPratico não existe no banco.")
            return []
        cursor.execute("""
            SELECT ExemploTexto, Explicacao
            FROM ExemploPratico
            ORDER BY pkExemploPratico
            LIMIT %s
        """, (limite,))
        rows = cursor.fetchall()
        registrar_log(f"[DB] {len(rows)} exemplos carregados de ExemploPratico.")
        return [{"exemplo": row[0], "explicacao": row[1]} for row in rows]
    except psycopg2.Error as e:
        registrar_log(f"[ERRO DB] Falha ao buscar exemplos: {e}")
        return []
    finally:
        cursor.close()

# ─────────────────────────────────────────────
# Geração de perguntas via Ollama (deepseek-r1:8b)
# ─────────────────────────────────────────────
def montar_prompt(exemplos: list[dict]) -> str:
    if exemplos:
        exemplos_texto = "\n".join(
            f"  - Exemplo: {e['exemplo']}\n    Explicacao: {e['explicacao']}"
            for e in exemplos
        )
    else:
        exemplos_texto = "  (nenhum exemplo disponivel na tabela ExemploPratico)"

    categorias = ', '.join(CATEGORIAS_VALIDAS)

    return f"""Voce e um especialista em banco de dados Sybase e padroes de nomenclatura do DETRAN-PE.

A seguir estao exemplos praticos reais extraidos da base de conhecimento do sistema,
que ilustram as regras de nomenclatura e boas praticas vigentes:

{exemplos_texto}

---

Sua tarefa: com base EXCLUSIVAMENTE nesses exemplos, gerar exatamente {PERGUNTAS_POR_LOTE} pares
de PERGUNTA e RESPOSTA para treinar um assistente RAG que valida nomenclaturas e boas praticas do DETRAN-PE.

Diretrizes:
1. Cada pergunta deve soar natural, como um desenvolvedor perguntaria ao assistente.
2. Varie os tipos: validacao de nome especifico, pergunta conceitual, pedido de correcao, duvida sobre sufixos/prefixos/operacoes.
3. Nomes de procedures inventados devem seguir o padrao dbfisc01..NomeProcedure.scp quando aplicavel.
4. A resposta deve ser tecnica, citar o exemplo ou regra relevante e ser objetiva.
5. Cada par deve ter uma CATEGORIA dentre: {categorias}.

Responda APENAS com um array JSON valido, sem texto antes ou depois, sem blocos de codigo markdown:
[
  {{
    "categoria": "...",
    "pergunta": "...",
    "resposta": "..."
  }}
]"""

def gerar_perguntas_ollama(exemplos: list[dict]) -> list[dict]:
    """Chama o Ollama local (deepseek-r1:8b) para gerar pares pergunta/resposta."""
    if not exemplos:
        registrar_log("[AVISO] Sem exemplos praticos para gerar perguntas. Abortando ciclo.")
        return []

    prompt = montar_prompt(exemplos)
    registrar_log(f"[OLLAMA] Chamando {ollama_gen_model} para geracao (pode demorar alguns minutos)...")

    try:
        resposta = requests.post(
            ollama_api_generate,
            json={
                "model": ollama_gen_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 2048,
                }
            },
            timeout=2400  # timeout generoso para perguntas complexas
        )
        resposta.raise_for_status()
        conteudo = resposta.json().get("response", "")

        # O deepseek-r1 usa tags <think>...</think> para raciocinio interno — removemos
        conteudo = re.sub(r"<think>.*?</think>", "", conteudo, flags=re.DOTALL).strip()

        # Remove possiveis blocos markdown antes do parse
        conteudo_limpo = re.sub(r"```json|```", "", conteudo).strip()

        # Extrai o primeiro array JSON encontrado na resposta
        match = re.search(r"\[.*\]", conteudo_limpo, re.DOTALL)
        if not match:
            registrar_log(f"[AVISO] Nenhum array JSON encontrado na resposta.\nConteudo: {conteudo_limpo[:300]}")
            return []

        pares = json.loads(match.group())

        if not isinstance(pares, list):
            registrar_log("[AVISO] Resposta parseada nao e uma lista JSON.")
            return []

        registrar_log(f"[OLLAMA] {len(pares)} pares gerados com sucesso.")
        return pares

    except requests.RequestException as e:
        registrar_log(f"[ERRO OLLAMA] Falha na chamada de geracao: {e}")
        return []
    except json.JSONDecodeError as e:
        registrar_log(f"[ERRO JSON] Falha ao parsear resposta: {e}\nConteudo: {conteudo_limpo[:300]}")
        return []

# ─────────────────────────────────────────────
# Salvar perguntas geradas
# ─────────────────────────────────────────────
def salvar_como_historico(pares: list[dict]):
    """Salva no formato .txt identico ao historico existente."""
    os.makedirs(DIRETORIO_SAIDA, exist_ok=True)
    timestamp_arquivo = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    caminho = os.path.join(DIRETORIO_SAIDA, f"perguntas_geradas_{timestamp_arquivo}.txt")

    with open(caminho, 'w', encoding='utf-8') as f:
        for par in pares:
            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            f.write("========================================\n")
            f.write(f"DATA: {data_hora}\n")
            f.write("========================================\n")
            f.write(f"CATEGORIA: {par.get('categoria', 'Geral')}\n")
            f.write("========================================\n")
            f.write(f"PERGUNTA: {par.get('pergunta', '')}\n")
            f.write("========================================\n")
            f.write(f"RESPOSTA:\n{par.get('resposta', '')}\n")
            f.write("========================================\n\n")

    registrar_log(f"[SALVO TXT] {len(pares)} pares em: {caminho}")
    return caminho

def salvar_como_json(pares: list[dict]):
    """Salva em JSON no mesmo formato dos logs do Gandalf."""
    os.makedirs(DIRETORIO_SAIDA, exist_ok=True)
    timestamp_arquivo = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    caminho = os.path.join(DIRETORIO_SAIDA, f"perguntas_geradas_{timestamp_arquivo}.json")

    registros = [
        {
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "categoria": p.get("categoria", "Geral"),
            "pergunta": p.get("pergunta", ""),
            "resposta": p.get("resposta", ""),
            "gerado_automaticamente": True,
            "modelo": ollama_gen_model
        }
        for p in pares
    ]

    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(registros, f, ensure_ascii=False, indent=4)

    registrar_log(f"[SALVO JSON] {caminho}")
    return caminho

# ─────────────────────────────────────────────
# Loop principal
# ─────────────────────────────────────────────
def ciclo_geracao(conn):
    registrar_log("── Iniciando ciclo de geracao de perguntas ──")

    exemplos = buscar_exemplos(conn)

    if not exemplos:
        registrar_log("[AVISO] Tabela ExemploPratico vazia ou inexistente. Ciclo ignorado.")
        return

    pares = gerar_perguntas_ollama(exemplos)

    if not pares:
        registrar_log("[AVISO] Nenhum par gerado neste ciclo.")
        return

    registrar_log(f"[OK] {len(pares)} pares gerados.")
    salvar_como_historico(pares)
    salvar_como_json(pares)

def main():
    INTERVALO_MINUTOS = int(os.getenv('GERADOR_INTERVALO_MIN', '60'))
    # Define a duração em horas (pode colocar no .env também, padrão 12h)
    DURACAO_HORAS = float(os.getenv('GERADOR_DURACAO_HORAS', '12'))
    DURACAO_SEGUNDOS = DURACAO_HORAS * 3600

    registrar_log("=== Gerador Automatico de Perguntas Gandalf ===")
    registrar_log(f"Modelo: {ollama_gen_model} | Duracao Maxima: {DURACAO_HORAS}h | Intervalo: {INTERVALO_MINUTOS} min")

    start_time = time.time()

    # Loop condicionado ao tempo decorrido
    while (time.time() - start_time) < DURACAO_SEGUNDOS:
        conn = None
        try:
            conn = db_pool.getconn()
            pgvector.psycopg2.register_vector(conn)
            ciclo_geracao(conn)
        except Exception as e:
            registrar_log(f"[ERRO CRITICO] {e}")
        finally:
            if conn:
                db_pool.putconn(conn)

        tempo_passado = time.time() - start_time
        tempo_restante = DURACAO_SEGUNDOS - tempo_passado

        # Se ainda houver tempo, aguarda para o próximo ciclo
        if tempo_restante > 0:
            # Espera o intervalo padrão ou o tempo que resta, o que for menor
            tempo_espera = min(INTERVALO_MINUTOS * 60, tempo_restante)
            horas_restantes = tempo_restante / 3600
            registrar_log(f"Aguardando {tempo_espera/60:.1f} min. Faltam {horas_restantes:.2f} horas para concluir a fase de geracao.")
            time.sleep(tempo_espera)

    registrar_log("=== Tempo limite atingido. Encerrando geracao. ===")
    registrar_log("Acionando rotina de limpeza de dados.")

    try:
        # 1. Chama a limpeza
        caminho_limpeza = os.path.join(diretorio_atual, "perguntas_geradas", "LimpezaJson.py")
        subprocess.run([sys.executable, caminho_limpeza], check=True)
        registrar_log("Limpeza de JSON executada e flags atribuidas com sucesso.")
        
        # 2. Chama o treinamento
        registrar_log("Acionando a esteira de treinamento (TreinoGendalf.py)...")
        caminho_treino = os.path.join(diretorio_atual, "TreinoGendalf.py")
        subprocess.run([sys.executable, caminho_treino], check=True)
        registrar_log("Treinamento acionado e concluido com sucesso.")
        
    except subprocess.CalledProcessError as e:
        registrar_log(f"[ERRO CRITICO] Falha na execucao da esteira (Subprocesso): {e}")
    except Exception as e:
        registrar_log(f"[ERRO CRITICO] Erro inesperado ao orquestrar scripts: {e}")

if __name__ == "__main__":
    main()