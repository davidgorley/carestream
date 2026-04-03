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

# Always regenerate LoadScreen.mp4 on startup to pick up any changes.
# It is auto-generated content, not user media - never cache it from a previous run.
echo "Generating LoadScreen.mp4 for video transitions..."
mkdir -p /carestream/media
if true; then

    # Square video (1080x1080) works in BOTH portrait and landscape orientations:
    #   - Landscape device: pillarboxed symmetrically, fills full height
    #   - Portrait device:  letterboxed symmetrically, fills full width
    # 1080px is a safe middle-ground — looks sharp on 720p, 1080p, and 4K displays.
    #
    # Font size is derived arithmetically so text fills exactly ~80% of the video width,
    # regardless of resolution.  No hardcoded pixel assumptions.
    #
    # "LOADING NEXT VIDEO..." = 21 chars.
    # DejaVuSans-Bold average char advance ≈ 0.58 × fontsize.
    # Target text_w = VIDEO_W × 0.80
    # ⟹  fontsize = VIDEO_W × 80 / 100 / 21 × 100 / 58
    #             = VIDEO_W × 8000 / (21 × 58)
    #             = VIDEO_W × 8000 / 1218  ≈  VIDEO_W / 15

    VIDEO_W=1080
    VIDEO_H=1080
    FONTSIZE=$(( VIDEO_W / 15 ))   # 72px at 1080 → text ≈ 864px ≈ 80% of 1080

    FONT_FILE="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    if [ ! -f "$FONT_FILE" ]; then
        echo "⚠ Font not found at $FONT_FILE - generating plain black screen as fallback"
        ffmpeg -y \
            -f lavfi -i "color=c=black:size=${VIDEO_W}x${VIDEO_H}:rate=30" \
            -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
            -t 7 \
            -vf "fade=t=in:st=0:d=2.5,fade=t=out:st=2.5:d=2.0" \
            -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
            -c:a aac -b:a 128k \
            -movflags +faststart \
            "$LOADSCREEN_PATH" \
            -loglevel error
    else
        ffmpeg -y \
            -f lavfi -i "color=c=black:size=${VIDEO_W}x${VIDEO_H}:rate=30" \
            -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
            -t 7 \
            -vf "drawtext=fontfile=${FONT_FILE}:text='LOADING NEXT VIDEO...':fontcolor=white:fontsize=${FONTSIZE}:x=(w-text_w)/2:y=(h-text_h)/2,fade=t=in:st=0:d=2.5,fade=t=out:st=2.5:d=2.0" \
            -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p \
            -c:a aac -b:a 128k \
            -movflags +faststart \
            "$LOADSCREEN_PATH" \
            -loglevel error
    fi

    if [ -f "$LOADSCREEN_PATH" ]; then
        FILE_SIZE=$(du -h "$LOADSCREEN_PATH" | cut -f1)
        echo "✓ LoadScreen.mp4 generated successfully (${VIDEO_W}x${VIDEO_H}, fontsize=${FONTSIZE}) ($FILE_SIZE)"
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
