FROM python:3

RUN mkdir -p /app
WORKDIR /app

COPY mailu ./mailu
COPY migrations ./migrations
COPY manage.py .
COPY requirements.txt .
COPY start.sh /start.sh

RUN pip install -r requirements.txt
RUN pybabel compile -d mailu/translations

CMD ["/start.sh"]
