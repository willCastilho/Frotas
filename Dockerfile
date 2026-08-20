FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# psycopg2-binary ja vem compilado; libpq garante o cliente do PostgreSQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Coleta os arquivos estaticos (nao falha se algo estiver ausente no build)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Sobe via script de inicializacao: migracoes + grupos/admin (nao bloqueantes)
# + gunicorn na porta definida pela plataforma (Railway injeta PORT).
CMD ["sh", "scripts/start.sh"]
