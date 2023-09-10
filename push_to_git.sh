#!/bin/bash

# Set the remote URL with the token
git remote set-url origin https://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@github.com/ohguowei/celery_rsi.git

# Add all changes to the staging area
git add .

# Commit the changes
git commit -m "test push"

# Push the changes to the main branch on the remote repository
git push -u origin main

