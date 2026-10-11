# Shared settings for the AWS research machine (sourced by the other scripts). No secrets here: credentials live in
# ~/.aws (IAM user claude-2048, policies AmazonEC2FullAccess + ServiceQuotasFullAccess only).
export AWS_REGION=us-east-2
export AWS_DEFAULT_REGION=us-east-2
KEY=~/.ssh/claude-2048.pem          # key pair "claude-2048" (ed25519)
SG=${SG:-}                          # security group claude-2048-ssh: SSH from the user's IP only
SUBNET=${SUBNET:-}                  # default VPC, us-east-2b (the only AZ with hpc8a; m8a/c8a also exist there)
AMI=ami-0fa99aa8f97f9e30b           # Ubuntu 24.04 amd64 gp3, 2026-09-23
NAME_TAG=2048-research
# this machine's resource IDs (SG, SUBNET) live in env.local.sh, which is not committed
[ -f "$(dirname "${BASH_SOURCE[0]}")/env.local.sh" ] && . "$(dirname "${BASH_SOURCE[0]}")/env.local.sh"
instance_id() { aws ec2 describe-instances --filters "Name=tag:Name,Values=$NAME_TAG" \
  "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[].Instances[].InstanceId' --output text; }
instance_ip() { aws ec2 describe-instances --instance-ids "$1" --query 'Reservations[].Instances[].PublicIpAddress' --output text; }
SSH_OPTS="-i $KEY -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60"
