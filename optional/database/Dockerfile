#Massively inspired by https://github.com/yobasystems/alpine-mariadb
FROM alpine

RUN apk --update add mariadb mariadb-client pwgen nano curl && \
    rm -f /var/cache/apk/*

ADD run.sh run.sh

RUN chmod +x /run.sh

EXPOSE 3306

ENTRYPOINT ["/run.sh"]