import json
from pathlib import Path
from typing import List, Dict

def diagnosticar_falhas_json() -> None:
    # Aponta dinamicamente para a pasta onde o PerguntarManual salva os logs
    diretorio_logs = Path(__file__).resolve().parent.parent / "memoria_gandalf"
    
    if not diretorio_logs.exists():
        print(f"[ERRO] Diretório '{diretorio_logs.name}' não encontrado.")
        print("Certifique-se de já ter feito perguntas ao Gandalf para gerar logs.")
        return

    # Busca todos os arquivos JSON gerados pelo Gandalf
    arquivos_log = list(diretorio_logs.glob("log_gandalf_*.json"))
    
    if not arquivos_log:
        print(f"[INFO] Nenhum arquivo JSON de log encontrado em '{diretorio_logs.name}'.")
        return

    total_perguntas = 0
    perguntas_falhas: List[Dict[str, str]] = []

    for arquivo in arquivos_log:
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                
            for interacao in logs:
                total_perguntas += 1
                resposta = interacao.get("resposta", "").lower()
                pergunta = interacao.get("pergunta", "Pergunta não registrada")
                categoria = interacao.get("categoria", "GERAL")
                
                # O gatilho de falha de RAG (quando o Gandalf não acha contexto)
                if "não localizei regras" in resposta or "não encontrei regras" in resposta:
                    perguntas_falhas.append({
                        "pergunta": pergunta,
                        "categoria": categoria,
                        "arquivo": arquivo.name
                    })
                    
        except json.JSONDecodeError:
            print(f"[AVISO] O arquivo {arquivo.name} está corrompido ou vazio.")
        except Exception as e:
            print(f"[ERRO] Falha ao ler {arquivo.name}: {e}")

    # --- CÁLCULO DE ACURÁCIA MATEMÁTICA ---
    total_falhas = len(perguntas_falhas)
    total_sucesso = total_perguntas - total_falhas
    
    acuracia = 0.0
    if total_perguntas > 0:
        acuracia = (total_sucesso / total_perguntas) * 100

    # --- RELATÓRIO FINAL ---
    print("\n" + "="*50)
    print("=== RELATÓRIO DE ACURÁCIA DO G.A.N.D.A.L.F ===")
    print("="*50)
    print(f"Total de Interações Analisadas: {total_perguntas}")
    print(f"Respostas com Sucesso (Regras Aplicadas): {total_sucesso}")
    print(f"Respostas com Falha (Sem Contexto): {total_falhas}")
    print(f"\n---> ACURÁCIA ATUAL: {acuracia:.2f}% <---")
    print("="*50)
    
    if total_falhas == 0 and total_perguntas > 0:
        print("\nNenhuma falha de contexto encontrada! O RAG está cobrindo todas as requisições.")
    elif total_falhas > 0:
        print("\n=== LISTA NEGRA DE CONHECIMENTO (Blind Spots) ===")
        print("As perguntas abaixo exigem adição de regras ou exemplos no banco de dados:\n")
        for i, item in enumerate(perguntas_falhas, 1):
            print(f"{i}. [{item['categoria']}] {item['pergunta']}")
            print(f"   (Encontrado no log: {item['arquivo']})\n")

if __name__ == "__main__":
    diagnosticar_falhas_json()