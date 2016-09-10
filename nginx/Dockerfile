FROM nginx:alpine

RUN apk add --update nginx-lua && rm -rf /var/cache/apk/*

COPY nginx.conf /etc/nginx/nginx.conf
