#!/bin/bash
set -e

# Load environment variables from .env if it exists inside the container
if [ -f /carestream/.env ]; then
    export $(grep -v '^#' /carestream/.env | xargs) || true
fi

# Get the host and port, defaulting appropriately
SERVER_IP=${SERVER_IP:-0.0.0.0}
PORT=${CARESTREAM_PORT:-8000}

# Generate LoadScreen.mp4 if it doesn't exist
# This provides a clean, reliable loading screen for video playback
LOADSCREEN_PATH="/carestream/media/LoadScreen.mp4"

if [ ! -f "$LOADSCREEN_PATH" ]; then
    echo "Generating LoadScreen.mp4 for video transitions..."
    mkdir -p /carestream/media
    
    # Create a 4 second loading screen with text and animated rotating loading wheel
    # The wheel is created using 8 rotating circles that create a spinning effect
    ffmpeg -f lavfi -i color=c=black:s=1920x1080:d=4 \
           -vf "drawtext=text='LOADING YOUR NEXT VIDEO ...':fontsize=90:fontcolor=white:x=(w-text_w)/2:y=(h*0.3):line_spacing=10, \
                drawcircle=x=(w/2)+150*cos(2*PI*t/2):y=(h*0.65)+150*sin(2*PI*t/2):r=25:color=white@0.9:t=fill, \
                drawcircle=x=(w/2)+150*cos(2*PI*t/2+PI/4):y=(h*0.65)+150*sin(2*PI*t/2+PI/4):r=25:color=white@0.7:t=fill, \
                drawcircle=x=(w/2)+150*cos(2*PI*t/2+PI/2):y=(h*0.65)+150*sin(2*PI*t/2+PI/2):r=25:color=white@0.5:t=fill, \
                drawcircle=x=(w/2)+150*cos(2*PI*t/2+3*PI/4):y=(h*0.65)+150*sin(2*PI*t/2+3*PI/4):r=25:color=white@0.3:t=fill" \
           -pix_fmt yuv420p -c:v libx264 -preset ultrafast -crf 23 \
           -movflags +faststart \
           -an \
           "$LOADSCREEN_PATH" -y 2>&1 | grep -v "frame=" | tail -1
    
    if [ -f "$LOADSCREEN_PATH" ]; then
        FILE_SIZE=$(du -h "$LOADSCREEN_PATH" | cut -f1)
        echo "✓ LoadScreen.mp4 generated successfully ($FILE_SIZE)"
    else
        echo "⚠ Warning: Failed to generate LoadScreen.mp4 - loading screens will be skipped"
    fi
else
    FILE_SIZE=$(du -h "$LOADSCREEN_PATH" | cut -f1)
    echo "✓ LoadScreen.mp4 already exists ($FILE_SIZE)"
fi

echo "Starting CareStream on $SERVER_IP:$PORT..."

# Start gunicorn with eventlet worker for WebSocket support
exec gunicorn \
    --worker-class eventlet \
    -w 1 \
    --bind $SERVER_IP:$PORT \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    run:app
