#!/bin/bash

# Check if input is provided
if [ $# -eq 0 ]; then
    echo "Error: please provide a number as an argument"
    exit 1
fi

# Check if input is within valid range
if [ $1 -lt 0 ] || [ $1 -gt 127 ]; then
    echo "Error: number must be between 0 and 127"
    exit 1
fi

# Normalize and execute command
 
normalized_value=$(awk -v n=$1 'BEGIN { printf "%d", (n/127) * (400-100) + 100 }')
v4l2-ctl -d /dev/video0 --set-ctrl zoom_absolute=$normalized_value

