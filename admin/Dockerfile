FROM python:3

RUN mkdir -p /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Temporarily install certbot from source while waiting for 0.10
RUN git clone https://github.com/certbot/certbot /certbot \
 && cd /certbot \
 && pip install -e ./acme \
 && pip install -e ./

COPY mailu ./mailu
COPY migrations ./migrations
COPY manage.py .
COPY start.sh /start.sh

RUN pybabel compile -d mailu/translations

CMD ["/start.sh"]
