FROM python:3.9-slim

WORKDIR /app

# Установка Node.js и npm
RUN apt-get update && apt-get install -y \
    gcc g++ build-essential \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# TypeScript сборка
COPY package*.json ./
RUN npm install

COPY app/static/js/src/ ./app/static/js/src/
COPY tsconfig.json ./
RUN npx tsc

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
