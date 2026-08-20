FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias de sistema para o mysqlclient
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Coleta os arquivos estaticos (nao falha se algo estiver ausente no build)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Aplica migracoes e sobe o Gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
