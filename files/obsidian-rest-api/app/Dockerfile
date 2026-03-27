FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV VAULT_ROOT=/vault
ENV API_KEY=""

EXPOSE 27124

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "27124"]
