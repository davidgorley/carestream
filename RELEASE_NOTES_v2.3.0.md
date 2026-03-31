# CareStream v2.3.0 - Playback & Stability Release

**Date**: March 30, 2026  
**Status**: ✅ PRODUCTION STABLE - All testing complete

## Overview

CareStream v2.3.0 represents a comprehensive stability and playback reliability overhaul. All major video playback issues have been resolved through a complete redesign of the push/playback sequence, improved ADB connection handling, and comprehensive device state cleanup.

## Major Fixes

### 1. Video Playback Interruption (CRITICAL)
**Problem**: Videos were cutting off early mid-playback  
**Root Cause**: Pre-launch logic attempted to launch LoadScreen at 80% through video, which switched the device's focus away from the video player, interrupting playback  
**Solution**: Redesigned timing to let videos play to **full completion**, then immediately queue LoadScreen  
**Impact**: All videos now play uninterrupted at their full duration

### 2. ADB Connection Instability (CRITICAL)
**Problem**: Device frequently went offline during push sequences  
**Root Cause**: Aggressive player detection running 5 consecutive `pm list packages` shell commands with long timeouts, destabilizing TCP connection  
**Solution**: Deprecated player detection; simplified to direct multi-strategy launch; added 150ms protective delays between rapid ADB commands  
**Impact**: Connections remain stable throughout entire push sequences

### 3. Old Content Replaying (HIGH)
**Problem**: After assigning new videos, device would replay old previously-assigned content  
**Root Cause**: Old media files persisted on device storage; media player would replay them on cycle/reset  
**Solution**: Added `adb_clear_old_media()` called at push START (clears old .mp4s, preserves LoadScreen)  
**Impact**: Device has clean state; only assigned content plays; zero residual files

### 4. Background Player State (HIGH)
**Problem**: Video player app remained in Android recents with cached state after playback  
**Root Cause**: Player app launched but never force-stopped  
**Solution**: Added `adb_force_stop_video_player()` called after Vizabli launch  
**Impact**: No app in recents; zero background state; device completely clean

## Architecture Changes

### Push Sequence (Complete Redesign)

```
OLD SEQUENCE (broken):
├─ Connect to device
├─ Push LoadScreen
├─ Push media files
├─ Launch Video 1
├─ At 80%: Launch LoadScreen (INTERRUPTS VIDEO 1!)
├─ Wait for LoadScreen
├─ Launch Video 2
└─ Back to Vizabli → Video player still running

NEW SEQUENCE (v2.3.0):
├─ Connect to device
├─ Clear old media (NEW)
├─ Push LoadScreen + media files
├─ Launch Video 1 (plays 100%)
├─ When Video 1 ends → Immediately launch LoadScreen
├─ When LoadScreen ends → Immediately launch Video 2
├─ When Video 2 ends → Launch Vizabli
├─ Force-stop video player (NEW)
└─ Device completely clean
```

### ADB Command Safety

Each rapid ADB command now has 150ms protective delay:
- Between consecutive `adb_launch_video()` calls
- Between consecutive `adb_push_file()` calls
- Before `adb_force_stop_video_player()` after Vizabli launch

**Purpose**: Allows device TCP connection to settle between state changes

### Key Timing Constants

```python
VIDEO_START_DELAY = 0.5          # Render startup time
LOADING_SCREEN_DURATION = 2.5    # LoadScreen playback
PLAYBACK_BUFFER_SECONDS = 0.05   # Minimal buffer (no device timeout)
ADB_COMMAND_DELAY = 0.15         # Inter-command protection
```

## Files Modified

### app/services/adb_service.py
- **NEW**: `adb_clear_old_media()` - Cleanup old media files
- **NEW**: `adb_force_stop_video_player()` - Force-stop player apps
- **DEPRECATED**: `get_video_player_package()` - Removed dangerous player detection loop
- **MODIFIED**: Player detection functions simplified

### app/services/push_service.py
- **MODIFIED**: Playback sequence completely redesigned
- **ADDED**: Call to `adb_clear_old_media()` after connect
- **ADDED**: Call to `adb_force_stop_video_player()` after Vizabli
- **ADDED**: ADB_COMMAND_DELAY protective delays throughout
- **REMOVED**: Unused imports (`adb_stop_media_player`, `adb_clear_app_data`)

## Testing Checklist

✅ Single video playback (no LoadScreen, direct to Vizabli)  
✅ Multi-video playlists (video → LoadScreen → video → ... → Vizabli)  
✅ No mid-playback interruptions  
✅ No device timeout gaps  
✅ ADB connection stable throughout  
✅ No old content replay after new assignment  
✅ Clean recents/multitasking view after playback  
✅ All video durations preserved (no cutting off)  
✅ LoadScreen displays cleanly between videos  
✅ Device returns to Vizabli cleanly  

## Deployment Instructions

```bash
# 1. Stop running services
docker compose down

# 2. Rebuild with new code
docker compose up -d --build

# 3. Verify logs for clean startup
docker logs carestream --tail 50

# 4. Test: Assign video to device and monitor complete sequence
```

## Rollback

If issues occur, rollback to v2.2.1:
```bash
git checkout v2.2.1
docker compose down
docker compose up -d --build
```

## Known Limitations

- LoadScreen duration fixed at 2.5s (configurable via `LOADING_SCREEN_DURATION` constant if needed)
- Maximum 600s timeout for large video files (configurable in `adb_push_file()`)
- Requires ADB port 5555 on device (Android TCP/IP requirement)

## Future Improvements

- Adaptive LoadScreen duration based on device switching speed
- Device connectivity monitoring dashboard
- Granular per-room push history
- Video quality auto-selection based on network speed

## Support

For issues:
1. Check logs: `docker logs carestream --tail 200`
2. Verify device connectivity: Check room status in CareStream dashboard
3. Check ADB: `adb devices` on host machine
4. Review CHANGELOG.md for known issues

---

**CareStream Team**  
Version 2.3.0 - Production Stable
