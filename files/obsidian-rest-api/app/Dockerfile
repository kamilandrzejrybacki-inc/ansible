FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/* \
 && openssl req -x509 -newkey rsa:2048 -keyout /app/tls.key -out /app/tls.crt -days 3650 -nodes \
      -subj "/CN=obsidian-rest-api"

ENV VAULT_ROOT=/vault
ENV API_KEY=""

EXPOSE 27124

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "27124", "--ssl-keyfile", "/app/tls.key", "--ssl-certfile", "/app/tls.crt"]
