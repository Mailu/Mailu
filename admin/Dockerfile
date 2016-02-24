FROM python:3

RUN mkdir -p /app
WORKDIR /app

COPY freeposte ./freeposte
COPY initdb.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

CMD gunicorn -w 4 -b 0.0.0.0:80 --access-logfile - --error-logfile - freeposte:app
