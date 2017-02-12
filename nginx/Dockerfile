FROM nginx:alpine

RUN apk add --no-cache nginx-lua openssl

COPY nginx.conf.default /etc/nginx/nginx.conf.default
COPY nginx.conf.fallback /etc/nginx/nginx.conf.fallback

COPY start.sh /start.sh

CMD ["/start.sh"]
