FROM python:3.11-slim

WORKDIR /api

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn","--bind", "0.0.0.0:5000", "main:app", "-c", "gunicorn_config.py"]