import asyncio
from typing import List
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector

async def buscar_regras_relevantes(
    pool: AsyncConnectionPool, 
    pergunta_usuario: str, 
    limite: int = 15, 
    limiar_similaridade: float = 0.35
) -> List[str]:
    """
    Busca as regras mais similares à pergunta do usuário usando pgvector.
    
    Ajustes arquiteturais:
    - limite (Top-K) aumentado para 15 para acomodar regras atomizadas.
    - limiar_similaridade (Threshold) garante que apenas regras com pontuação
      mínima aceitável sejam retornadas, evitando ruído no LLM.
    """
    
    # 1. Gera o embedding da pergunta paralelamente
    vetor_pergunta = await asyncio.to_thread(get_embedding_local, pergunta_usuario)
    
    # 2. Query otimizada com cálculo de score como filtro (Threshold)
    query = """
        WITH CalculoSimilaridade AS (
            SELECT 
                c.NomeCategoria,
                o.NomeObjeto,
                r.descricaoregra,
                1 - (r.embedding <=> %s::vector) AS score
            FROM RegraNomenclatura r
            LEFT JOIN CategoriaRegra c ON r.pkCategoriaRegra = c.pkCategoriaRegra
            LEFT JOIN ObjetoDb o ON r.pkObjetoDb = o.pkObjetoDb
            WHERE r.embedding IS NOT NULL
        )
        SELECT NomeCategoria, NomeObjeto, descricaoregra, score
        FROM CalculoSimilaridade
        WHERE score >= %s
        ORDER BY score DESC
        LIMIT %s;
    """
    
    resultados_formatados = []
    
    async with pool.connection() as conn:
        await register_vector(conn)
        async with conn.cursor() as cur:
            # Passamos o vetor, o limiar de corte e o limite máximo
            await cur.execute(query, (vetor_pergunta, limiar_similaridade, limite))
            resultados = await cur.fetchall()
            
            for cat, obj, desc, score in resultados:
                contexto_objeto = f"Objeto: {obj}" if obj else "Regra Geral"
                texto_rag = f"[{cat}] {contexto_objeto} - {desc} (Score: {score:.2f})"
                resultados_formatados.append(texto_rag)
                
    return resultados_formatados
