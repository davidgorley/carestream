import logging
from app.services.adb_service import adb_launch_video, adb_return_to_vizabli

logger = logging.getLogger(__name__)


def launch_sequential_playback(ip_address, filenames_with_durations):
    """
    Launch videos sequentially on device.
    filenames_with_durations: list of (filename, duration_seconds) tuples
    Returns list of (filename, success, message) tuples.
    """
    import time
    BUFFER_SECONDS = 3
    results = []

    for filename, duration in filenames_with_durations:
        success, msg = adb_launch_video(ip_address, filename)
        results.append((filename, success, msg))

        if success and duration > 0:
            wait_time = duration + BUFFER_SECONDS
            logger.info(f'Waiting {wait_time}s for {filename} playback')
            time.sleep(wait_time)
        elif success:
            # Unknown duration, wait a default time
            time.sleep(10)

    # Return to Vizabli
    adb_return_to_vizabli(ip_address)
    return results
