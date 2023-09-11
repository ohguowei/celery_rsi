#!/bin/bash

# Set the path to the git directory
GIT_DIR="/home/pi/Desktop/celery_autotrade"

# Determine the hostname
HOSTNAME=$(hostname)

# Go to the GIT_DIR
cd $GIT_DIR

# Store the current commit hash
CURRENT_COMMIT=$(git rev-parse HEAD)

# Pull the latest changes from the repository
git pull origin master

# Check for changes between the old commit and the new commit
CHANGED_FILES=$(git diff --name-only $CURRENT_COMMIT)

# Check if there were any changes
if [[ "$CURRENT_COMMIT" != $(git rev-parse HEAD) ]]; then
    # If the hostname is rbot1, rbot2, or rbotz1
    if [[ "$HOSTNAME" == "rbot1" || "$HOSTNAME" == "rbot2" || "$HOSTNAME" == "rbotz1" ]]; then
        # Restart the celery.service
        sudo systemctl restart celery.service
    fi

    # If the hostname is rbot1 or rbot2
    if [[ "$HOSTNAME" == "rbot1" || "$HOSTNAME" == "rbot2" ]]; then
        # Check if celery_config.py has changed and if celerybeat.service is running
        if echo "$CHANGED_FILES" | grep -q "celery_config.py" && systemctl is-active --quiet celerybeat.service; then
            # Restart the celerybeat.service
            sudo systemctl restart celerybeat.service
        fi
    fi
fi
