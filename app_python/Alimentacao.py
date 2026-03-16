import os
import shutil
from datetime import datetime

# Configurações de diretórios baseadas na sua estrutura
DIRETORIO_MEMORIA = "memoria_gandalf"
DIRETORIO_TESTES = "arquivos_teste"

def extrair_conhecimento_consolidado():
    """Lê os logs diários e cria um arquivo de 're-treino' para o RAG."""
    os.makedirs(DIRETORIO_TESTES, exist_ok=True)
    
    if not os.path.exists(DIRETORIO_MEMORIA):
        print(f"[ERRO] Diretório {DIRETORIO_MEMORIA} não encontrado.")
        return

    arquivos_log = [f for f in os.listdir(DIRETORIO_MEMORIA) if f.startswith('log_gandalf_')]
    
    if not arquivos_log:
        print("[INFO] Nenhum log de memória encontrado para processar.")
        return

    conhecimento_acumulado = []

    for log in arquivos_log:
        caminho = os.path.join(DIRETORIO_MEMORIA, log)
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                conteudo = f.read()
                # Adiciona o conteúdo do log ao acumulador
                conhecimento_acumulado.append(f"--- FONTE: {log} ---\n{conteudo}\n")
        except Exception as e:
            print(f"[ERRO] Falha ao ler {log}: {e}")

    if conhecimento_acumulado:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_saida = f"consolidado_memoria_{timestamp}.txt"
        caminho_saida = os.path.join(DIRETORIO_TESTES, nome_saida)
        
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            f.write("\n".join(conhecimento_acumulado))
        
        print(f"[SUCESSO] Gerado arquivo de treino: {nome_saida}")
        print(f"[INFO] O TreinoGandalf.py processará este arquivo no próximo ciclo.")

if __name__ == "__main__":
    extrair_conhecimento_consolidado()