import psycopg2
import requests
import pgvector.psycopg2

db_params = {
    "dbname": "DetranNorma",
    "user": "postgres",
    "password": "123456",
    "host": "localhost",
    "port": "5432"
}

def getembedding(text):
    url = "http://localhost:11434/api/embeddings"
    try:
        resp = requests.post(url, json={"model": "nomic-embed-text:latest", "prompt": text})
        return resp.json()['embedding']
    except Exception as e:
        print(f"Erro ao vetorizar: {e}")
        return None
    
def inserrirexemplo(conn, foco, texto, is_bom, explicacao):
    vec = getembedding(f"{foco} : {texto}")
    cursor = conn.cursor()
    cursor.execute("""
        insert into exemplos_praticos (objeto_foco, exemplo_texto, is_bom_exemplo, explicacao, embedding)
        values (%s, %s, %s, %s, %s)
    """, (foco, texto, is_bom, explicacao, vec))
    conn.commit()

    if is_bom:
        status = True
    else:
        status = False
    print(f"Exemplo inserido com sucesso: {status} -> {texto}")

exemplos = [
    
    #PROCEDURES
    ("Procedure", "BatchConsumoServicoWebS", True, "Usar sigla, em letra maiúscula, das operações básicas: Selecionar (S),Inserir (I), Excluir (E), Alterar (A), Relatório (R); Quando a procedure for executada via processamento batch, deve-se colocar no início do nome da procedure a palavra “Batch”."),
    ("Procedure", "BatchConsumoServicoWebA", True, "Usar sigla, em letra maiúscula, das operações básicas: Selecionar (S),Inserir (I), Excluir (E), Alterar (A), Relatório (R); Quando a procedure for executada via processamento batch, deve-se colocar no início do nome da procedure a palavra “Batch”."),
    ("Procedure", "BatchConsumoServicoWebMover", True, "Usar sigla, em letra maiúscula, das operações básicas: Selecionar (S),Inserir (I), Excluir (E), Alterar (A), Relatório (R); Quando a procedure for executada via processamento batch, deve-se colocar no início do nome da procedure a palavra “Batch”."),  
    ("Procedure", "dbvcen..ProcEletronicoTransacaoListarS.scp", True, "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos."),
    ("Procedure", "VeiculoRoubadoPopularSds.sco", True, "Inicia com verbo/ação, notação húngara."),
    ("Procedure", "dbinfracao..ConsultaCancelamentoOrgaoS.scp", True, "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos."), 
    ("Procedure", "dbinfracao..SitInfracaoE.scp", True, "o Manual pede objetivo[complemento]operacao e se as operações não for de  S, I, E, A, R o verbo deve estar no infinitivo"),
    ("Procedure", "dbinfracao..SitInfracaoI.scp", True, "o Manual pede objetivo[complemento]operacao e se as operações não for de  S, I, E, A, R o verbo deve estar no infinitivo"),
    ("Procedure", "dbinfracao..SitInfracaoS.scp", True, "o Manual pede objetivo[complemento]operacao e se as operações não for de  S, I, E, A, R o verbo deve estar no infinitivo"),
    ("Procedure", "dbinfracao..SitInfracaoA.scp", True, "o Manual pede objetivo[complemento]operacao e se as operações não for de  S, I, E, A, R o verbo deve estar no infinitivo"),
    ("Procedure", "VerificaAdvertenciaS.scp", True, "Inicia com verbo/ação, notação húngara."),   
    ("Procedure", "dbvcen..ProcEletronicoTransacaoListarS.scp", True, "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos."),    
    ("Procedure", "dbvcen.dbo.ProcessoEletroAberturaAnalisar ", True, "No sistema de Veículos, os nomes das procedures RENAVAM e RENAINF ficarão iguais aos já existentes. Se for no banco RENAVAM todos os padrões serão mantidos, mas se for em outro banco, só se houver algum termo que indique que a procedure faz parte de um desses projetos."),      
    ("Procedure", "Operacao..VeiculoRoubadoAtualizarSds.scp", False, "De acordo com o manual: Nome de procedure: Objetivo[Complemento]Operacao."),
    ("Procedure", "PopulaVeiculoRoubadoSDS", False, "o Manual pede objetivo[complemento]operacao e se as operações não for de  S, I, E, A, R o verbo deve estar no infinitivo"),
    ("Procedure", "Operacao..VeiculoRoubadoPopularSDS.sco", False, "o Manual pede objetivo[complemento]operacao e se as operações não for de  S, I, E, A, R o verbo deve estar no infinitivo"),
        
]

try:
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    cursor.execute("TRUNCATE TABLE exemplos_praticos RESTART IDENTITY;")
    conn.commit()
    
    print("Iniciando carga de exemplos.")
    for item in exemplos:
        inserrirexemplo(conn, item[0], item[1], item[2], item[3])

    conn.close()
    print("\nSucesso! Tabela de exemplos populada.")
except Exception as e:
    print(f"Erro: {e}")
