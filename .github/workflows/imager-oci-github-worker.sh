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
OCI_WORKER=oci.$ARCH.$REV.worker
if [ ! -z "$INSTANCE_TYPE" ]
then
   echo Use $INSTANCE_TYPE - $ARCH
elif [ $ARCH = "x86_64" ]
then
   INSTANCE_TYPE=VM.Standard.E4.Flex
   #[ -z "$AMI" ] && AMI=ami-0d527b8c289b4af7f
   [ -z "$AMI" ] && AMI=$(node .github/workflows/oci-find-image.js $ARCH)
   [ -z "$DOCKER_TAG" ] && DOCKER_TAG=ghrunner-latest
   [ -z "$NECKLESS_URL" ] && NECKLESS_URL=https://github.com/mabels/neckless/releases/download/v0.1.15/neckless_0.1.15_Linux_x86_64.tar.gz
   SHAPE='{"ocpus":4.0,"memoryInGBs":4.0,"baselineOcpuUtilization":"BASELINE_1_8"}'
elif [ $ARCH = "aarch64" ]
then
   INSTANCE_TYPE=VM.Standard.A1.Flex
   #[ -z "$AMI" ] && AMI=ami-0b168c89474ef4301
   [ -z "$AMI" ] && AMI=$(node .github/workflows/oci-find-image.js $ARCH)
   [ -z "$DOCKER_TAG" ] && DOCKER_TAG=ghrunner-latest
   [ -z "$NECKLESS_URL" ] && NECKLESS_URL=https://github.com/mabels/neckless/releases/download/v0.1.15/neckless_0.1.15_Linux_arm64.tar.gz
   SHAPE='{"ocpus":4.0,"memoryInGBs":4.0}'
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

node .github/workflows/oci-find-image.js $ARCH
echo $AMI

cat > ./user-data <<EOF
#!/bin/bash -x
export HOME=/root

ret=1
while [ "\$ret" -ne 0 ]
do
  apt update -y && apt upgrade -y && apt install -y jq curl docker.io
  ret=\$?
  sleep 5
done

GITHUB_ACCESS_TOKEN=$GITHUB_ACCESS_TOKEN
ARCH=$ARCH
REV=$REV
USER=$USER
PROJECT=$PROJECT
DOCKER_TAG=$DOCKER_TAG

$(cat ./.github/workflows/imager.sh.template)
EOF

# $HOME/user-data is a artefact of docker
oci \
--auth api_key \
compute instance launch  \
--availability-domain Rjsp:EU-FRANKFURT-1-AD-2 \
--subnet-id ocid1.subnet.oc1.eu-frankfurt-1.aaaaaaaauzimrxgjorgl27ug3i6hoflyoi4gwlnr7ihiuxgagr4bahmcejyq \
--shape $INSTANCE_TYPE \
--image-id $AMI \
--compartment-id ocid1.tenancy.oc1..aaaaaaaax2n5snd6z7n3ddnnii5x2727bh4zhjzcb7umshzorp4qnp7a2jda \
--shape-config "$SHAPE" \
--assign-public-ip true \
--boot-volume-size-in-gbs 120 \
--user-data-file "$HOME/user-data" \
--is-pv-encryption-in-transit-enabled true \
--metadata "{\"ssh_authorized_keys\": $(curl https://github.com/mabels.keys | jq -Rsa .)}" \
 > $OCI_WORKER 

#aws ec2 run-instances \
#  --image-id $AMI \
#  --instance-type $INSTANCE_TYPE \
#  --user-data file://./user-data \
#  --security-group-ids $(aws ec2 describe-security-groups | jq ".SecurityGroups[] | select(.GroupName==\"${PROJECT}-ec2-github-runner\") .GroupId" -r) \
#  --key-name ${PROJECT}-ec2-github-manager \
#  --associate-public-ip-address \
#  --instance-initiated-shutdown-behavior terminate \
#  --iam-instance-profile Name=${PROJECT}-ec2-github-runner > $OCI_WORKER

