FROM python:3

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY mailu ./mailu
COPY migrations ./migrations
COPY manage.py .
COPY start.sh /start.sh

RUN pybabel compile -d mailu/translations

CMD ["/start.sh"]
