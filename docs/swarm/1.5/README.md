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
Hereafer we will use a NFS share:
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
```bashcore@coreos-01 ~ $ sudo umount /mnt/local/
```


### Networking mode
On a swarm, the services are available (default mode) through a routing mesh managed by docker itself. With this mode, each service is given a virtual IP adress and docker manages the routing between this virtual IP and the container(s) provinding this service.
With this default networking mode, I cannot get login working properly... As found in https://github.com/Mailu/Mailu/issues/375 ,  a workaround is to use the dnsrr networking mode at least for the front services
The main consequence/limiation will be that the front services will *not* be available on every node, but only on the node where it will be deployed. In my case, I have only one manager and I choose to deploy the front service to the manager node, so I know on wich IP the front service will be available (aka the IP adress of my manager node).

### Variable substitution 
The docker stack deploy command doesn't support variable substitution in the .yml file itself (vut we still can use .env file to pass variables to the services). As a consequence we need to adjust the docker-compose file to :
- remove all variables : $VERSION , $BIND_ADDRESS4 , $BIND_ADDRESS6 , $ANTIVIRUS , $WEBMAIL , etc
- change the way we define the volumes (nfs share in our case)

### Docker compose 
A working docker-compose.yml file is avalable here:


