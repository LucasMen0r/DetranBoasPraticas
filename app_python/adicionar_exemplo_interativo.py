import os
import requests
import psycopg2
import pgvector.psycopg2
from PyPDF2 import PdfReader

db_name = os.getenv('DB_NAME', 'DetranNorma')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASS', 'abc321')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5435')

ollama_url = os.getenv('OLLAMA_HOST', f"http://{db_host}:11436")
ollama_api_embed = f"{ollama_url}/api/embeddings"

def get_embedding(texto):
    try:
        resposta = requests.post(
            ollama_api_embed,
            json={"model": "nomic-embed-text:latest", "prompt": texto}
        )
        resposta.raise_for_status()
        return resposta.json()['embedding']
    except requests.RequestException as e:
        print(f"[ERRO OLLAMA] Falha ao vetorizar: {e}")
        return None

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def processarpdf(caminho_pdf):
    """Extrai texto do PDF e divide em chunks para evitar estouro de contexto."""
    if not os.path.exists(caminho_pdf):
        print(f"[ERRO] Arquivo não encontrado: {caminho_pdf}")
        return []

    try:
        reader = PdfReader(caminho_pdf)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text() + "\n"
        
        # Estratégia de Chunking Simples (ex: cada 1000 caracteres)
        # Em produção, recomenda-se RecursiveCharacterTextSplitter
        tamanho_chunk = 1000
        return [texto_completo[i:i + tamanho_chunk] for i in range(0, len(texto_completo), tamanho_chunk)]
    except Exception as e:
        print(f"[ERRO PDF] Falha ao ler arquivo: {e}")
        return []

def main():
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port
        )
        pgvector.psycopg2.register_vector(conn)
        cursor = conn.cursor()
    except psycopg2.Error as e:
        print(f"Erro de Conexao com o Banco: {e}")
        return

    while True:
        limpar_tela()
        print("=====================================================")
        print("   G.A.N.D.A.L.F - ALIMENTACAO DE BASE DE CONHECIMENTO")
        print("=====================================================")
        print("1. Adicionar ou Atualizar Exemplo")
        print("2. Remover Exemplo Existente")
        print("3. Sair\n")

        opcao = input("Escolha uma opcao: ").strip()

        if opcao == '1':
            foco = input("Objeto Foco (ex: Tabela, Procedure, PK, Coluna, etc.): ").strip()
            if not foco:
                print("O foco nao pode ser vazio. Tente novamente.\n")
                input("Pressione Enter para continuar...")
                continue

            texto = input(f"Exemplo de nome para '{foco}' (ex: tbCliente): ").strip()
            if not texto:
                print("O texto nao pode ser vazio. Tente novamente.\n")
                input("Pressione Enter para continuar...")
                continue

            while True:
                is_bom_input = input("Este e um BOM exemplo a ser seguido? (S/N): ").strip().upper()
                if is_bom_input in ['S', 'N']:
                    is_bom = True if is_bom_input == 'S' or is_bom_input == 's' else False
                    break
                print("Por favor, digite apenas 'S' para Sim ou 'N' para Nao.")

            explicacao = input("Explicacao tecnica do motivo (regra aplicada): ").strip()
            if not explicacao:
                print("A explicacao e obrigatoria. Tente novamente.\n")
                input("Pressione Enter para continuar...")
                continue

            print("\nProcessando vetorizacao...")
            prompt_composto = f"{foco} : {texto}"
            embedding = get_embedding(prompt_composto)

            if embedding:
                try:
                    # Verifica se o registro já existe
                    cursor.execute("SELECT 1 FROM ExemploPratico WHERE ObjetoFoco = %s AND ExemploTexto = %s", (foco, texto))
                    existe = cursor.fetchone()

                    if existe:
                        cursor.execute("""
                            UPDATE ExemploPratico 
                            SET is_BomExemplo = %s, Explicacao = %s, embedding = %s
                            WHERE ObjetoFoco = %s AND ExemploTexto = %s
                        """, (is_bom, explicacao, embedding, foco, texto))
                        print("\n[SUCESSO] Exemplo atualizado com sucesso na memoria do Gandalf!")
                    else:
                        cursor.execute("""
                            INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, is_BomExemplo, Explicacao, embedding)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (foco, texto, is_bom, explicacao, embedding))
                        print("\n[SUCESSO] Exemplo gravado com sucesso na memoria do Gandalf!")
                    
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"\n[ERRO BANCO] Falha ao gravar no banco de dados: {e}")
            else:
                print("\n[ERRO IA] Falha ao gerar embedding. O exemplo nao foi gravado.")
            
            input("\nPressione Enter para retornar ao menu...")

        elif opcao == '2':
            print("\n--- Remover Exemplo ---")
            foco = input("Objeto Foco do exemplo a remover: ").strip()
            texto = input("Texto do exemplo a remover: ").strip()

            if not foco or not texto:
                print("Foco e texto sao obrigatorios para a remocao.\n")
                input("Pressione Enter para continuar...")
                continue

            try:
                cursor.execute("DELETE FROM ExemploPratico WHERE ObjetoFoco = %s AND ExemploTexto = %s", (foco, texto))
                if cursor.rowcount > 0:
                    conn.commit()
                    print(f"\n[SUCESSO] Foram removidos {cursor.rowcount} registro(s) da memoria.")
                else:
                    print("\n[AVISO] Nenhum registro encontrado com esses dados.")
            except Exception as e:
                conn.rollback()
                print(f"\n[ERRO BANCO] Falha ao remover do banco de dados: {e}")

            input("\nPressione Enter para retornar ao menu...")

        elif opcao == '3':
            break
        else:
            print("Opcao invalida.")
            input("Pressione Enter para continuar...")

    cursor.close()
    conn.close()
    print("\nSessao encerrada.")

if __name__ == "__main__":
    main()