FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY consts.py .
COPY gs_init.py .
COPY helpers.py .
COPY logger.py .
COPY spreadsheets.py .
COPY service_account.json .

COPY bot/ ./bot/

CMD ["python", "main.py"]