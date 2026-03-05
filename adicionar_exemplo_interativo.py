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

    limpar_tela()
    print("=====================================================")
    print("   G.A.N.D.A.L.F - ALIMENTACAO DE BASE DE CONHECIMENTO")
    print("=====================================================")
    print("Utilize esta interface para cadastrar exemplos homologados.\n")

    while True:
        foco = input("1. Objeto Foco (ex: Tabela, Procedure, PK, Coluna, etc.): ").strip()
        if not foco:
            print("O foco nao pode ser vazio. Tente novamente.\n")
            continue

        texto = input(f"2. Exemplo de nome para '{foco}' (ex: tbCliente): ").strip()
        if not texto:
            print("O texto nao pode ser vazio. Tente novamente.\n")
            continue

        while True:
            is_bom_input = input("3. Este e um BOM exemplo a ser seguido? (S/N): ").strip().upper()
            if is_bom_input in ['S', 's', 'N', 'n']:
                is_bom = True if is_bom_input == 'S' or is_bom_input == 's' else False
                break
            print("Por favor, digite apenas 'S' para Sim ou 'N' para Nao.")

        explicacao = input("4. Explicacao tecnica do motivo (regra aplicada): ").strip()
        if not explicacao:
            print("A explicacao e obrigatoria para o treinamento. Tente novamente.\n")
            continue

        print("\nProcessando vetorizacao.")
        prompt_composto = f"{foco} : {texto}"
        embedding = get_embedding(prompt_composto)

        if embedding:
            try:
                cursor.execute("""
                    INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, is_BomExemplo, Explicacao, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                """, (foco, texto, is_bom, explicacao, embedding))
                conn.commit()
                print("\n[SUCESSO] Exemplo gravado com sucesso na memoria do Gandalf!")
            except Exception as e:
                conn.rollback()
                print(f"\n[ERRO BANCO] Falha ao gravar no banco de dados: {e}")
        else:
            print("\n[ERRO IA] Falha ao gerar embedding. O exemplo nao foi gravado.")

        continuar = input("\nDeseja cadastrar outro exemplo? (S/N): ").strip().upper()
        if continuar != 'S':
            break
        print("\n")

    cursor.close()
    conn.close()
    print("\nSessao encerrada.")

if __name__ == "__main__":
    main()