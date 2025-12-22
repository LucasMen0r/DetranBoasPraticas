# syntax=docker/dockerfile:1
# Usando uma versão estável e slim do Python (3.12)
FROM python:3.12-slim as base

# Evita arquivos .pyc e buffer de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema necessárias para o psycopg2 (Postgres)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root (segurança)
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Instala dependências Python
# Dica: Garanta que seu requirements.txt tenha 'psycopg2-binary' e 'ollama'
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY . .

# Ajusta permissões (caso necessário) e troca usuário
RUN chown -R appuser:appuser /app
USER appuser

# Expõe a porta (se for usar API web)
EXPOSE 8000

# Comando padrão
CMD ["python3", "perguntar_ao_manual.py"]
