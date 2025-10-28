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

# Копируем файлы зависимостей
COPY requirements.txt package*.json ./
RUN pip install --no-cache-dir -r requirements.txt
RUN npm install
RUN npm install -g typescript

# Копируем исходники для TypeScript
COPY app/static/js/src/ ./app/static/js/src/
COPY tsconfig.json ./

# Создаем директорию dist и компилируем TypeScript
RUN mkdir -p app/static/js/dist && tsc

# Копируем остальные файлы
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
