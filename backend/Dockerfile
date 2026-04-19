FROM python:3.11-slim

WORKDIR /app

# System deps for Prophet / LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-generate mock data at build time
RUN python -c "from data.generate_mock_data import generate_all; generate_all()"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
