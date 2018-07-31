# Install Mailu master on kubernetes

## Prequisites

### Structure

There's chosen to have a double NGINX stack for Mailu, this way the main ingress can still be used to access other websites/domains on your cluster. This is the current structure:

- `NGINX Ingress controller`: Listens to the nodes ports 80 & 443 and directly forwards all TCP traffic on the E-amail ports (993,143,25,587,...). This is because this `DaemonSet` already consumes ports 80 & 443 and uses `hostNetwork: true`
- `Cert manager`: Creates automatic Lets Encrypt certificates based on an `Ingress`-objects domain name.
- `Mailu NGINX Front container`: This container receives all the mail traffic forwarded from the ingress controller. The web traffic is also forwarded based on an ingress
- `Mailu components`: All Mailu components are split into separate files to make them more 

### What you need
- A working Kubernetes cluster (tested with 1.10.5)
- A working [cert-manager](https://github.com/jetstack/cert-manager) installation
- A working nginx-ingress controller needed for the lets-encrypt certificates. You can find those files in the `nginx` subfolder

#### Cert manager

The `Cert-manager` is quite easy to deploy using Helm when reading the [docs](https://cert-manager.readthedocs.io/en/latest/getting-started/2-installing.html). 
After booting the `Cert-manager` you'll need a `ClusterIssuer` which takes care of all required certificates through `Ingress` items. An example:

```yaml
apiVersion: certmanager.k8s.io/v1alpha1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    email: something@example.com
    http01: {}
    privateKeySecretRef:
      key: ""
      name: letsencrypt-stage
    server: https://acme-v02.api.letsencrypt.org/directory
```

### Things to change
- All services run in the same namespace, currently `mailu-mailserver`. So if you want to use a different one, change the `namespace` value in **every** file
- Check the `storage-class` field in the `pvc.yaml` file, you can also change the sizes to your liking. Note that you need `RWX` (read-write-many) and `RWO` (read-write-once) storageclasses.
- Check the `configmap.yaml` and adapt it to your needs. Be sure to check the kubernetes DNS values at the end (if you use a different namespace)
- Check the `ingress-ssl.yaml` and change it to the domain you want (this is for the kubernetes ingress controller, it will forward to `mailu/nginx` a.k.a. the `front` pod)

## Installation
First run the command to start Mailu:

```bash
kubectl create -f rbac.yaml
kubectl create -f configmap.yaml
kubectl create -f pvc.yaml
kubectl create -f ingress-ssl.yaml
kubectl create -f redis.yaml
kubectl create -f front.yaml
kubectl create -f webmail.yaml
kubectl create -f imap.yaml
kubectl create -f security.yaml
kubectl create -f smtp.yaml
kubectl create -f fetchmail.yaml
kubectl create -f admin.yaml
kubectl create -f webdav.yaml
```

## Create the first admin account

When the cluster is online you need to create you master user to access `https://mail.example.com/admin`.
Enter the main `admin` pod to create the root account:

```bash
kubectl -n mailu-mailserver get po
kubectl -n mailu-mailserver exec -it mailu-admin-.... /bin/sh
```

And in the pod run the following command. The command uses following entries:
- `admin` Make it an admin user
- `root` The first part of the e-mail adres (ROOT@example.com)
- `example.com` the domain appendix
- `password` the chosen password for the user

```bash
python manage.py admin root example.com password
```

Now you should be able to login on the mail account: `https://mail.example.com/admin`

## Adaptations

I noticed you need an override for the `postfix` server in order to be able to send mail. I noticed Google wasn't able to deliver mail to my account and it had to do with the `smtpd_authorized_xclient_hosts` value in the config file. The config can be read [here](https://github.com/hacor/Mailu/blob/master/core/postfix/conf/main.cf#L35) and is pointing to a single IP of the service. But the requests come from the host IPs (the NGINX Ingress proxy) and they don't use the service specific IP.

Enter the `postfix` pod:

```bash
kubectl -n mailu-mailserver get po
kubectl -n mailu-mailserver exec -it mailu-smtp-.... /bin/sh
```

Now you're in the pod, create an override file like so:

```bash
vi /overrides/postfix.cf
```

And give it the following contents, off course replacing `10.2.0.0/16` with the CIDR of your pod range. This way the NGINX pods can also restart and your mail server will still operate

```bash
not_needed = true
smtpd_authorized_xclient_hosts = 10.2.0.0/16
```

The first line seems stupid, but is needed because its pasted after a #, so from the second line we're really in action.
Save and close the file and exit. Now you need to delete the pod in order to recreate the config file.

```bash
kubectl -n mailu-mailserver delete po/mailu-smtp-....
```

Wait for the pod to recreate and you're online!
Happy mailing!