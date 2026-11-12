# IndustrialTelemetry.Middleware chay trong Docker (build context = ./IndustrialTelemetry.Middleware).
# Code middleware giu nguyen; cau hinh truyen qua bien moi truong (settings.py doc os.environ).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
