# Install Mailu on a docker swarm

## Some warnings

### How Docker swarm works

Docker swarm enables replication and fail-over scenarios. As a feature, if a node dies or goes away, Docker will re-schedule it's containers on the remaining nodes.
In order to take this decisions, docker swarm works on a consensus between managers regarding the state of nodes. Therefore it recommends to always have an uneven amount of manager nodes. This will always give a majority on either halve of a potential network split.

### Storage

On top of this some of Mailu's containers heavily rely on disk storage. As noted below, every host will need the same dataset on every host where related containers are run. So Dovecot IMAP needs `/mailu/mail` replicated to every node it *may* be scheduled to run. There are various solutions for this like NFS and GlusterFS.

### When disaster strikes

So imagine 3 swarm nodes and 3 GlusterFS endpoints:

```
node-A -> gluster-A --|
node-B -> gluster-B --|--> Single file system
node-C -> gluster-C --|
```

Each node has a connection to the shared file system and maintains connections between the other nodes. Let's say Dovecot is running on `node-A`. Now a network error / outage occurs on the route between `node-A` and the remaining nodes, but stays connected to the `gluster-A` endpoint. `node-B` and `node-C` conclude that `node-A` is down. They reschedule Dovecot to start on either one of them. Dovecot starts reading and writing its indexes to the **shared** filesystem. However, it is possible the Dovecot on `node-A` is still up and handling some client requests. I've seen cases where this situations resulted in:

- Retained locks
- Corrupted indexes
- Users no longer able to read any of mail
- Lost mail

### It gets funkier

Our original deployment also included `main.db` on the GlusterFS. Due to the above we corrupted it once and we decided to move it to local storage and restirct the `admin` container to that host only. This inspired us to put some legwork is supporting different database back-ends like MySQL and PostgreSQL. We highly recommend to use either of them, in favor of sqlite.

### Conclusion

Although the above situation is less-likely to occur on a stable (local) network, it does indicate a failure case where there is a probability of data-loss or downtime. It may help to create redundant networks, but the effort might be too much for the actual results. We will need to look into better and safer methods of replicating mail data. For now, we regret to have to inform you that Docker swarm deployment is **unstable** and should be avoided in production environments.

-- @muhlemmer, 17th of January 2019.

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
In order to allow every (front & webmail) container to access the other services, we will use the variable SUBNET.

Let's create the mailu_default network:
```bash
core@coreos-01 ~ $ docker network create -d overlay --attachable mailu_default
core@coreos-01 ~ $ docker network inspect mailu_default | grep Subnet
                    "Subnet": "10.0.1.0/24",
```
In the docker-compose.yml file, we will then use SUBNET = 10.0.1.0/24 
In fact, imap & smtp logs doesn't show the IPs from the front(s) container(s), but the IP of  "mailu_default-endpoint". So it is sufficient to set SUBNET to this specific ip (which can be found by inspecting mailu_default network). The issue is that this endpoint is created while the stack is created, I did'nt figure a way to determine this IP before the stack creation...

### Limitation with the ingress mode
With the default ingress mode, the front(s) container(s) will see origin IP(s) all being 10.255.0.x (which is the ingress-endpoint, can be found by inspecting the ingress network)

This issue is known and discussed here:

https://github.com/moby/moby/issues/25526

A workaround (using network host mode and global deployment) is discussed here:

https://github.com/moby/moby/issues/25526#issuecomment-336363408 

### Don't create an open relay !
As a side effect of this ingress mode "feature", make sure that the ingress subnet is not in your RELAYHOST, otherwise you would create an smtp open relay :-(

### Ratelimits

When using ingress mode you probably want to disable rate limits, because all requests originate from the same ip address. Otherwise automatic login attempts can easily DoS the legitimate users.

## Scalability
- smtp and imap are scalable
- front and webmail are scalable (pending SUBNET is used), although the let's encrypt magic might not like it (race condidtion ? or risk to be banned by let's encrypt server if too many front containers attemps to renew the certs at the same time) 
- redis, antispam, antivirus, fetchmail, admin, webdav have not been tested (hence replicas=1 in the following docker-compose.yml file)

## Docker secrets
There are DB_PW_FILE and SECRET_KEY_FILE environment variables available to specify files for these variables. These can be used to configure Docker secrets instead of writing the values directly into the `docker-compose.yml` or `mailu.env`.

## Variable substitution and docker-compose.yml
The docker stack deploy command doesn't support variable substitution in the .yml file itself. 
As a consequence, we cannot simply use ``` docker stack deploy -c docker.compose.yml mailu ```
Instead, we will use the following work-around:
``` echo "$(docker-compose -f /mnt/docker/apps/mailu/docker-compose.yml config 2>/dev/null)" | docker stack deploy -c- mailu ```

We need also to:
- add a deploy section for every service
- modify the way the ports are defined for the front service
- add the SUBNET definition for admin (for imap), smtp and antispam services

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
      - SUBNET=10.0.1.0/24
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
      - SUBNET=10.0.1.0/24
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
      - SUBNET=10.0.1.0/24
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

## Notes on unbound resolver

In Docker compose flavor we currently have the option to include the unbound DNS resolver. This does not work in Docker Swarm, as it in not possible to configure any static IP addresses. There is an [open issue](https://github.com/moby/moby/issues/24170) for this at Docker. However, this doesn't seem to move anywhere since some time now. For that reasons we've chosen not to include the unbound resolver in the stack flavor.

If you still want to benefit from Unbound as a system resolver, you can install it system-wide. The following procedure was done on a Fedora 28 system and might needs some adjustments for your system. Note that this will need to be done on every swarm node. In this example we will make use of `dnssec-trigger`, which is used to configure unbound. When installing this and running the service, unbound is pulled in as dependency and does not need to be installed, configured or run separately.

Install required packages(unbound will be installed as dependency):

```
sudo dnf install dnssec-trigger
```

Enable and start the *dnssec-trigger* daemon:

```
sudo systemctl enable --now dnssec-triggerd.service
```

Configure NetworkManager to use unbound, create the file `/etc/NetworkManager/conf.d/unbound.conf` with contents:

```
[main]
dns=unbound
```

You might need to restart NetworkManager for the changes to take effect:

```
sudo systemctl restart NetworkManager
```

Verify `resolv.conf`:

```
$ cat /etc/resolv.conf
# Generated by dnssec-trigger-script
nameserver 127.0.0.1
```

Most of this info was take from this [Fedora Project page](https://fedoraproject.org/wiki/Changes/Default_Local_DNS_Resolver#How_To_Test).
