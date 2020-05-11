#!/bin/bash
# ------------------------------------------------------------------
# [Kosalag] Mailu installer
#          This script deploys mailu server into a k8s cluster
# ------------------------------------------------------------------

VERSION=0.1.0
SUBJECT="Deployment Script for Mailu"

USAGE () {
    echo  " Installation Guide:

Run this script without argumants.
./install.sh


During Installation, You will be ask for
  -d -  Domain Name - Full Qualified Domain Name of youe mail server
  -a -  Admin User Name - Username of your intial administrator
  -i -  Pod IP Range - If you are using nginx ingress provide your Pod IP Range  ex- 10.4.0.0/14
  -p -  Admin User Password
  -h, 
  
  Display this help and exit"
}

INPUT_ERROR(){
echo $1;
echo "Exiting...";
exit 0;
}

GET_VALUES(){

  echo -n "Enter Full Qualified Domain Name: "
  read HOST_NAME

  echo -n "Enter Admin User's User Name: "
  read ADMIN_USER

  echo -n "Enter POD IP Range  ex- 10.4.0.0/14: "
  read POD_IP

  echo -n "Enter Admin User Password: "
  read -s ADMIN_PWD
}

WAIT_TILL_RUNNING(){
  POD_STATUS=$(kubectl get po $1 -o custom-columns=STAT:.status.phase --no-headers)

  while (( $POD_STATUS != 'Running' ))
  do
    echo "wait 5 for $1 pod to start";
    sleep 5
    POD_STATUS=$(kubectl get po $1 -o custom-columns=STAT:.status.phase --no-headers)
  done
}

# --- Options processing -------------------------------------------
if [ $# == 0 ] ; then
    USAGE
    echo -n "Do you want to continue and enter details later? (yes/no) :"
    read CONTINUE
    if [ "$CONTINUE" == "yes" ]; then GET_VALUES ; else exit 0; fi
fi

while getopts ":d:a:i:p:vh" optname
  do
    case "$optname" in
      "v")
        echo "Version $VERSION"
        exit 0;
        ;;
      "d")
        HOST_NAME=$OPTARG
        ;;
      "a")
        ADMIN_USER=$OPTARG
        ;;
      "i")
        POD_IP=$OPTARG
        ;;
      "p")
        ADMIN_PWD=$OPTARG
        ;;
      "h")
        USAGE
        exit 0;
        ;;
      "?")
        echo "Unknown option $OPTARG"
        USAGE
        exit 0;
        ;;
      ":")
        echo "No argument value for option $OPTARG"
        exit 0;
        ;;
      *)
        echo "Unknown error while processing options"
        exit 0;
        ;;
    esac
  done

shift $(($OPTIND - 1))

param1=$1
param2=$2

# --- Locks -------------------------------------------------------
LOCK_FILE=/tmp/$SUBJECT.lock
if [ -f "$LOCK_FILE" ]; then
   echo "Script is already running"
   exit
fi

trap "rm -f $LOCK_FILE" EXIT
touch $LOCK_FILE

# --- Body --------------------------------------------------------


DOMAIN=${HOST_NAME#*.*} #Get Domain from the given hostname

echo "FQDN is - $HOST_NAME"
echo $DOMAIN
echo $ADMIN_USER

echo "******** Writing Config Changes ********"

# Write configurations to configmap.yaml and ingress.yaml

sed -i "s/mail.example.com/$HOST_NAME/g" ingress.yaml

sed -i "s/mail.example.com/$HOST_NAME/g" configmap.yaml
sed -i "s/example.com/$DOMAIN/g" configmap.yaml

sed -i "s/INITIAL/#INITIAL/g" configmap.yaml # Comment out if already set
sed -i "s/POD_ADDRESS_RANGE/#POD_ADDRESS_RANGE/g" configmap.yaml # Comment out if already set

if [ -z "$HOST_NAME" ]; then INPUT_ERROR "Domain Name Not Set!"; else echo "FQDN is - $HOST_NAME"; fi
if [ -z "$ADMIN_USER" ]; then INPUT_ERROR "Admin User  Not Set!"; else echo "Admin User is - $ADMIN_USER"; fi
if [ -z "$ADMIN_PWD" ]; then INPUT_ERROR "Admin Password  Not Set!"; else echo "Admin Password is set"; fi
if [ -z "$POD_IP" ]; then INPUT_ERROR "Pod IP Range  Not Set!"; else echo "Pod IP Range is - $POD_IP"; fi

cat <<EOT >> configmap.yaml

    POD_ADDRESS_RANGE: "${POD_IP}"
    # INITIAL_ADMIN_ACCOUNT: "${ADMIN_USER}"
    # INITIAL_ADMIN_HOST_NAME: "${HOST_NAME}"
    # INITIAL_ADMIN_PW: "${ADMIN_PWD}"

EOT

echo "******** Writing Config Changes Success ********"


kubectl apply -f rbac.yaml
kubectl apply -f configmap.yaml
kubectl apply -f pvc.yaml && sleep 10
kubectl apply -f redis.yaml && sleep 10
kubectl apply -f front.yaml && sleep 10
kubectl apply -f webmail.yaml && sleep 10
kubectl apply -f imap.yaml && sleep 10
kubectl apply -f security.yaml && sleep 10
kubectl apply -f smtp.yaml && sleep 10
kubectl apply -f fetchmail.yaml && sleep 10
kubectl apply -f admin.yaml && sleep 10
kubectl apply -f webdav.yaml && sleep 10
kubectl apply -f ingress.yaml && sleep 30


# Get IMAP Pod Name
IMAP_POD=$(kubectl get po -l app=mailu-imap -o custom-columns=NAME:.metadata.name --no-headers -n mailu-mailserver)
echo "IMAP POD NAME - " $IMAP_POD

WAIT_TILL_RUNNING $IMAP_POD # Wait till the pod start

kubectl cp dovecot.conf $IMAP_POD:/overrides/dovecot.conf -n mailu-mailserver
kubectl delete po $IMAP_POD -n mailu-mailserver && sleep 30

# Create Admin User
ADMIN_POD=$(kubectl get po -l app=mailu-admin -o custom-columns=NAME:.metadata.name --no-headers -n mailu-mailserver)
echo "ADMIN POD NAME - " $ADMIN_POD

WAIT_TILL_RUNNING $ADMIN_POD # Wait till the pod start

kubectl exec -it $ADMIN_POD -- flask mailu admin $ADMIN_USER $HOST_NAME "$ADMIN_PWD"


echo ""
echo ""
kubectl get po -n mailu-mailserver
echo ""
echo ""
echo "Setup finished. When all the pods are running, visit https://$HOST_NAME/admin"
echo "Admin Email is - $ADMIN_USER@$HOST_NAME"
echo "Happy Mailing..."

# -----------------------------------------------------------------