import json
import re
from pathlib import Path
from typing import Dict, Any

def validar_qa(item: Dict[str, Any]) -> bool:
    texto_completo = str(item.get("pergunta", "")) + " " + str(item.get("resposta", ""))
    
    # 1. Bloqueia caracteres especiais em nomes de arquivos/objetos
    if re.search(r'[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]\w*\.scp', texto_completo):
        return False
        
    # 2. Bloqueia contradições diretas de sufixos
    termos_invalidos = [
        "AtualizarDocumentoS", 
        "VeiculoRoubadoAtualizarS",
        "ExcluirMultasI",
        "ValidarRegistroSefazI",
        "tmpParcelaDebitoSefazI"
    ]
    if any(termo in texto_completo for termo in termos_invalidos):
        return False
        
    # 3. Bloqueia alucinações sobre regras de tabelas
    alucinacoes_tabelas = ["MultasA", "VeiculoS"]
    if any(termo in texto_completo for termo in alucinacoes_tabelas):
        return False
        
    # 4. Bloqueia verbos redundantes ou concorrentes no mesmo nome
    verbos_redundantes = ["AtualizarVeiculoRoubadoExcluirE", "VeiculoConsultaInserirA"]
    if any(termo in texto_completo for termo in verbos_redundantes):
        return False

    return True

def processar_arquivos() -> None:
    # Define o diretório base dinamicamente como a pasta onde este script está localizado
    diretorio_base = Path(__file__).resolve().parent
    
    # Busca pelos arquivos JSON na mesma pasta do script
    arquivos_entrada = list(diretorio_base.glob("perguntas_geradas_*.json"))
    
    if not arquivos_entrada:
        print(f"Nenhum arquivo JSON encontrado no diretorio '{diretorio_base}'.")
        return

    total_arquivos = 0
    total_validos = 0
    total_invalidos = 0

    for arquivo in arquivos_entrada:
        # Ignora o arquivo consolidado antigo, caso ele ainda esteja na pasta
        if arquivo.name == "dados_limpos_gandalf.json":
            continue

        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                
            total_arquivos += 1
            
            # Adiciona a flag nos itens lidos
            for item in dados:
                is_valido = validar_qa(item)
                item["valido"] = is_valido
                
                if is_valido:
                    total_validos += 1
                else:
                    total_invalidos += 1
                    
            # Sobrescreve o mesmo arquivo com os dados enriquecidos
            with open(arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=4)
                
        except json.JSONDecodeError:
            print(f"Erro: O arquivo {arquivo.name} possui uma formatação JSON invalida.")
        except Exception as e:
            print(f"Erro ao processar o arquivo {arquivo.name}: {e}")

    print("Processamento de Limpeza concluido.")
    print(f"Arquivos atualizados: {total_arquivos}")
    print(f"Registros classificados como VALIDOS (true): {total_validos}")
    print(f"Registros classificados como INVALIDOS (false): {total_invalidos}")

if __name__ == "__main__":
    processar_arquivos()