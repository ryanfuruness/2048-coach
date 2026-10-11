#!/bin/bash
# ssh into the research machine; extra arguments are run as a remote command.
cd "$(dirname "$0")"; . ./env.sh
ID=$(instance_id); IP=$(instance_ip "$ID")
[ -z "$IP" ] || [ "$IP" = None ] && { echo "no running instance (id: $ID)"; exit 1; }
exec ssh $SSH_OPTS ubuntu@$IP "$@"
