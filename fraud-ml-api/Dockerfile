FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fraud-ml-api/ .

EXPOSE 3000

CMD ["bentoml", "serve", "app.service:FraudDetectionService", "--port", "3000"]