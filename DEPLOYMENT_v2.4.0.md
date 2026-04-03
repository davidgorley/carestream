# CareStream v2.4.0 Deployment Checklist

**Version**: 2.4.0 (Released April 1, 2026)  
**Status**: ✅ PRODUCTION READY  
**Testing**: COMPLETE AND VALIDATED  
**Feature**: User-Configurable Timezone Selector + Global Timezone Fixes

---

## Pre-Deployment

- [ ] Review CHANGELOG.md for v2.4.0 changes
- [ ] Review STATUS_v2.4.0.md for feature details
- [ ] **IMPORTANT**: Verify hospital timezone requirements (EST/CST/PST/UTC/etc)
- [ ] Backup current database (automatic, but recommended for safety)
- [ ] Notify users of brief service window (< 2 minutes)

## Key Changes in v2.4.0

✅ **NEW**: User-configurable timezone selector in Settings  
✅ **FIXED**: Timestamp offset issues across all timezones  
✅ **CHANGED**: Backend timestamp architecture now timezone-aware  
✅ **IMPROVED**: Database-driven timezone (no rebuild needed to change timezone)

---

## Deployment Steps

### 1. Stop Current Services
```bash
docker compose down
```

### 2. Rebuild Container with New Code
```bash
docker compose up -d --build
```

The build will:
- Install new Python dependencies (zoneinfo utilities)
- Create settings database table automatically
- Initialize default timezone from TZ env variable
- Start the application with full timezone support

### 3. Verify Container Startup
```bash
docker logs carestream --tail 50
# Look for: "CareStream is ready" or successful initialization message
```

### 4. Check Health
```bash
docker compose ps
# Status should be "Up" for carestream container
```

### 5. Access Dashboard
- Open browser to `http://localhost:5000` (adjust port if configured differently)
- Dashboard should load and display correct current time in selected timezone
- Settings page should work
- Settings → Timezone dropdown should show 18 timezones

---

## Functional Testing

### 1. Verify Timezone Selector
- [ ] Navigate to Settings → Timezone
- [ ] Verify dropdown shows ~18 timezones (EST, CST, PST, UTC, GMT, CET, IST, JST, AEST, etc.)
- [ ] Select EST (or your hospital's timezone)
- [ ] Click "Save Timezone"
- [ ] Verify success message appears
- [ ] Refresh page
- [ ] Verify timezone persists (still shows EST)

### 2. Verify Timestamps Update
- [ ] Go to Dashboard
- [ ] Verify "Checked" timestamp shows current time in selected timezone
- [ ] Select a different timezone in Settings (e.g., PST)
- [ ] Return to Dashboard
- [ ] Verify timestamps updated to new timezone (should be 3 hours earlier if EST→PST)

### 3. Verify Push Operations
- [ ] Select a room and media file
- [ ] Push media to room
- [ ] Dashboard should show push start time in selected timezone
- [ ] Verify push completes successfully
- [ ] Check push log displays times in selected timezone

### 4. Verify Media Manager
- [ ] Upload a media file (or use existing)
- [ ] Verify upload time displays in selected timezone
- [ ] Create a playlist
- [ ] Verify creation time displays in selected timezone
- [ ] Switch timezones in Settings
- [ ] Verify all times update in Media Manager

### 5. Cross-Browser Testing
- [ ] Test Dashboard from 2+ browsers/devices
- [ ] Verify each shows same timezone (database-driven, not browser-local)
- [ ] Edit timezone in Settings from one browser
- [ ] Verify other browser reflects change on page reload

### 6. Verify Environment Variable Fallback
- [ ] In Docker, if timezone not savedin database, TZ env variable should be used
- [ ] Default is America/New_York if neither set
- [ ] Test by removing timezone from Settings database (advanced testing)

---

## Troubleshooting Deployment Issues

### Issue: Timezone dropdown is empty or won't save
- **Cause**: Settings table not created or API endpoint not responding
- **Fix**: 
  ```bash
  docker compose down
  docker compose up -d --build
  docker logs carestream
  ```
- Verify "CREATE TABLE settings" appears in logs

### Issue: Timestamps still wrong after selecting timezone
- **Cause**: Cache or stale component state
- **Fix**: 
  - Hard refresh browser (Ctrl+Shift+R)
  - Clear browser cache
  - Try different browser to isolate if browser-specific

### Issue: Container won't start after upgrade
- **Cause**: Database schema issue or dependency problem
- **Fix**:
  ```bash
  # Check logs for specific error
  docker logs carestream
  
  # If needed, backup and reset database
  docker compose down
  rm -f data/carestream.db
  docker compose up -d --build
  ```

### Issue: "Settings table already exists" error (benign)
- **Cause**: Normal during initial setup
- **Fix**: No action needed; proceeding normally

---

## Performance Notes

- Timezone changes are instant (no rebuild required)
- Timezone selection persists in SQLite database
- All timestamp operations compatible with 18 major timezones globally
- No performance impact from v2.3.0 (same push/playback speed)

---

## Rollback Plan (if needed)

If critical issues found post-deployment:

```bash
# Stop v2.4.0
docker compose down

# Get latest v2.3.1 code
git checkout v2.3.1

# Restart with previous version
docker compose up -d --build

# Database will downgrade gracefully (settings table ignored by v2.3.1)
```

---

## Post-Deployment

- [ ] Verify all rooms show correct current time in dashboard
- [ ] Confirm timezone selector works in Settings
- [ ] Confirm push operations complete successfully  
- [ ] Verify timestamps update when switching timezones
- [ ] Document timezone configuration for nursing staff in internal wiki
- [ ] Test from 2+ different locations/VPNs to ensure consistency
- [ ] Update deployment documentation for next team

---

## Key Files Modified

| File | Change | Impact |
|------|--------|--------|
| `app/models/settings.py` | NEW - Settings table | Database-driven config |
| `app/utils.py` | NEW - Timezone functions | All timestamp creation |
| `app/__init__.py` | Initialize settings table | Automatic on startup |
| `app/routes/settings.py` | Add `/timezone` endpoints | API for UI |
| `app/services/heartbeat_service.py` | Use timezone functions | Device check times |
| `app/services/push_service.py` | Use timezone functions | Push timestamps |
| `app/routes/push.py` | Use timezone functions | Push start times |
| `app/routes/media.py` | Use timezone functions | Upload times |
| `app/routes/playlists.py` | Use timezone functions | Creation times |
| `frontend/src/components/Settings.js` | Add timezone selector | User control |
| `frontend/src/components/Dashboard.js` | Fetch & use timezone | Display times |
| `frontend/src/components/MediaManager.js` | Fetch & use timezone | Display times |

---

## Support & Documentation

- **Changelog**: See CHANGELOG.md for complete feature list
- **Release Notes**: See RELEASE_NOTES_v2.4.0.md for architecture details
- **Status**: See STATUS_v2.4.0.md for test results
- **Main Docs**: See README.md for timezone configuration instructions
