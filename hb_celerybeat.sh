#!/bin/bash

# Ensure the script runs only on rbot2
if [[ $(hostname) != "rbot2" ]]; then
    echo "This script should only run on rbot2."
    exit 1
fi

# SSH into rbot1 and check the status of celerybeat.service
STATUS=$(ssh pi@rbot1 "systemctl is-active celerybeat.service" 2>/dev/null)

# Check the status of celerybeat.service on rbot2
LOCAL_STATUS=$(systemctl is-active celerybeat.service)

# If SSH failed or celerybeat.service is not running on rbot1
if [[ -z "$STATUS" || "$STATUS" != "active" ]]; then
    # Check if rbot2 can ping Google
    if ping -c 1 google.com &> /dev/null; then
        # If there's internet connectivity and celerybeat.service is not active on rbot2, start it
        if [ "$LOCAL_STATUS" != "active" ]; then
            sudo systemctl start celerybeat.service
            echo "Started celerybeat.service on rbot2."
        fi
    else
        echo "No internet connection on rbot2."
    fi
# If celerybeat.service is running on both rbot1 and rbot2, stop it on rbot2
elif [ "$STATUS" == "active" ] && [ "$LOCAL_STATUS" == "active" ]; then
    sudo systemctl stop celerybeat.service
    echo "Stopped celerybeat.service on rbot2."
fi
