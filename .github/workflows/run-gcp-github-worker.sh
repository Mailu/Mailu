#!/bin/bash
PROJECT=mailu-arm
USER=mabels
REV=$1
if [ -z "$REV" ]
then
  echo "please set the REV"
  exit 1
fi
ARCH=$2
if [ -z "$ARCH" ]
then
   ARCH=$(uname -m)
fi
INSTANCE_TYPE=$3
AMI=$4
DOCKER_TAG=$5
NECKLESS_URL=$6
GCP_WORKER=gcp.$ARCH.$REV.worker
if [ ! -z "$INSTANCE_TYPE" ]
then
   echo Use $INSTANCE_TYPE - $ARCH
elif [ $ARCH = "x86_64" ]
then
   INSTANCE_TYPE=e2-standard-4
   #[ -z "$AMI" ] && AMI=ami-0d527b8c289b4af7f
   [ -z "$AMI" ] && AMI=$(node .github/workflows/gcp-find-image.js $ARCH)
   [ -z "$DOCKER_TAG" ] && DOCKER_TAG=ghrunner-latest
   [ -z "$NECKLESS_URL" ] && NECKLESS_URL=https://github.com/mabels/neckless/releases/download/v0.1.15/neckless_0.1.15_Linux_x86_64.tar.gz
elif [ $ARCH = "aarch64" ]
then
   INSTANCE_TYPE=t2a-standard-4
   #[ -z "$AMI" ] && AMI=ami-0b168c89474ef4301
   [ -z "$AMI" ] && AMI=$(node .github/workflows/gcp-find-image.js $ARCH)
   [ -z "$DOCKER_TAG" ] && DOCKER_TAG=ghrunner-latest
   [ -z "$NECKLESS_URL" ] && NECKLESS_URL=https://github.com/mabels/neckless/releases/download/v0.1.15/neckless_0.1.15_Linux_arm64.tar.gz
else
   echo "the is no INSTANCE_TYPE known for the arch $ARCH"
   exit 1
fi
if [ -z "$AMI" ]
then
   echo "the is no AMI for $INSTANCE_TYPE known for the arch $ARCH"
   exit 1
fi
if [ -z "$DOCKER_TAG" ]
then
   echo "the is no DOCKER_TAG for $INSTANCE_TYPE known for the arch $ARCH"
   exit 1
fi
if [ -z "$NECKLESS_URL" ]
then
   echo "the is no NECKLESS_URL for $INSTANCE_TYPE known for the arch $ARCH"
   exit 1
fi

#node .github/workflows/gcp-find-image.js $ARCH
#echo $AMI

cat > ./user-data.yaml <<EOF
#cloud-config

users:
- name: cloudservice
  uid: 2000

packages:
  - jq
  - curl
  - docker.io

package_update: true

write_files:
- path: /setup.sh
  permissions: 0755
  owner: root
  content: |
    #!/bin/bash -x
    export HOME=/root

    GITHUB_ACCESS_TOKEN=$GITHUB_ACCESS_TOKEN
    ARCH=$ARCH
    REV=$REV
    USER=$USER
    PROJECT=$PROJECT
    DOCKER_TAG=$DOCKER_TAG

    $(sed 's/^/    /' ./.github/workflows/start-github-worker.sh.template)

runcmd:
- bash -x /setup.sh
EOF

instance=$(echo $PROJECT-$(echo $ARCH | tr -dc '[:alpha:]')-$(echo $REV | fold -w 10 | head -1))
gcloud --quiet compute instances create $instance \
	--project=vibrant-mantis-723 \
	--zone=us-central1-a \
	--machine-type=$INSTANCE_TYPE \
	--network-interface=network-tier=PREMIUM,nic-type=GVNIC,subnet=default \
	--maintenance-policy=MIGRATE \
	--provisioning-model=STANDARD \
	--service-account=307390870127-compute@developer.gserviceaccount.com \
	--scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
	--create-disk=auto-delete=yes,boot=yes,device-name=instance-1,image=$AMI,mode=rw,size=200,type=projects/vibrant-mantis-723/zones/us-central1-a/diskTypes/pd-balanced \
	--no-shielded-secure-boot \
	--shielded-vtpm \
	--shielded-integrity-monitoring \
	--reservation-affinity=any \
	--metadata-from-file user-data=./user-data.yaml

echo "gcloud --quiet compute instances delete $instance --project=vibrant-mantis-723 --zone=us-central1-a" > $GCP_WORKER

