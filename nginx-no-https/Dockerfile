FROM nginx:alpine

RUN apk add --no-cache nginx-lua openssl

COPY nginx.conf.default /etc/nginx/nginx.conf.default

COPY start.sh /start.sh

CMD ["/start.sh"]
