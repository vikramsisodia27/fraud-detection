FROM python:3.11-slim

WORKDIR /app

# Install core dependencies (scikit-learn, pandas, etc.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# # COMMENTED OUT: FinBERT + PyTorch (not currently in use)
# # Install PyTorch (CPU-only) + transformers for FinBERT
# RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# RUN pip install --no-cache-dir transformers
#
# # Pre-cache ProsusAI/finbert model at build time
# RUN python -c "\
# from transformers import pipeline; \
# pipe = pipeline('text-classification', model='ProsusAI/finbert', top_k=None); \
# result = pipe('Pre-cache test', truncation=True, max_length=512); \
# print('FinBERT pre-cached OK:', result)"

COPY fraud-ml-api/ .

EXPOSE 3000

CMD ["bentoml", "serve", "app.service:FraudDetectionService", "--port", "3000"]