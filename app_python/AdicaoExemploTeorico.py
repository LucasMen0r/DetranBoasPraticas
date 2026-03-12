import os
import requests
import psycopg2
from dotenv import load_dotenv
import pgvector.psycopg2

# Configuracoes de Banco de Dados e Ollama
load_dotenv()
db_name = os.getenv('DB_NAME', 'DetranNorma')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASS', 'abc321')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5435')

ollama_url = os.getenv('OLLAMA_HOST', f"http://{db_host}:11436")
ollama_api_embed = f"{ollama_url}/api/embeddings"

def auditar_nomenclatura(foco, texto):
    """Aplica as regras de negocio para validar a nomenclatura dos objetos."""
    if foco == "View":
        if texto.startswith("vw"):
            if "_" not in texto:
                return True, "Correto: Inicia com prefixo 'vw' e usa notação húngara."
            else:
                return False, "Erro: View inicia com 'vw' mas contem '_' (use notação húngara)."
        elif texto.startswith("vm"):
            return True, "Correto: Inicia com prefixo 'vm' (View Materializada)."
        else:
            return False, "Erro: Views devem iniciar obrigatoriamente com 'vw' ou 'vm'."

    elif foco == "Tabela":
        if texto.startswith("tb"):
            return False, "Erro: Tabelas NAO devem utilizar o prefixo 'tb'."
        elif "_" in texto:
            return False, "Erro: Tabelas devem usar notação húngara, sem snake_case."
        elif texto.startswith("Log") or texto.startswith("tmp") or texto.startswith("temp"):
            return True, "Correto: Uso aceito de prefixo especial (Log/tmp/temp)."
        elif texto.startswith("px"):
            return True, "Correto: Uso aceito para Proxy Tables (px + Origem + Nome)."
        elif texto.startswith("z") and len(texto) > 1 and texto[1].islower():
            return True, "Correto: Uso aceito para tabelas de descarte (z + login)."
        else:
            if texto.endswith("s") and not texto.endswith("ss") and not texto.endswith("is"):
                return False, "Atencao: Nome da tabela parece estar no plural (deve ser Singular)."
            else:
                return True, "Correto: Nome descritivo, no singular e em notação húngara."

    elif foco == "Procedure":
        sufixos_validos = ['S', 'I', 'E', 'A', 'R']
        ultimo_char = texto[-1] if texto else ' '

        # 1. Regras de Exclusao (devem ser validadas primeiro)
        if texto.startswith("tmp"):
            return False, "Erro: O prefixo 'tmp' e exclusivo para tabelas temporarias, nao procedures."
            
        # 2. Regras de Permissao
        elif texto.startswith("Batch"):
            return True, "Correto: Procedure de processamento em lote inicia com 'Batch'."
        elif texto.startswith("Rpc"):
            return True, "Correto: Procedure cross-system inicia com 'Rpc'."
        elif texto.startswith("i") and len(texto) > 1 and texto[1].isupper():
            return True, "Correto: Procedure para acesso web inicia com 'i' minusculo."
        elif ultimo_char in sufixos_validos:
            return True, f"Correto: Termina com a sigla da operacao '{ultimo_char}'."
        elif texto.endswith(("ar", "er", "ir")):
            return True, "Correto: Operacao descrita com verbo no infinitivo no final."
        else:
            return False, "Erro: Procedures devem terminar com sigla (S,I,E,A,R) ou verbo no infinitivo no fim."
            
    elif foco in ["PK", "pk"]:
        if texto.startswith("pk") and "_" not in texto:
            return True, "Correto: Prefixo 'pk' + NomeTabela em notação húngara."
        else:
            return False, "Erro: Chaves primarias devem ser 'pk' + NomeTabela."

    elif foco in ["FK", "fk"]:
        if texto.startswith("fk"):
            return True, "Correto: Prefixo 'fk' + TabelaFilha + TabelaPai."
        else:
            return False, "Erro: Chaves estrangeiras devem iniciar com 'fk'."
        
    elif foco in ["Trigger", "trigger"]:
        if texto.startswith("tg") and "_" not in texto:
            return True, "Correto: Prefixo 'tg' + NomeTabela + Operacao (S,I,E)."
        else:
            return False, "Erro: Triggers devem ser 'tg' + NomeTabela + Operacao (S,I,E) e sem '_'."

    else:
        return True, "Validacao generica: formato aceito para fins de exemplo."
def get_embedding(texto):
    """Gera o vetor do texto utilizando o Ollama."""
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

def main():
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port
        )
        conn.autocommit = False
        pgvector.psycopg2.register_vector(conn)
        cursor = conn.cursor()
    except psycopg2.Error as e:
        print(f"Erro de Conexao com o Banco: {e}")
        return

    print("Iniciando R.A.G. revisor")
    print("Recriando tabela ExemploPratico")

    try:
        # Garante que a extensao vector existe e recria a tabela do zero
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExemploPratico (
                pkExemploPratico SERIAL PRIMARY KEY,
                ObjetoFoco TEXT,
                ExemploTexto TEXT,
                is_BomExemplo BOOLEAN,
                Explicacao TEXT,
                embedding vector(768)
            );
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao configurar o banco: {e}")
        return

    dados_brutos = [
        # BONS EXEMPLOS EXTRAIDOS
        ("Procedure", "EscalaA"),
        ("Procedure", "EscalaI"),
        ("Procedure", "EscalaS"),
        ("Procedure", "NotificarToxicologicoA"),
        ("Procedure", "NotificarToxicologicoS"),
        ("Procedure", "ConsultaTurnoEscalaS"),
        ("Procedure", "ConsultarTurnoHorarioA"),
        ("Procedure", "ConsultarTurnoHorarioE"),
        ("Procedure", "ConsultarTurnoHorarioS"),
        ("Procedure", "CadastrarTurnoHorarioI"),
        ("Tabela", "tmpParcelaDebitoSefaz"),
        ("Trigger", "tgProvimentoCetranI"),
        ("Trigger", "tgProvimentoJariI"),
        
        # MAUS EXEMPLOS EXTRAIDOS
        ("Procedure", "tmpParcelaDebitoSefazD"),
        ("Procedure", "tmpParcelaDebitoSefazI"),
        ]

    print(f"Iniciando carga e auditoria de {len(dados_brutos)} exemplos.")

    for foco, texto in dados_brutos:
        is_bom_auto, explicacao_auto = auditar_nomenclatura(foco, texto)
        
        prompt_composto = f"{foco} : {texto}"
        embedding = get_embedding(prompt_composto)

        if embedding:
            try:
                cursor.execute("""
                    INSERT INTO ExemploPratico (ObjetoFoco, ExemploTexto, is_BomExemplo, Explicacao, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                """, (foco, texto, is_bom_auto, explicacao_auto, embedding))
                
                status = "BOM" if is_bom_auto else "RUIM"
                print(f"Processado: [{foco}] {status} -> {texto}")
            except Exception as e:
                conn.rollback()
                print(f"Erro ao inserir '{texto}': {e}")
        else:
            print(f"Vetorizacao falhou para '{texto}', ignorando insercao.")

    conn.commit()
    cursor.close()
    conn.close()
    print("Carga concluida com sucesso!")

if __name__ == "__main__":
    main()