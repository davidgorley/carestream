import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app import db, socketio
from app.models.room import Room
from app.services.adb_service import adb_check_device
from app.utils import get_tz_aware_now_with_app

logger = logging.getLogger(__name__)
scheduler = None


def check_all_devices(app):
    """Check connectivity status of all configured rooms."""
    with app.app_context():
        rooms = Room.query.all()
        for room in rooms:
            try:
                status = adb_check_device(room.ip_address)
                room.status = status
                room.last_checked = get_tz_aware_now_with_app(app)
                logger.debug(f'Heartbeat: {room.room_number} ({room.ip_address}) -> {status}')
            except Exception as e:
                room.status = 'unknown'
                room.last_checked = get_tz_aware_now_with_app(app)
                logger.error(f'Heartbeat error for {room.room_number}: {e}')

        db.session.commit()

        # Emit status updates for all rooms
        room_statuses = [r.to_dict() for r in rooms]
        socketio.emit('heartbeat_update', {'rooms': room_statuses})
        logger.info(f'Heartbeat complete: checked {len(rooms)} rooms')


def start_heartbeat(app):
    """Start the background heartbeat scheduler."""
    global scheduler
    if scheduler is not None:
        return

    interval = int(os.getenv('HEARTBEAT_INTERVAL', 300))
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=check_all_devices,
        trigger='interval',
        seconds=interval,
        args=[app],
        id='heartbeat',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f'Heartbeat service started (interval: {interval}s)')
