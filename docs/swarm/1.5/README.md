# Install Mailu master on kubernetes

## Prequisites

### Swarm

You need to have a swarm running

In order to deploy mailu on a swarm, you will first need to initialize it:
The main command will be:
```bash
docker swarm init --advertise-addr <IP_ADDR>
```
See https://docs.docker.com/engine/swarm/swarm-tutorial/create-swarm/

If you want to add other managers or workers, please use:
```bash
docker swarm join --token xxxxx 
```
See https://docs.docker.com/engine/swarm/join-nodes/

You have now a working swarm, and you can check its status with:
```bash
core@coreos-01 ~/git/Mailu/docs/swarm/1.5 $ docker node ls
ID                            HOSTNAME            STATUS              AVAILABILITY        MANAGER STATUS      ENGINE VERSION
xhgeekkrlttpmtgmapt5hyxrb     black-pearl         Ready               Active                                  18.06.0-ce
sczlqjgfhehsfdjhfhhph1nvb *   coreos-01           Ready               Active              Leader              18.03.1-ce
mzrm9nbdggsfz4sgq6dhs5i6n     flying-dutchman     Ready               Active                                  18.06.0-ce
```

### Volume definition
For data persistance (the mailu services might be launched/relaunched on any of the swarm nodes), we need to have mailu data stored in a manner accessible by every manager or worker in the swarm.
Hereafter we will use a NFS share:
```bash
core@coreos-01 ~/git/Mailu/docs $ showmount -e 192.168.0.30
Export list for 192.168.0.30:
/mnt/Pool1/pv            192.168.0.0
```

on the nfs server, I am using the following /etc/exports
```bash
$more /etc/exports
/mnt/Pool1/pv -alldirs -mapall=root -network 192.168.0.0 -mask 255.255.255.0 
```
on the nfs server, I created the mailu directory (in fact I copied a working mailu set-up)
```bash
$mkdir /mnt/Pool1/pv/mailu
```

On your manager node, mount the nfs share to check that the share is available:
```bash
core@coreos-01 ~ $ sudo mount -t nfs 192.168.0.30:/mnt/Pool1/pv/mailu /mnt/local/
```
If this is ok, you can umount it:
```bash
core@coreos-01 ~ $ sudo umount /mnt/local/
```


### Networking mode
On a swarm, the services are available (default mode) through a routing mesh managed by docker itself. With this mode, each service is given a virtual IP adress and docker manages the routing between this virtual IP and the container(s) provinding this service.
With this default networking mode, I cannot get login working properly... As found in https://github.com/Mailu/Mailu/issues/375 ,  a workaround is to use the dnsrr networking mode at least for the front services.

The main consequence/limitation will be that the front services will *not* be available on every node, but only on the node where it will be deployed. In my case, I have only one manager and I choose to deploy the front service to the manager node, so I know on wich IP the front service will be available (aka the IP adress of my manager node).

### Variable substitution 
The docker stack deploy command doesn't support variable substitution in the .yml file itself (vut we still can use .env file to pass variables to the services). As a consequence we need to adjust the docker-compose file to :
- remove all variables : $VERSION , $BIND_ADDRESS4 , $BIND_ADDRESS6 , $ANTIVIRUS , $WEBMAIL , etc
- change the way we define the volumes (nfs share in our case)

### Docker compose 
A working docker-compose.yml file is avalable here:

```yaml

version: '3.2'

services:

  front:
    image: mailu/nginx:1.5
    env_file: .env
    ports:
      - target: 80
        published: 80
        mode: host
      - target: 443
        published: 443
        mode: host
      - target: 110
        published: 110
        mode: host
      - target: 143
        published: 143
        mode: host
      - target: 993
        published: 993
        mode: host
      - target: 995
        published: 995
        mode: host
      - target: 25
        published: 25
        mode: host
      - target: 465
        published: 465
        mode: host
      - target: 587
        published: 587
        mode: host
    volumes:
#      - "/mailu/certs:/certs"
      - type: volume
        source: mailu_certs
        target: /certs
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  redis:
    image: redis:alpine
    restart: always
    volumes:
#      - "/mailu/redis:/data"
      - type: volume
        source: mailu_redis
        target: /data
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  imap:
    image: mailu/dovecot:1.5
    restart: always
    env_file: .env
    volumes:
#      - "$ROOT/data:/data"
      - type: volume
        source: mailu_data
        target: /data
#      - "$ROOT/mail:/mail"
      - type: volume
        source: mailu_mail
        target: /mail
#      - "$ROOT/overrides:/overrides"
      - type: volume
        source: mailu_overrides
        target: /overrides
    depends_on:
      - front
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  smtp:
    image: mailu/postfix:1.5
    restart: always
    env_file: .env
    volumes:
#      - "$ROOT/data:/data"
      - type: volume
        source: mailu_data
        target: /data
#      - "$ROOT/overrides:/overrides"
      - type: volume
        source: mailu_overrides
        target: /overrides
    depends_on:
      - front
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  antispam:
    image: mailu/rspamd:1.5
    restart: always
    env_file: .env
    depends_on:
      - front
    volumes:
#      - "$ROOT/filter:/var/lib/rspamd"
      - type: volume
        source: mailu_filter
        target: /var/lib/rspamd
#      - "$ROOT/dkim:/dkim"
      - type: volume
        source: mailu_dkim
        target: /dkim
#      - "$ROOT/overrides/rspamd:/etc/rspamd/override.d"
      - type: volume
        source: mailu_overrides_rspamd
        target: /etc/rspamd/override.d
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  antivirus:
    image: mailu/none:1.5
    restart: always
    env_file: .env
    volumes:
#      - "/mailu/filter:/data"
      - type: volume
        source: mailu_filter
        target: /data
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  webdav:
    image: mailu/none:1.5
    restart: always
    env_file: .env
    volumes:
#      - /mailu/dav:/data"
      - type: volume
        source: mailu_dav
        target: /data
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  admin:
    image: mailu/admin:1.5
    restart: always
    env_file: .env
    volumes:
#      - "/mailu/data:/data"
      - type: volume
        source: mailu_data
        target: /data
#      - "/mailu/dkim:/dkim"
      - type: volume
        source: mailu_dkim
        target: /dkim
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - redis
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  webmail:
    image: "mailu/roundcube:1.5"
    restart: always
    env_file: .env
    volumes:
#      - "/mailu/webmail:/data"
      - type: volume
        source: mailu_data
        target: /data
    depends_on:
      - imap
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

  fetchmail:
    image: mailu/fetchmail:1.5
    restart: always
    env_file: .env
    volumes:
#      - "/mailu/data:/data"
      - type: volume
        source: mailu_data
        target: /data
    logging:
      driver: none
    deploy:
      endpoint_mode: dnsrr
      replicas: 1
      placement:
        constraints: [node.role == manager]

volumes:
  mailu_filter:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/filter"
  mailu_dkim:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/dkim"
  mailu_overrides_rspamd:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/overrides/rspamd"
  mailu_data:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/data"
  mailu_mail:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/mail"
  mailu_overrides:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/overrides"
  mailu_dav:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/dav"
  mailu_certs:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/certs"
  mailu_redis:
    driver_opts:
      type: "nfs"
      o: "addr=192.168.0.30,nolock,soft,rw"
      device: ":/mnt/Pool1/pv/mailu/redis"
```
