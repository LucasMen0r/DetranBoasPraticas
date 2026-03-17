import os
import re
import requests
import psycopg2
import pgvector.psycopg2
import pdfplumber
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
db_name = os.getenv('DB_NAME', 'DetranNorma')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASS', 'abc321')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5435') 

ollama_url = os.getenv('OLLAMA_HOST', f"http://{db_host}:11436") 
ollama_api_embed = f"{ollama_url}/api/embeddings"

def embeddingtexto(texto):
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
    caminho = Path(caminho_pdf)
    
    if not caminho.is_file():
        print(f"[ERRO] Arquivo não encontrado ou caminho inválido: {caminho}")
        return []

    try:
        paginas_extraidas = []
        with pdfplumber.open(caminho) as pdf:
            for page in pdf.pages:
                texto_extraido = page.extract_text()
                if texto_extraido:
                    paginas_extraidas.append(texto_extraido)
        
        texto_completo = "\n".join(paginas_extraidas)
        
        regras_extraidas = []
        categoria_atual = None
        objeto_atual = None
        buffer_texto = ""

        linhas = texto_completo.split('\n')

        regex_regras_gerais = re.compile(r'^2\.\s*Regras\s*Gerais', re.IGNORECASE)
        regex_banco = re.compile(r'^3\.1\s*Banco\s*de\s*Dados', re.IGNORECASE)
        regex_tabelas = re.compile(r'^3\.2\s*Tabelas', re.IGNORECASE)
        regex_colunas = re.compile(r'^3\.3\s*Colunas', re.IGNORECASE)
        regex_procedures = re.compile(r'^3\.7\s*Procedures', re.IGNORECASE)
        regex_boas_praticas = re.compile(r'^5\.\s*Recomendações', re.IGNORECASE)
        regex_manual_bolso = re.compile(r'^2\.6\s*Padrão\s*de\s*nomes', re.IGNORECASE)
        regex_dicionario = re.compile(r'^6\.\s*Dicionário\s*de\s*Termos', re.IGNORECASE)

        def salvar_buffer():
            nonlocal buffer_texto, regras_extraidas, categoria_atual, objeto_atual
            texto_limpo = buffer_texto.strip()
            
            if texto_limpo and categoria_atual and categoria_atual != 'Ignorar':
                if categoria_atual == 'Regras Gerais':
                    texto_limpo = re.sub(r'^[\W_]\s*', '', texto_limpo).strip()
                
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
                categoria_atual = 'Ignorar'
                continue

            if categoria_atual == 'Ignorar' or not categoria_atual:
                continue

            if linha.startswith('DETRAN-PE') or linha.startswith('Página'):
                continue
                
            regex_sql = r'^(CREATE\s|DECLARE\s|SELECT\s|FROM\s|WHERE\s|EXEC\s|IF\s|DROP\s|BEGIN\b|END\b|AS$|GO$|@|//|/\*)'
            if re.match(regex_sql, linha, re.IGNORECASE):
                continue

            buffer_texto = buffer_texto + " " + linha if buffer_texto else linha

            if linha.endswith('.') or linha.endswith(';') or linha.endswith(':'):
                salvar_buffer()

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

    try:
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
                    input("Pressione Enter para continuar.")
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
                embedding = embeddingtexto(prompt_composto)

                if embedding:
                    try:
                        comando_sql = """
                            INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, is_BomExemplo, Explicacao, embedding)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (ObjetoFoco, ExemploTexto) 
                            DO UPDATE SET 
                                is_BomExemplo = EXCLUDED.is_BomExemplo,
                                Explicacao = EXCLUDED.Explicacao,
                                embedding = EXCLUDED.embedding;
                        """
                        cursor.execute(comando_sql, (foco, texto, is_bom, explicacao, embedding))
                        conn.commit()
                        
                        print("\n[SUCESSO] Exemplo processado e sincronizado com sucesso na memória do Gandalf!")
                        
                    except Exception as e:
                        conn.rollback()
                        print(f"\n[ERRO BANCO] Falha ao processar o registro no banco de dados: {e}")
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
                
                diretorio_manuais = Path('Manual')
                diretorio_manuais.mkdir(exist_ok=True) 
                
                arquivos_pdf = list(diretorio_manuais.glob('*.pdf'))
                
                if not arquivos_pdf:
                    print(f"\n[AVISO] Nenhum arquivo PDF encontrado na pasta '{diretorio_manuais.resolve()}'.")
                    input("\nPressione Enter para retornar ao menu...")
                    continue
                
                print("Arquivos encontrados:\n")
                for i, pdf in enumerate(arquivos_pdf):
                    print(f"{i + 1}. {pdf.name}")
                print("0. Cancelar")

                escolha = input("\nEscolha o numero do arquivo PDF para processar: ").strip()
                
                if escolha == '0':
                    continue
                    
                try:
                    indice = int(escolha) - 1
                    if indice < 0 or indice >= len(arquivos_pdf):
                        raise ValueError
                    arquivo_selecionado = arquivos_pdf[indice]
                except ValueError:
                    print("\n[ERRO] Opção inválida.")
                    input("Pressione Enter para continuar...")
                    continue

                print("\nExtraindo texto do arquivo PDF, aguarde...")
                regras_extraidas = processarpdf_semantico(arquivo_selecionado)

                if regras_extraidas:
                    print(f"\n[INFO] Foram extraídas {len(regras_extraidas)} regras. Iniciando sincronização inteligente...")
                    inseridas = 0
                    atualizadas = 0
                    inicio_sincronizacao = datetime.now()

                    try:
                        # OTIMIZAÇÃO N+1: Carrega dicionários em memória
                        cursor.execute("SELECT NomeCategoria, pkCategoriaRegra FROM CategoriaRegra")
                        mapa_categorias = {row[0].lower(): row[1] for row in cursor.fetchall()}

                        cursor.execute("SELECT NomeObjeto, pkObjetoDb FROM ObjetoDb")
                        mapa_objetos = {row[0].lower(): row[1] for row in cursor.fetchall()}

                        for regra in regras_extraidas:
                            nome_categoria = regra.get('categoria', '').lower()
                            nome_objeto = regra.get('objeto', '').lower() if regra.get('objeto') else None
                            texto_regra = regra.get('texto')

                            # Busca otimizada via dicionário (O(1))
                            pk_categoria = mapa_categorias.get(nome_categoria)
                            
                            if not pk_categoria:
                                print(f"[AVISO] Categoria '{regra.get('categoria')}' não encontrada. Regra ignorada.")
                                continue

                            pk_objeto = mapa_objetos.get(nome_objeto) if nome_objeto else None

                            cursor.execute("""
                                SELECT pkRegraNomenclatura FROM RegraNomenclatura 
                                WHERE pkCategoriaRegra = %s 
                                AND pkObjetoDb IS NOT DISTINCT FROM %s 
                                AND DescricaoRegra = %s
                            """, (pk_categoria, pk_objeto, texto_regra))
                            
                            regra_existente = cursor.fetchone()

                            if regra_existente:
                                cursor.execute("""
                                    UPDATE RegraNomenclatura 
                                    SET ultima_verificacao = %s 
                                    WHERE pkRegraNomenclatura = %s
                                """, (inicio_sincronizacao, regra_existente[0]))
                                atualizadas += 1
                            else:
                                embedding = embeddingtexto(texto_regra)
                                if embedding:
                                    cursor.execute("""
                                        INSERT INTO RegraNomenclatura (pkCategoriaRegra, pkObjetoDb, DescricaoRegra, embedding, ultima_verificacao)
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, (pk_categoria, pk_objeto, texto_regra, embedding, inicio_sincronizacao))
                                    inseridas += 1
                                else:
                                    print(f"[ERRO IA] Falha ao vetorizar a regra inédita: {texto_regra[:30]}.")

                        cursor.execute("""
                            DELETE FROM RegraNomenclatura 
                            WHERE ultima_verificacao < %s OR ultima_verificacao IS NULL
                        """, (inicio_sincronizacao,))
                        
                        removidas = cursor.rowcount

                        conn.commit()
                        print(f"\n[SUCESSO] Sincronização do manual concluída.")
                        print(f"Novas regras registradas: {inseridas}")
                        print(f"Regras mantidas (sem alteração): {atualizadas}")
                        print(f"Regras antigas removidas (obsoletas): {removidas}")

                    except Exception as e:
                        conn.rollback()
                        print(f"\n[ERRO BANCO] Transação interrompida. Falha geral na sincronização: {e}")

                else:
                    print("\n[ERRO] Nenhuma regra extraída. Verifique a formatação do PDF.")

                input("\nPressione Enter para retornar ao menu.")
            
            elif opcao == '0':
                break
            else:
                print("Opção inválida.")
                input("Pressione Enter para continuar...")

    finally:
        # Garante o encerramento seguro da conexão e do cursor
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        print("\nSessão e conexão com o banco encerradas de forma segura.")

if __name__ == "__main__":
    main()