# Используем официальный образ Playwright, где ВСЁ уже установлено
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Указываем рабочую папку
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Открываем порт
EXPOSE 8080

# Запускаем сразу gunicorn (WebKit уже внутри образа!)
CMD ["gunicorn", "-w", "1", "--bind", "0.0.0.0:8080", "app:app"]
