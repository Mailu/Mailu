# Install Mailu on a docker swarm

## Prequisites

### Swarm

In order to deploy Mailu on a swarm, you will first need to initialize the swarm:

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
For data persistance (the Mailu services might be launched/relaunched on any of the swarm nodes), we need to have Mailu data stored in a manner accessible by every manager or worker in the swarm.

Hereafter we will assume that "Mailu Data" is available on every node at "$ROOT" (GlusterFS and nfs shares have been successfully used).

On this example, we are using:
- the mesh routing mode (default mode). With this mode, each service is given a virtual IP adress and docker manages the routing between this virtual IP and the container(s) providing this service. 
- the default ingress mode.

### Allow authentification with the mesh routing
In order to allow every (front & webmail) container to access the other services, we will use the variable POD_ADDRESS_RANGE.

Let's create the mailu_default network:
```bash
core@coreos-01 ~ $ docker network create -d overlay --attachable mailu_default
core@coreos-01 ~ $ docker network inspect mailu_default | grep Subnet
                    "Subnet": "10.0.1.0/24",
```
In the docker-compose.yml file, we will then use POD_ADDRESS_RANGE = 10.0.1.0/24 
In fact, imap & smtp logs doesn't show the IPs from the front(s) container(s), but the IP of  "mailu_default-endpoint". So it is sufficient to set POD_ADDRESS_RANGE to this specific ip (which can be found by inspecting mailu_default network). The issue is that this endpoint is created while the stack is created, I did'nt figure a way to determine this IP before the stack creation...

### Limitation with the ingress mode
With the default ingress mode, the front(s) container(s) will see origin IP(s) all being 10.255.0.x (which is the ingress-endpoint, can be found by inspecting the ingress network)

This issue is known and discussed here:

https://github.com/moby/moby/issues/25526

A workaround (using network host mode and global deployment) is discussed here:

https://github.com/moby/moby/issues/25526#issuecomment-336363408 

### Don't create an open relay !
As a side effect of this ingress mode "feature", make sure that the ingress subnet is not in your RELAYHOST, otherwise you would create an smtp open relay :-(


## Scalability
- smtp and imap are scalable
- front and webmail are scalable (pending POD_ADDRESS_RANGE is used), although the let's encrypt magic might not like it (race condidtion ? or risk to be banned by let's encrypt server if too many front containers attemps to renew the certs at the same time) 
- redis, antispam, antivirus, fetchmail, admin, webdav have not been tested (hence replicas=1 in the following docker-compose.yml file)

## Variable substitution and docker-compose.yml
The docker stack deploy command doesn't support variable substitution in the .yml file itself. 
As a consequence, we cannot simply use ``` docker stack deploy -c docker.compose.yml mailu ```
Instead, we will use the following work-around:
``` echo "$(docker-compose -f /mnt/docker/apps/mailu/docker-compose.yml config 2>/dev/null)" | docker stack deploy -c- mailu ```

We need also to:
- add a deploy section for every service
- modify the way the ports are defined for the front service
- add the POD_ADDRESS_RANGE definition for admin (for imap), smtp and antispam services

## Docker compose 
An example of docker-compose-stack.yml file is available here:

```yaml

version: '3.2'

services:

  front:
    image: mailu/nginx:$VERSION
    restart: always
    env_file: .env
    ports:
      - target: 80
        published: 80
      - target: 443
        published: 443
      - target: 110
        published: 110
      - target: 143
        published: 143
      - target: 993
        published: 993
      - target: 995
        published: 995
      - target: 25
        published: 25
      - target: 465
        published: 465
      - target: 587
        published: 587
    volumes:
      - "$ROOT/certs:/certs"
    deploy:
      replicas: 2

  redis:
    image: redis:alpine
    restart: always
    volumes:
      - "$ROOT/redis:/data"
    deploy:
      replicas: 1

  imap:
    image: mailu/dovecot:$VERSION
    restart: always
    env_file: .env
    volumes:
      - "$ROOT/mail:/mail"
      - "$ROOT/overrides:/overrides"
    depends_on:
      - front
    deploy:
      replicas: 2

  smtp:
    image: mailu/postfix:$VERSION
    restart: always
    env_file: .env
    environment:
      - POD_ADDRESS_RANGE=10.0.1.0/24
    volumes:
      - "$ROOT/overrides:/overrides"
    depends_on:
      - front
    deploy:
      replicas: 2

  antispam:
    image: mailu/rspamd:$VERSION
    restart: always
    env_file: .env
    environment:
      - POD_ADDRESS_RANGE=10.0.1.0/24
    volumes:
      - "$ROOT/filter:/var/lib/rspamd"
      - "$ROOT/dkim:/dkim"
      - "$ROOT/overrides/rspamd:/etc/rspamd/override.d"
    depends_on:
      - front
    deploy:
      replicas: 1

  antivirus:
    image: mailu/none:$VERSION
    restart: always
    env_file: .env
    volumes:
      - "$ROOT/filter:/data"
    deploy:
      replicas: 1

  webdav:
    image: mailu/none:$VERSION
    restart: always
    env_file: .env
    volumes:
      - "$ROOT/dav:/data"
    deploy:
      replicas: 1

  admin:
    image: mailu/admin:$VERSION
    restart: always
    env_file: .env
    environment:
      - POD_ADDRESS_RANGE=10.0.1.0/24
    volumes:
      - "$ROOT/data:/data"
      - "$ROOT/dkim:/dkim"
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - redis
    deploy:
      replicas: 1

  webmail:
    image: mailu/roundcube:$VERSION
    restart: always
    env_file: .env
    volumes:
      - "$ROOT/webmail:/data"
    depends_on:
      - imap
    deploy:
      replicas: 2

  fetchmail:
    image: mailu/fetchmail:$VERSION
    restart: always
    env_file: .env
    volumes:
    deploy:
      replicas: 1

networks:
  default:
    external:
      name: mailu_default
```

## Deploy Mailu on the docker swarm
Run the following command:
```bash
echo "$(docker-compose -f /mnt/docker/apps/mailu/docker-compose.yml config 2>/dev/null)" | docker stack deploy -c- mailu
```
See how the services are being deployed:
```bash
core@coreos-01 ~ $ docker service ls
ID                  NAME                                 MODE                REPLICAS            IMAGE                                     PORTS
ywnsetmtkb1l        mailu_antivirus                      replicated          1/1                 mailu/none:master
pqokiaz0q128        mailu_fetchmail                      replicated          1/1                 mailu/fetchmail:master
```
check a specific service:
```bash
core@coreos-01 ~ $ docker service ps mailu_fetchmail
ID                  NAME                IMAGE                 NODE                DESIRED STATE       CURRENT STATE         ERROR               PORTS
tbu8ppgsdffj        mailu_fetchmail.1   mailu/fetchmail:master   coreos-01           Running             Running 11 days ago
```
You might also have a look on the logs:
```bash
core@coreos-01 ~ $ docker service logs -f mailu_fetchmail
```

## Remove the stack
Run the follwoing command:
```bash
core@coreos-01 ~ $ docker stack rm mailu
```
