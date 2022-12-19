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
EC2_WORKER=ec2.$ARCH.$REV.worker
if [ ! -z "$INSTANCE_TYPE" ]
then
   echo Use $INSTANCE_TYPE - $ARCH
elif [ $ARCH = "x86_64" ]
then
   INSTANCE_TYPE=m5ad.large 
   #[ -z "$AMI" ] && AMI=ami-0d527b8c289b4af7f
   [ -z "$AMI" ] && AMI=ami-015c25ad8763b2f11
   [ -z "$DOCKER_TAG" ] && DOCKER_TAG=ghrunner-latest
   [ -z "$NECKLESS_URL" ] && NECKLESS_URL=https://github.com/mabels/neckless/releases/download/v0.1.12/neckless_0.1.12_Linux_x86_64.tar.gz
elif [ $ARCH = "aarch64" ]
then
   INSTANCE_TYPE=m6gd.large
   #[ -z "$AMI" ] && AMI=ami-0b168c89474ef4301
   [ -z "$AMI" ] && AMI=ami-0641bed8c0ce71686
   [ -z "$DOCKER_TAG" ] && DOCKER_TAG=ghrunner-latest
   [ -z "$NECKLESS_URL" ] && NECKLESS_URL=https://github.com/mabels/neckless/releases/download/v0.1.12/neckless_0.1.12_Linux_arm64.tar.gz
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


cat > user-data <<EOF
#!/bin/bash -x
export HOME=/root

mkfs.ext4 /dev/nvme1n1
mount /dev/nvme1n1 /mnt

mkdir -p /mnt/snap /var/snap
mkdir -p /mnt/docker /var/lib/docker

mv /var/snap /var/snap-off
mkdir -p /var/snap
mount --bind /mnt/snap /var/snap
rsync -vaxH /var/snap-off/ /var/snap/

mv /var/lib/docker /var/lib/docker-off
mkdir -p /var/lib/docker
mount --bind /mnt/docker /var/lib/docker
rsync -vaxH /var/lib/docker-off/ /var/lib/docker/

apt update -y
apt upgrade -y
apt install -y awscli jq curl docker.io
aws sts get-caller-identity
curl -L -o /tmp/neckless.tar.gz $NECKLESS_URL
(cd /tmp && tar xvzf neckless.tar.gz)
cp /tmp/neckless /usr/bin
curl -L -o .neckless https://raw.githubusercontent.com/${USER}/${PROJECT}/main/.neckless
eval \$(NECKLESS_PRIVKEY=\$(aws --region eu-central-1 secretsmanager get-secret-value \
  --secret-id arn:aws:secretsmanager:eu-central-1:973800055156:secret:${PROJECT}/neckless \
  --query SecretString --output text | jq -r ".\"${PROJECT}\"") neckless kv ls GITHUB_ACCESS_TOKEN)

GITHUB_ACCESS_TOKEN=\$GITHUB_ACCESS_TOKEN
ARCH=$ARCH
REV=$REV
USER=$USER
PROJECT=$PROJECT
DOCKER_TAG=$DOCKER_TAG

$(cat ./.github/workflows/start-github-worker.sh.template)
EOF

cat > spot.json <<EOF
{
    "MarketType": "spot",
    "SpotOptions": {
      "MaxPrice": "string",
      "SpotInstanceType": "one-time"|"persistent",
      "BlockDurationMinutes": integer,
      "ValidUntil": timestamp,
      "InstanceInterruptionBehavior": "hibernate"|"stop"|"terminate"
    }
}
EOF

cat > spot-config.json <<EOF
{
    "IamFleetRole": "arn:aws:iam::973800055156:role/aws-ec2-spot-fleet-tagging-role",
    "AllocationStrategy": "lowestPrice",
    "TargetCapacity": 1,
    "ValidFrom": "2022-05-19T20:13:15.000Z",
    "ValidUntil": "2023-05-19T20:23:00.000Z",
    "TerminateInstancesWithExpiration": true,
    "Type": "maintain",
    "TargetCapacityUnitType": "units",
    "SpotPrice": "40.9447",
    "LaunchSpecifications": [
        {
            "ImageId": "ami-015c25ad8763b2f11",
            "KeyName": "krypton-oneplus",
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "DeleteOnTermination": true,
                        "SnapshotId": "snap-0bda75060a0810cac",
                        "VolumeSize": 8,
                        "VolumeType": "gp2",
                        "Encrypted": true
                    }
                }
            ],
            "SubnetId": "subnet-ea761282, subnet-b26bc5c8, subnet-29516963",
            "InstanceRequirements": {
                "VCpuCount": {
                    "Min": 4
                },
                "MemoryMiB": {
                    "Min": 8192
                },
                "LocalStorage": "required",
                "TotalLocalStorageGB": {
                    "Min": 100
                },
                "LocalStorageTypes": [
                    "ssd"
                ]
            }
        }
    ]
}
EOF

cat > spot-options.json <<EOF
{
  "MarketType": "spot",
  "SpotOptions": {
    "MaxPrice": "0.02",
    "SpotInstanceType": "one-time"
  }
}
EOF

#  --instance-market-options file://./spot-options.json

aws ec2 run-instances \
  --image-id $AMI \
  --instance-type $INSTANCE_TYPE \
  --user-data file://./user-data \
  --security-group-ids $(aws ec2 describe-security-groups | jq ".SecurityGroups[] | select(.GroupName==\"${PROJECT}-ec2-github-runner\") .GroupId" -r) \
  --key-name ${PROJECT}-ec2-github-manager \
  --associate-public-ip-address \
  --instance-initiated-shutdown-behavior terminate \
  --iam-instance-profile Name=${PROJECT}-ec2-github-runner > $EC2_WORKER

