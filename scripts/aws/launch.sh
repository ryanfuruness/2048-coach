#!/bin/bash
# Launch the research machine (once the vCPU quota allows it). usage: launch.sh [INSTANCE_TYPE]
#   hpc8a.96xlarge (default; 192 AMD Turin cores, 768 GiB, ~$7.92/h, needs the HPC quota L-F7808C92)
#   m8a.48xlarge   (fallback; 192 vCPU, 768 GiB, ~$11.69/h, needs the Standard quota L-1216C47A)
# Root volume: 500 GB gp3 (kept when the instance is stopped; stop it whenever nothing is queued).
set -e
cd "$(dirname "$0")"; . ./env.sh
TYPE=${1:-hpc8a.96xlarge}
if [ -n "$(instance_id)" ]; then echo "instance already exists: $(instance_id)"; exit 1; fi
# Hard time cap: the instance stops (not terminates: the disk is kept) when the OS shuts down, and the first-boot
# user-data schedules that shutdown CAP_HOURS after launch (default 24).
CAP_HOURS=${CAP_HOURS:-24}
printf '#!/bin/bash\nshutdown -h +%d "time cap reached"\n' $((CAP_HOURS * 60)) > /tmp/claude-2048-userdata.sh
aws ec2 run-instances --image-id $AMI --instance-type $TYPE --key-name claude-2048 \
  --instance-initiated-shutdown-behavior stop --user-data file:///tmp/claude-2048-userdata.sh \
  --network-interfaces "DeviceIndex=0,SubnetId=$SUBNET,Groups=$SG,AssociatePublicIpAddress=true" \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=500,VolumeType=gp3,DeleteOnTermination=false}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME_TAG},{Key=Project,Value=2048}]" \
                       "ResourceType=volume,Tags=[{Key=Name,Value=$NAME_TAG-root},{Key=Project,Value=2048}]" \
  --query 'Instances[0].InstanceId' --output text
