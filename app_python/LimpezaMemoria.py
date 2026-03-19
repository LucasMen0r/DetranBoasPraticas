import os
import requests
import shutil
from dotenv import load_dotenv

diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.abspath(os.path.join(diretorio_atual, '..', '.env'))
load_dotenv(dotenv_path=caminho_env)

# Configurações de Ambiente
DB_HOST = os.getenv('DB_HOST', 'localhost')
OLLAMA_BASE_URL = f"http://{DB_HOST}:11436"
OLLAMA_API_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = "deepseek-r1:8b" # Recomenda-se um modelo de linguagem, não de embedding, para esta etapa

# Diretórios
DIRETORIO_LOGS_BRUTOS = "memoria_gandalf"
DIRETORIO_LOGS_PROCESSADOS = "memoria_gandalf_processada"
DIRETORIO_TESTES = "arquivos_teste/testes" # Destino do texto limpo para o RAG

def extrair_conhecimento_llm(texto_log):
    prompt_sistema = (
        "Você é um engenheiro de dados limpando logs de sistema para um banco vetorial RAG. "
        "Leia o log abaixo e extraia estritamente o conhecimento técnico útil: "
        "qual foi o problema/contexto e qual foi a ação ou resolução. "
        "Ignore completamente timestamps (datas/horas), avisos de rotina ou mensagens de 'Aguardando'. "
        "Responda apenas com o resumo técnico, sem introduções.\n\n"
        f"LOG:\n{texto_log}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt_sistema,
        "stream": False
    }

    try:
        resposta = requests.post(OLLAMA_API_GENERATE, json=payload, timeout=2400)
        resposta.raise_for_status()
        return resposta.json().get('response', '').strip()
    except requests.RequestException as e:
        print(f"[ERRO] Falha ao contatar Ollama para extração: {e}")
        return None

def processar_logs():
    os.makedirs(DIRETORIO_LOGS_BRUTOS, exist_ok=True)
    os.makedirs(DIRETORIO_LOGS_PROCESSADOS, exist_ok=True)
    os.makedirs(DIRETORIO_TESTES, exist_ok=True)

    arquivos = [f for f in os.listdir(DIRETORIO_LOGS_BRUTOS) if f.endswith('.txt') or f.endswith('.log')]
    
    if not arquivos:
        print(f"[INFO] Nenhum arquivo bruto encontrado em '{DIRETORIO_LOGS_BRUTOS}'.")
        return

    for arquivo in arquivos:
        caminho_origem = os.path.join(DIRETORIO_LOGS_BRUTOS, arquivo)
        
        print(f"Limpando arquivo de log: {arquivo}...")
        
        with open(caminho_origem, 'r', encoding='utf-8') as f:
            conteudo_bruto = f.read()

        if not conteudo_bruto.strip():
            continue

        conhecimento_limpo = extrair_conhecimento_llm(conteudo_bruto)

        if conhecimento_limpo:
            novo_nome = f"clean_{arquivo}"
            caminho_destino_limpo = os.path.join(DIRETORIO_TESTES, novo_nome)
            
            with open(caminho_destino_limpo, 'w', encoding='utf-8') as f:
                f.write(conhecimento_limpo)
            
            print(f"  -> Sucesso. Conhecimento extraído e salvo como {novo_nome}.")
            
            caminho_processado = os.path.join(DIRETORIO_LOGS_PROCESSADOS, arquivo)
            shutil.move(caminho_origem, caminho_processado)
        else:
            print(f"  -> [AVISO] Nenhuma informação útil extraída ou falha no LLM para {arquivo}.")

if __name__ == "__main__":
    print("Iniciando pipeline de limpeza de memória do Gandalf.")
    processar_logs()
    print("Pipeline de limpeza concluído.")