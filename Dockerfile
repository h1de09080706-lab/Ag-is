FROM python:3.11-slim

# Installer ffmpeg (indispensable pour la musique)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD ["python", "bot.py"]
