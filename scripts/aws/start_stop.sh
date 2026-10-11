#!/bin/bash
# usage: start_stop.sh start|stop|status   (stopping keeps the disk; compute billing stops)
cd "$(dirname "$0")"; . ./env.sh
ID=$(instance_id); [ -z "$ID" ] && { echo "no instance"; exit 1; }
case "$1" in
  start) aws ec2 start-instances --instance-ids $ID --query 'StartingInstances[].CurrentState.Name' --output text
         aws ec2 wait instance-running --instance-ids $ID; echo "running at $(instance_ip $ID)" ;;
  stop)  aws ec2 stop-instances --instance-ids $ID --query 'StoppingInstances[].CurrentState.Name' --output text ;;
  *)     aws ec2 describe-instances --instance-ids $ID --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,PublicIpAddress]' --output text ;;
esac
