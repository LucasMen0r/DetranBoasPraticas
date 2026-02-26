import sys
import time
import random
import psycopg2
import requests
from datetime import datetime

# Importa as ferramentas do seu script original
# Certifique-se de que o arquivo perguntar_ao_manual.py está na mesma pasta ou no path
from perguntar_ao_manual import conectadb, embedtext, encontrarregras, perguntaollama, limparrespostadeepseek, salvarrespotas

# --- CONFIGURAÇÕES ---
ARQUIVO_FERIAS = "LOG_FERIAS_GANDALF.txt" # O nome do arquivo que será salvo
DB_HOST = 'localhost'
OLLAMA_CHAT = f"http://{DB_HOST}:11434/api/chat"
MODELO_GERADOR = "deepseek-r1:8b" # Modelo usado para INVENTAR as perguntas

def gerar_pergunta_simulada(regra_texto):
    """
    Usa o Ollama para criar uma dúvida técnica baseada em uma regra real do banco.
    """
    prompt = f"""
    Aja como um desenvolvedor júnior confuso.
    Com base nesta regra técnica: "{regra_texto}"
    Crie uma pergunta curta e direta (uma frase) perguntando se pode fazer algo que viole ou que siga essa regra.
    Exemplo: "Posso criar a tabela com nome X?"
    Não dê explicações, apenas a pergunta.
    """
    try:
        resp = requests.post(OLLAMA_CHAT, json={
            "model": MODELO_GERADOR,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.8} # Criatividade alta para variar as perguntas
        })
        if resp.status_code == 200:
            return limparrespostadeepseek(resp.json()['message']['content'])
        return None
    except Exception as e:
        print(f"[ERRO GERADOR] {e}")
        return None

def auditoria_automatica():
    conn = conectadb()
    if not conn: 
        print("Erro ao conectar no banco.")
        return

    cursor = conn.cursor()
    print(f">>> INICIANDO MODO FÉRIAS <<<")
    print(f"As respostas serão salvas em: {ARQUIVO_FERIAS}")
    
    ciclos = 0
    
    while True:
        try:
            ciclos += 1
            print(f"\n--- CICLO {ciclos} INICIADO ---")
            
            # 1. Sorteia uma regra do banco para ser o tema do teste
            cursor.execute("SELECT DescricaoRegra FROM RegraNomenclatura ORDER BY RANDOM() LIMIT 1")
            resultado = cursor.fetchone()
            
            if not resultado:
                print("Banco de regras vazio! Abortando.")
                break
                
            regra_base = resultado[0]
            
            # 2. O 'Aluno' (Ollama) cria uma pergunta sobre essa regra
            print(f"[1/4] Gerando pergunta baseada na regra...")
            pergunta_simulada = gerar_pergunta_simulada(regra_base)
            
            if pergunta_simulada:
                print(f"      Pergunta gerada: {pergunta_simulada}")
                
                # 3. O 'Professor' (Gandalf) responde usando o RAG normal
                print(f"[2/4] Vetorizando...")
                vetor = embedtext(pergunta_simulada)
                
                print(f"[3/4] Buscando regras...")
                # Busca regras REAIS no banco para responder a pergunta SIMULADA
                regras_encontradas = encontrarregras(conn, vetor, "GERAL", "Auditoria")
                
                print(f"[4/4] Gerando resposta do Gandalf...")
                resposta_final = perguntaollama(pergunta_simulada, regras_encontradas, [])
                
                # 4. SALVA NO ARQUIVO (Usando sua função original)
                # Passamos o nome do arquivo de férias para não misturar com os antigos
                salvarrespotas(pergunta_simulada, "AUDITORIA_AUTOMATICA", resposta_final, nome_arquivo=ARQUIVO_FERIAS)
                
                print("[SUCESSO] Interação registrada no arquivo.")
            
            # 5. Intervalo aleatório para não sobrecarregar (entre 2 e 6 horas)
            # 2 horas = 7200 segundos | 6 horas = 21600 segundos
            tempo_espera = random.randint(7200, 21600)
            
            # (Para teste rápido agora, troque a linha acima por: tempo_espera = 60)
            
            proxima_execucao = datetime.fromtimestamp(time.time() + tempo_espera).strftime('%d/%m %H:%M')
            print(f"[DORMINDO] O Gandalf vai descansar por {tempo_espera/3600:.1f} horas.")
            print(f"[AGENDADO] Próximo teste: {proxima_execucao}")
            
            time.sleep(tempo_espera)
            
            # Mantém a conexão viva
            conn.commit()

        except Exception as e:
            print(f"[ERRO CRÍTICO] Ocorreu uma falha no loop: {e}")
            # Se der erro, espera 10 minutos e tenta de novo
            time.sleep(600)
            conn = conectadb() # Tenta reconectar

if __name__ == "__main__":
    auditoria_automatica()
