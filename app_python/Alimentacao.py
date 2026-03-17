import os
import json
from datetime import datetime

DIRETORIO_MEMORIA = "memoria_gandalf"
DIRETORIO_TESTES = "arquivos_teste"

def extrair_conhecimento_consolidado():
    """Lê os logs diários em JSON e cria um arquivo de 're-treino' para o RAG."""
    os.makedirs(DIRETORIO_TESTES, exist_ok=True)
    
    if not os.path.exists(DIRETORIO_MEMORIA):
        print(f"[ERRO] Diretório {DIRETORIO_MEMORIA} não encontrado.")
        return

    # Alterado para buscar arquivos .json
    arquivos_log = [f for f in os.listdir(DIRETORIO_MEMORIA) if f.startswith('log_gandalf_') and f.endswith('.json')]
    
    if not arquivos_log:
        print("[INFO] Nenhum log de memória encontrado para processar.")
        return

    conhecimento_acumulado = []

    for log in arquivos_log:
        caminho = os.path.join(DIRETORIO_MEMORIA, log)
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                dados_json = json.load(f)
                
                # Itera sobre o array de objetos JSON
                for registro in dados_json:
                    pergunta = registro.get("pergunta", "")
                    resposta = registro.get("resposta", "")
                    categoria = registro.get("categoria", "GERAL")
                    
                    # Formata de volta para um bloco de texto legível para o embedding do TreinoGandalf
                    bloco_texto = (
                        f"Categoria Associada: {categoria}\n"
                        f"Pergunta do Usuário: {pergunta}\n"
                        f"Resolução Técnica: {resposta}\n"
                    )
                    conhecimento_acumulado.append(f"--- FONTE: {log} ---\n{bloco_texto}\n")
        except json.JSONDecodeError as e:
            print(f"[ERRO] Arquivo JSON corrompido ou mal formatado {log}: {e}")
        except Exception as e:
            print(f"[ERRO] Falha ao ler {log}: {e}")

    if conhecimento_acumulado:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_saida = f"consolidado_memoria_{timestamp}.txt"
        caminho_saida = os.path.join(DIRETORIO_TESTES, nome_saida)
        
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            f.write("\n".join(conhecimento_acumulado))
        
        print(f"[SUCESSO] Gerado arquivo de treino consolidado: {nome_saida}")