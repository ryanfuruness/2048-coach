#!/bin/bash
# Run ON the instance once after launch: build tools and the project directory.
set -e
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q build-essential rsync htop tmux python3-numpy unzip
mkdir -p ~/2048
echo "cores: $(nproc), memory: $(free -g | awk '/Mem:/ {print $2}') GB"
