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
from pathlib import Path
from dotenv import load_dotenv

diretorio_atual = Path(__file__).resolve().parent
caminho_env = (diretorio_atual / '..' / '.env').resolve()
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

PERGUNTAS_POR_LOTE = 5
DIRETORIO_SAIDA = diretorio_atual / "perguntas_geradas"
ARQUIVO_LOG = diretorio_atual / "memoria_teste_n_supervisionado" / "log_gerador_perguntas.txt"

CATEGORIAS_VALIDAS = [
    "Nomenclatura de Objetos",
    "Boas Práticas",
    "Integridade Referencial",
    "Stored Procedures",
    "Performance",
]

try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 5, dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
    )
except psycopg2.Error as e:
    print(f"[ERRO] Falha ao criar pool de conexoes: {e}")
    exit(1)

def registrar_log(mensagem: str):
    ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with open(ARQUIVO_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {mensagem}\n")
    print(mensagem)

def buscar_exemplos(conn, limite: int = 5) -> list[dict]:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.ExemploPratico');")
        if not cursor.fetchone()[0]:
            return []
        
        cursor.execute("""
            SELECT ExemploTexto, Explicacao
            FROM ExemploPratico
            ORDER BY RANDOM()
            LIMIT %s
        """, (limite,))
        rows = cursor.fetchall()
        return [{"exemplo": row[0], "explicacao": row[1]} for row in rows]
    except psycopg2.Error as e:
        registrar_log(f"[ERRO DB] Falha ao buscar exemplos: {e}")
        return []
    finally:
        cursor.close()

def montar_prompt(exemplos: list[dict]) -> str:
    exemplos_texto = "\n".join(f"- EXCECAO/REGRA: {e['exemplo']} | MOTIVO: {e['explicacao']}" for e in exemplos) if exemplos else ""
    categorias = ', '.join(CATEGORIAS_VALIDAS)

    return f"""Voce atua como um gerador de dados estritos de treinamento para um sistema de validacao de banco de dados do DETRAN-PE.
Baseie-se EXCLUSIVAMENTE nas regras fornecidas abaixo. NAO INVENTE NENHUMA REGRA OU SUFIXO.

REGRAS VIGENTES E EXEMPLOS:
{exemplos_texto}

TAREFA: Gere exatamente {PERGUNTAS_POR_LOTE} perguntas tecnicas e suas respectivas respostas precisas sobre as regras acima.
- As respostas devem ser diretas e citar a justificativa exata.
- Formato OBRIGATORIO: Apenas um array JSON valido. Sem explicacoes adicionais. Sem tags de marcacao.

[
  {{
    "categoria": "escolha uma entre: {categorias}",
    "pergunta": "...",
    "resposta": "..."
  }}
]"""

def gerar_perguntas_ollama(exemplos: list[dict]) -> list[dict]:
    if not exemplos: return []
    
    prompt = montar_prompt(exemplos)
    try:
        resposta = requests.post(
            ollama_api_generate,
            json={
                "model": ollama_gen_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2, 
                    "num_predict": 2048,
                }
            },
            timeout=2400
        )
        resposta.raise_for_status()
        conteudo = resposta.json().get("response", "")
        conteudo = re.sub(r"<think>.*?</think>", "", conteudo, flags=re.DOTALL).strip()
        conteudo_limpo = re.sub(r"```json|```", "", conteudo).strip()

        match = re.search(r"\[.*\]", conteudo_limpo, re.DOTALL)
        if not match: return []
        
        pares = json.loads(match.group())
        return pares if isinstance(pares, list) else []

    except Exception as e:
        registrar_log(f"[ERRO GERAL] Falha na geracao: {e}")
        return []

def salvar_como_json(pares: list[dict]):
    DIRETORIO_SAIDA.mkdir(parents=True, exist_ok=True)
    timestamp_arquivo = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    caminho = DIRETORIO_SAIDA / f"perguntas_geradas_{timestamp_arquivo}.json"

    registros = [
        {
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "categoria": p.get("categoria", "Geral"),
            "pergunta": p.get("pergunta", ""),
            "resposta": p.get("resposta", ""),
            "gerado_automaticamente": True,
            "modelo": ollama_gen_model
        } for p in pares
    ]

    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(registros, f, ensure_ascii=False, indent=4)
    registrar_log(f"[SALVO JSON] {caminho.name}")

def ciclo_geracao(conn):
    registrar_log("Iniciando ciclo de geracao de perguntas.")
    exemplos = buscar_exemplos(conn)
    pares = gerar_perguntas_ollama(exemplos)
    if pares:
        registrar_log(f"[OK] {len(pares)} pares gerados.")
        salvar_como_json(pares)

def main():
    INTERVALO_MINUTOS = int(os.getenv('GERADOR_INTERVALO_MIN', '60'))
    DURACAO_HORAS = float(os.getenv('GERADOR_DURACAO_HORAS', '12'))
    DURACAO_SEGUNDOS = DURACAO_HORAS * 3600

    registrar_log("=== Gerador Automatico de Perguntas Gandalf ===")
    start_time = time.time()

    while (time.time() - start_time) < DURACAO_SEGUNDOS:
        conn = None
        try:
            conn = db_pool.getconn()
            pgvector.psycopg2.register_vector(conn)
            ciclo_geracao(conn)
        except Exception as e:
            registrar_log(f"[ERRO CRITICO] {e}")
        finally:
            if conn: db_pool.putconn(conn)

        tempo_restante = DURACAO_SEGUNDOS - (time.time() - start_time)
        if tempo_restante > 0:
            tempo_espera = min(INTERVALO_MINUTOS * 60, tempo_restante)
            registrar_log(f"Aguardando proximo ciclo. Faltam {tempo_restante / 3600:.2f} horas.")
            time.sleep(tempo_espera)

    registrar_log("=== Fase de geracao concluida. Acionando pipeline downstream. ===")
    try:
        caminho_limpeza = diretorio_atual / "LimpezaJson.py"
        subprocess.run([sys.executable, str(caminho_limpeza)], check=True)
        
        caminho_treino = diretorio_atual / "TreinoGendalf.py"
        subprocess.run([sys.executable, str(caminho_treino)], check=True)
        registrar_log("Pipeline finalizado com sucesso.")
    except Exception as e:
        registrar_log(f"[ERRO CRITICO] Falha na orquestracao: {e}")

if __name__ == "__main__":
    main()