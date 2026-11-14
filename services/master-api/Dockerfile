FROM python:3.12-slim

# app.py tinh ROOT = parents[2] (= goc repo) va doc ROOT/config/master_data.json.
# Dat app o /srv/services/master-api de ROOT = /srv; mount ./config -> /srv/config.
# (Dat o /app/app.py se crash: Path('/app/app.py').parents[2] -> IndexError.)
WORKDIR /srv/services/master-api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
