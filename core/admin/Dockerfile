# First stage to build assets
FROM node:8 as assets

COPY package.json ./
RUN npm install

COPY ./webpack.config.js ./
COPY ./assets ./assets
RUN mkdir static \
 && ./node_modules/.bin/webpack-cli


# Actual application
FROM python:3.7

RUN mkdir -p /app
WORKDIR /app

COPY requirements-prod.txt requirements.txt
RUN pip install -r requirements.txt

COPY --from=assets static ./mailu/ui/static
COPY mailu ./mailu
COPY migrations ./migrations
COPY start.py /start.py

RUN pybabel compile -d mailu/translations

EXPOSE 80/tcp
VOLUME ["/data","/dkim"]
ENV FLASK_APP mailu

CMD /start.py

HEALTHCHECK CMD curl -f -L http://localhost/ui/login?next=ui.index || exit 1
