FROM alpine:3.8

RUN apk add --no-cache unbound curl \
	&& curl -o /etc/unbound/root.hints https://www.internic.net/domain/named.cache \
	&& chown root:unbound /etc/unbound \
	&& chmod 775 /etc/unbound \
	&& apk del --no-cache curl \
	&& /usr/sbin/unbound-anchor -a /etc/unbound/trusted-key.key | true

COPY unbound.conf /etc/unbound/unbound.conf

EXPOSE 53/udp 53/tcp

CMD /usr/sbin/unbound
