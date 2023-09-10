#!/bin/bash

# Set the path to the git directory
GIT_DIR="/home/pi/Desktop/celery_autotrade"

# Determine the hostname
HOSTNAME=$(hostname)

# Go to the GIT_DIR
cd $GIT_DIR

# Pull the latest changes from the repository
git pull origin main

# Check if there are changes in the working directory or the staging area
if [[ $(git diff --name-only) ]]; then
    # If the hostname is rbot1, rbot2, or rbotz1
    if [[ "$HOSTNAME" == "rbot1" || "$HOSTNAME" == "rbot2" || "$HOSTNAME" == "rbotz1" ]]; then
        # Restart the celery.service
        sudo systemctl restart celery.service
    fi

    # If the hostname is rbot1 or rbot2
    if [[ "$HOSTNAME" == "rbot1" || "$HOSTNAME" == "rbot2" ]]; then
        # Check if celery_config.py is changed and if celerybeat.service is running
        if git diff --name-only | grep "celery_config.py" && systemctl is-active --quiet celerybeat.service; then
            # Restart the celerybeat.service
            sudo systemctl restart celerybeat.service
        fi
    fi
fi
