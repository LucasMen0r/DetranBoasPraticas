import os
import re
import requests
import psycopg2
import pgvector.psycopg2
import pdfplumber
from dotenv import load_dotenv

load_dotenv()
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

def processarpdf_semantico(caminho_pdf):
    """Extrai texto estruturado do PDF utilizando PDFPlumber, Regex e Buffer de Parágrafos."""
    if not os.path.exists(caminho_pdf):
        print(f"[ERRO] Arquivo não encontrado: {caminho_pdf}")
        return []

    try:
        texto_completo = ""
        with pdfplumber.open(caminho_pdf) as pdf:
            for page in pdf.pages:
                texto_extraido = page.extract_text()
                if texto_extraido:
                    texto_completo += texto_extraido + "\n"
        
        regras_extraidas = []
        categoria_atual = None
        objeto_atual = None
        buffer_texto = ""

        linhas = texto_completo.split('\n')

        # Expressões Regulares de navegação
        regex_regras_gerais = re.compile(r'^2\.\s*Regras\s*Gerais', re.IGNORECASE)
        regex_banco = re.compile(r'^3\.1\s*Banco\s*de\s*Dados', re.IGNORECASE)
        regex_tabelas = re.compile(r'^3\.2\s*Tabelas', re.IGNORECASE)
        regex_colunas = re.compile(r'^3\.3\s*Colunas', re.IGNORECASE)
        regex_procedures = re.compile(r'^3\.7\s*Procedures', re.IGNORECASE)
        regex_boas_praticas = re.compile(r'^5\.\s*Recomendações', re.IGNORECASE)
        regex_manual_bolso = re.compile(r'^2\.6\s*Padrão\s*de\s*nomes', re.IGNORECASE)
        regex_dicionario = re.compile(r'^6\.\s*Dicionário\s*de\s*Termos', re.IGNORECASE) # Ponto de parada

        def salvar_buffer():
            nonlocal buffer_texto, regras_extraidas, categoria_atual, objeto_atual
            texto_limpo = buffer_texto.strip()
            
            if texto_limpo and categoria_atual and categoria_atual != 'Ignorar':
                if categoria_atual == 'Regras Gerais':
                    # Limpa o caractere de checkbox ou marcadores residuais
                    texto_limpo = re.sub(r'^[\W_]\s*', '', texto_limpo).strip()
                
                # Filtro final para evitar frases soltas ou exemplos
                if len(texto_limpo) > 15 and not texto_limpo.lower().startswith('exemplo'):
                    regras_extraidas.append({
                        'categoria': categoria_atual,
                        'objeto': objeto_atual,
                        'texto': texto_limpo
                    })
            buffer_texto = ""

        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue

            # 1. Máquina de Estados (Identificação de Seções)
            if regex_regras_gerais.match(linha):
                salvar_buffer()
                categoria_atual = 'Regras Gerais'
                objeto_atual = None
                continue
            elif regex_manual_bolso.match(linha):
                salvar_buffer()
                categoria_atual = 'Ignorar'
                continue
            elif regex_banco.match(linha):
                salvar_buffer()
                categoria_atual = 'Nomenclatura de Objetos'
                objeto_atual = 'Banco'
                continue
            elif regex_tabelas.match(linha):
                salvar_buffer()
                categoria_atual = 'Nomenclatura de Objetos'
                objeto_atual = 'Tabela'
                continue
            elif regex_colunas.match(linha):
                salvar_buffer()
                categoria_atual = 'Nomenclatura de Objetos'
                objeto_atual = 'Coluna'
                continue
            elif regex_procedures.match(linha):
                salvar_buffer()
                categoria_atual = 'Nomenclatura de Objetos'
                objeto_atual = 'Procedure'
                continue
            elif regex_boas_praticas.match(linha):
                salvar_buffer()
                categoria_atual = 'Boas Práticas'
                objeto_atual = None
                continue
            elif regex_dicionario.match(linha):
                salvar_buffer()
                categoria_atual = 'Ignorar' # Bloqueia a leitura das tabelas do final do PDF
                continue

            # 2. Acúmulo no Buffer
            if categoria_atual == 'Ignorar' or not categoria_atual:
                continue

            # Ignora cabeçalhos e rodapés de página
            if linha.startswith('DETRAN-PE') or linha.startswith('Página'):
                continue
                
            # Filtro Semântico: Ignora linhas de código de exemplo e comentários SQL do PDF
            regex_sql = r'^(CREATE\s|DECLARE\s|SELECT\s|FROM\s|WHERE\s|EXEC\s|IF\s|DROP\s|BEGIN\b|END\b|AS$|GO$|@|//|/\*)'
            if re.match(regex_sql, linha, re.IGNORECASE):
                continue

            # Adiciona a linha atual ao buffer, garantindo o espaçamento correto
            buffer_texto = buffer_texto + " " + linha if buffer_texto else linha

            # Se a linha encerrar com pontuação final, consideramos a regra completa e limpamos o buffer
            if linha.endswith('.') or linha.endswith(';') or linha.endswith(':'):
                salvar_buffer()

        # Garante que a última regra do documento seja salva caso não tenha terminador
        salvar_buffer()

        return regras_extraidas

    except Exception as e:
        print(f"[ERRO PDF] Falha ao processar arquivo: {e}")
        return []
    
def main():
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port
        )
        pgvector.psycopg2.register_vector(conn)
        cursor = conn.cursor()
    except psycopg2.Error as e:
        print(f"Erro de Conexão com o Banco: {e}")
        return

    while True:
        limpar_tela()
        print("=====================================================")
        print("   G.A.N.D.A.L.F - ALIMENTACAO DE BASE DE CONHECIMENTO")
        print("=====================================================")
        print("1. Adicionar ou Atualizar Exemplo")
        print("2. Remover Exemplo Existente")
        print("3. Inserir PDF com novas regras\n")
        print("0. Sair")

        opcao = input("Escolha uma opcao: ").strip()

        if opcao == '1':
            foco = input("Objeto Foco (ex: Tabela, Procedure, PK, Coluna, etc.): ").strip()
            if not foco:
                print("O foco não pode ser vazio. Tente novamente.\n")
                input("Pressione Enter para continuar.")
                continue

            texto = input(f"Exemplo de nome para '{foco}' (ex: dbhcen.alunodisciplina): ").strip()
            if not texto:
                print("O texto não pode ser vazio. Tente novamente.\n")
                input("Pressione Enter para continuar...")
                continue

            while True:
                is_bom_input = input("Este é um BOM exemplo a ser seguido? (S/N): ").strip().upper()
                if is_bom_input in ['S', 'N']:
                    is_bom = True if is_bom_input == 'S' else False
                    break
                print("Por favor, digite apenas 'S' para Sim ou 'N' para Não.")

            explicacao = input("Explicação técnica do motivo (regra aplicada): ").strip()
            if not explicacao:
                print("A explicação é obrigatória. Tente novamente.\n")
                input("Pressione Enter para continuar.")
                continue

            print("\nProcessando vetorização. Aguarde.")
            prompt_composto = f"{foco} : {texto}"
            embedding = get_embedding(prompt_composto)

            if embedding:
                try:
                    cursor.execute("SELECT 1 FROM ExemploPratico WHERE ObjetoFoco = %s AND ExemploTexto = %s", (foco, texto))
                    existe = cursor.fetchone()

                    if existe:
                        cursor.execute("""
                            UPDATE ExemploPratico 
                            SET is_BomExemplo = %s, Explicacao = %s, embedding = %s
                            WHERE ObjetoFoco = %s AND ExemploTexto = %s
                        """, (is_bom, explicacao, embedding, foco, texto))
                        print("\n[SUCESSO] Exemplo atualizado com sucesso na memória do Gandalf!")
                    else:
                        cursor.execute("""
                            INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, is_BomExemplo, Explicacao, embedding)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (foco, texto, is_bom, explicacao, embedding))
                        print("\n[SUCESSO] Exemplo gravado com sucesso na memória do Gandalf!")
                    
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"\n[ERRO BANCO] Falha ao gravar no banco de dados: {e}")
            else:
                print("\n[ERRO IA] Falha ao gerar embedding. O exemplo não foi gravado.")
            
            input("\nPressione Enter para retornar ao menu...")

        elif opcao == '2':
            print("\n--- Remover Exemplo ---")
            foco = input("Objeto Foco do exemplo a remover: ").strip()
            texto = input("Texto do exemplo a remover: ").strip()

            if not foco or not texto:
                print("Foco e texto são obrigatórios para a remoção.\n")
                input("Pressione Enter para continuar...")
                continue

            try:
                cursor.execute("DELETE FROM ExemploPratico WHERE ObjetoFoco = %s AND ExemploTexto = %s", (foco, texto))
                if cursor.rowcount > 0:
                    conn.commit()
                    print(f"\n[SUCESSO] Foram removidos {cursor.rowcount} registro(s) da memória.")
                else:
                    print("\n[AVISO] Nenhum registro encontrado com esses dados.")
            except Exception as e:
                conn.rollback()
                print(f"\n[ERRO BANCO] Falha ao remover do banco de dados: {e}")

            input("\nPressione Enter para retornar ao menu...")

        elif opcao == '3':
            print("\n--- Inserir PDF com Novas Regras ---")
            caminho_pdf = input("Digite o caminho completo do arquivo PDF: ").strip()
            regras_extraidas = processarpdf_semantico(caminho_pdf)

            if regras_extraidas:
                print(f"\n[INFO] Foram extraídas {len(regras_extraidas)} regras. Iniciando vetorização e inserção...")
                inseridas = 0
                ignoradas = 0

                for regra in regras_extraidas:
                    nome_categoria = regra.get('categoria')
                    nome_objeto = regra.get('objeto')
                    texto_regra = regra.get('texto')

                    # 1. Resolução da Chave Estrangeira da Categoria
                    cursor.execute("SELECT pkCategoriaRegra FROM CategoriaRegra WHERE NomeCategoria = %s", (nome_categoria,))
                    cat_result = cursor.fetchone()
                    pk_categoria = cat_result[0] if cat_result else None

                    if not pk_categoria:
                        print(f"[AVISO] Categoria '{nome_categoria}' não encontrada no banco. Regra ignorada.")
                        continue

                    # 2. Resolução da Chave Estrangeira do Objeto (Aceita NULL)
                    pk_objeto = None
                    if nome_objeto:
                        cursor.execute("SELECT pkObjetoDb FROM ObjetoDb WHERE NomeObjeto = %s", (nome_objeto,))
                        obj_result = cursor.fetchone()
                        pk_objeto = obj_result[0] if obj_result else None

                    # 3. Gerar Embedding
                    embedding = get_embedding(texto_regra)

                    if embedding:
                        try:
                            # 4. Inserção Segura com Controle de Duplicatas
                            cursor.execute("""
                                INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, embedding)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT ON CONSTRAINT ukRegraUnica DO NOTHING
                            """, (pk_categoria, pk_objeto, texto_regra, embedding))

                            if cursor.rowcount > 0:
                                inseridas += 1
                            else:
                                ignoradas += 1
                                
                            conn.commit()
                        except Exception as e:
                            conn.rollback()
                            print(f"[ERRO BANCO] Falha na regra '{texto_regra[:30]}...': {e}")
                    else:
                        print(f"[ERRO IA] Falha ao vetorizar a regra: {texto_regra[:30]}...")

                print(f"\n[SUCESSO] Processamento de PDF concluído.")
                print(f"Novas regras registradas: {inseridas}")
                print(f"Regras ignoradas (duplicatas): {ignoradas}")

            else:
                print("\n[ERRO] Nenhuma regra extraída. Verifique o caminho e a formatação do PDF.")

            input("\nPressione Enter para retornar ao menu.")
        
        elif opcao == '0':
            break
        else:
            print("Opção inválida.")
            input("Pressione Enter para continuar...")

    cursor.close()
    conn.close()
    print("\nSessão encerrada.")

if __name__ == "__main__":
    main()