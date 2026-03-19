FROM python:3.12-slim

WORKDIR /app

COPY stock_analysis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stock_analysis/ .

EXPOSE 5000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4"]
