# CRITICAL VIDEO PLAYBACK FIX - DEPLOYMENT GUIDE

## Problems Fixed

### 1. ✓ LoadScreen.mp4 Missing from Container
**Problem**: Python app looked for LoadScreen.mp4 at `/carestream/media/LoadScreen.mp4` but file wasn't available in container
- Dockerfile COPY approach had build context issues
- File path variations and local vs container syncing problems
- Loading screens never reached device, "blank video" appeared instead

**Fix**: Auto-generate LoadScreen.mp4 at container startup
- Added code to `entrypoint.sh` to generate LoadScreen.mp4 on startup
- **If file doesn't exist**: Auto-generates a 1920x1080 video with "LOADING YOUR NEXT VIDEO..." text
- **If file exists**: Uses existing file (lets you override with your own LoadScreen.mp4)
- File persists in named volume for future container restarts
- **Option**: Users can provide their own LoadScreen.mp4 via `docker cp` (resolution doesn't matter - Android handles scaling)
### 2. ✓ Silent File Push Failures
**Problem**: Files might fail to push to device but code didn't verify
- `adb_push_file()` returned success but file wasn't actually on device
- Device would launch video player with non-existent file path → black screen

**Fix**: Added `adb_verify_file()` function
- After every push, verifies file exists on device with exact file size
- Logs file size for debugging
- Returns detailed error if file not found on device
- Fails the entire push rather than silently continuing

### 3. ✓ Insufficient Launch Diagnostics
**Problem**: When videos wouldn't play, impossible to debug why
- No visibility into which command was sent to device
- No file existence checks on device before launch
- Error messages unclear about root cause

**Fix**: Enhanced `adb_launch_video()` with comprehensive logging
- **File verification**: Checks file exists on device BEFORE launching player
  - If file missing: Returns clear error "File not found on device"
  - Shows expected vs actual remote path
- **Command visibility**: Logs exact ADB commands being sent
- **Strategy tracking**: Shows which launch method succeeded
- **Visual formatting**: Uses box drawing for easy log scanning

### 4. ✓ Better LoadScreen Diagnostics  
**Problem**: Unclear if LoadScreen pushed successfully
- Silent failures during push
- No distinction between "file not found" vs "push failed"
- Users didn't know to rebuild container

**Fix**: Enhanced push_service.py logging for LoadScreen
- Shows where LoadScreen is being looked for
- Clear indicator if file not found vs push failed  
- **New**: Helpful message suggesting `docker compose up -d --build`
- Tracks whether LoadScreen was available throughout playback



## Deployment Steps

### Step 1: Rebuild Docker Container
```powershell
cd "c:\Users\Dave\Desktop\ALAIRO\MedCast\medcast-deployment\carestream"
docker compose down
docker compose up -d --build
```

**That's it!** LoadScreen.mp4 will be automatically generated when the container starts.

### Step 2: Verify LoadScreen.mp4 Was Created
```bash
docker exec carestream ls -lh /carestream/media/LoadScreen.mp4
```

Expected output:
```
-rw-r--r-- 1 root root 45K ... LoadScreen.mp4
```

Or check the logs for confirmation:
```bash
docker logs carestream | grep LoadScreen
```

Expected to see:
```
✓ LoadScreen.mp4 generated successfully (45K)
```

### Step 3: Check Server Logs for Diagnostics
```bash
# Watch logs during/after push operation
docker logs carestream --follow
```

**Look for these lines:**

✓ **File push success** (shows file size):
```
File verified on device: /sdcard/carestream/PreventiDiabetes.mp4 (1.2M)
✓ File push VERIFIED: Preventing_Diabetes.mp4 on device
```

✗ **File push failure** (shows component):
```
✗ File push FAILED verification: Preventing_Diabetes.mp4 not found
Possible causes: Push failed silently, file not pushed at all
```

✓ **Video launch success** (shows method):
```
✓ VERIFY] Checking if file exists on device...
✓ File verified on device: ... (45K)
[STRATEGY 1] Attempting generic ACTION_VIEW intent...
✓ Strategy 1 SUCCESS: Video launched with generic intent
```

✗ **Video launch failure** (shows file was missing):
```
✗ ERROR: File does NOT exist on device: /sdcard/carestream/video.mp4
     This will cause a blank/black screen!
     Possible causes: Push failed silently, file not pushed at all
```

✓ **Loading screen pushed**:
```
✓ Looking for LoadScreen.mp4 at: /carestream/media/LoadScreen.mp4
✓ LoadScreen.mp4 FOUND - attempting to push
✓ Loading screen pushed successfully
```

✗ **Loading screen missing**:
```
⚠ LoadScreen.mp4 NOT FOUND at /carestream/media/LoadScreen.mp4
  - Loading screens will NOT be displayed between videos
  - Check that LoadScreen.mp4 exists in /carestream/media/ directory
  - Or rebuild Docker container: docker compose up -d --build
```



## Testing Checklist

### Test 1: LoadScreen Auto-Generated
```bash
docker logs carestream | grep -i "loadscreen"
```
Should show: `✓ LoadScreen.mp4 generated successfully` ✓

### Test 2: Single Video Playback
1. **Assign 1 video** to a room
2. **Expected**: Video plays with visible content (not black screen)
3. **Check logs** for: `✓ File verified on device` and `✓ Strategy 1 SUCCESS`
4. **Result**: Video plays 5-10 seconds, then returns to Vizabli

### Test 3: Multiple Videos + LoadScreen
1. **Assign 2-3 videos** to a room  
2. **Expected sequence**:
   - Video 1 plays
   - LoadScreen displays (2.5 seconds, shows "LOADING YOUR NEXT VIDEO...")
   - Video 2 plays
   - (If 3 videos) LoadScreen again
   - Video 3 plays
   - Returns to Vizabli
3. **Check logs** for: `✓ Loading screen launched successfully`



## Common Issues & Solutions

### Issue: I want to use my own LoadScreen.mp4 (different resolution/design)
**Solution**: Copy your custom file into the container after first startup
```bash
# Your 1280x720 LoadScreen.mp4 will be used instead of the auto-generated one
docker cp ./media/LoadScreen.mp4 carestream:/carestream/media/LoadScreen.mp4

# Verify it was copied
docker exec carestream ls -lh /carestream/media/LoadScreen.mp4
```

On next container restart, entrypoint will see your file exists and use that instead of generating.

**Note**: There's no resolution issue - Android devices automatically scale/letterbox videos to fit display. Your 1280x720 will work fine.

### Issue: LoadScreen displays but appears black
**Cause**: Might be device/codec issue, or LoadScreen file has black content (that's OK)
**Solution**: 
1. Check device is receiving file: `adb shell ls -lh /sdcard/carestream/LoadScreen.mp4`
2. Try launching manually: `adb shell am start -a android.intent.action.VIEW -d file:///sdcard/carestream/LoadScreen.mp4 -t video/mp4`
3. Check device media player installed: `adb shell pm list packages | grep -i video`

### Issue: "File push FAILED verification"
**Cause**: Push command executed but file not actually on device
**Possible Reasons**:
- Device storage full: `adb shell df`
- Device disconnected mid-push
- File permissions: `adb shell chmod -R 777 /sdcard/carestream/`
- Device crashed: Restart it

**Solution**:
```bash
# Clear device storage
adb shell rm -rf /sdcard/carestream/*

# Verify push dest exists
adb shell mkdir -p /sdcard/carestream/

# Try push again
```

### Issue: Only Strategy 2 working (not Strategy 1)
**Cause**: Generic intent not working with device's intent resolver
**Expected**: System will automatically failover to Strategy 2
**Normal behavior**: Not an error - video still plays

### Issue: Device returns to Vizabli before video finishes
**Cause**: Video duration not set in database
**Solution**: 
1. Re-scan media files to get duration
2. Check database: `SELECT filename, duration FROM media_file;`
3. See push logs: `⚠ Duration not set - using fallback: 20s`



## Rollback (if needed)

If new code causes issues:

```bash
# Revert to previous code  
git checkout HEAD~1

# Rebuild - LoadScreen will auto-generate again at startup
docker compose down
docker compose up -d --build
```

LoadScreen.mp4 is auto-generated on container startup, so it will always be available.

## Success Indicators

After deployment, you should see in logs when pushing videos:

```
✓ File push VERIFIED: video1.mp4 on device
✓ File verified on device: /sdcard/carestream/video1.mp4 (45M)
✓ Strategy 1 SUCCESS: Video launched with generic intent
[VIDEO 1/2] ✓ Video playback complete

✓ Loading screen launched successfully
[VIDEO 1/2] ✓ Loading screen display complete - proceeding to next video

✓ File push VERIFIED: video2.mp4 on device
✓ File verified on device: /sdcard/carestream/video2.mp4 (30M)
✓ Strategy 1 SUCCESS: Video launched with generic intent  
[VIDEO 2/2] ✓ Video playback complete

✓ PUSH COMPLETE AND SUCCESSFUL
```

This means:
- Files being transferred successfully (verified)
- Videos detected on device before launching
- Playback launching reliably
- LoadScreen appears between videos
- Device returns to Vizabli cleanly
