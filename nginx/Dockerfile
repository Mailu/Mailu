FROM nginx:alpine

RUN apk add --update nginx-lua && rm -rf /var/cache/apk/*

COPY nginx.conf /etc/nginx/nginx.conf
COPY nginx.conf.fallback /etc/nginx/nginx.conf.fallback

COPY start.sh /start.sh

CMD ["/start.sh"]
