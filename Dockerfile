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

# Aplica migracoes e sobe o Gunicorn na porta definida pela plataforma
# (Railway injeta a variavel PORT; localmente cai para 8000).
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py criar_grupos && python manage.py criar_admin && gunicorn project.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3"]
