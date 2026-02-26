import re

ARQUIVO_LOG = "historico_auditoria_jan2026.txt"

def diagnosticar_falhas():
    try:
        with open(ARQUIVO_LOG, 'r', encoding='utf-8') as f:
            conteudo = f.read()
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{ARQUIVO_LOG}' não encontrado.")
        return

    interacoes = conteudo.split("DATA:")
    perguntas_falhas = []
    
    for bloco in interacoes:
        if "PERGUNTA:" not in bloco or "RESPOSTA:" not in bloco:
            continue

        try:
            # Extrair Pergunta
            parte_pergunta = bloco.split("PERGUNTA:")[1]
            texto_pergunta = parte_pergunta.split("RESPOSTA:")[0].strip()
            
            # Extrair Resposta
            parte_resposta = bloco.split("RESPOSTA:")[1]
            texto_resposta = parte_resposta.split("=====")[0].strip().lower()

            # Se houve falha de memória, salva a pergunta para analisarmos
            if "não localizei regras" in texto_resposta or "não encontrei regras" in texto_resposta:
                perguntas_falhas.append(texto_pergunta)
                
        except IndexError:
            continue

    print(f"\n=== RELATÓRIO DE FALHAS (A Lista Negra) ===")
    print(f"Total de falhas detectadas: {len(perguntas_falhas)}")
    print("-" * 50)
    
    if len(perguntas_falhas) == 0:
        print("Nenhuma falha encontrada! (Ué, mas deu 69% antes?)")
    else:
        for i, p in enumerate(perguntas_falhas, 1):
            print(f"{i}. {p}")
            
    print("-" * 50)
    print("DICA: Analise se essas perguntas usam termos que não estão no seu banco SQL.")

if __name__ == "__main__":
    diagnosticar_falhas()
