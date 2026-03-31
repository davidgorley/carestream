# CareStream Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.1] - 2026-03-31

### Fixed
- **Viewsonic Device Temporary Disconnect During Multiple Pushes** - Device would "go offline" when pushing multiple videos sequentially
  - Root cause: Viewsonic firmware intentionally disconnects ADB daemon during video playback transitions for resource management
  - Impact: Second and subsequent video pushes would timeout/fail
  - Solution: Added automatic reconnection logic (`ensure_adb_connection()`) with 3 retry attempts
  - Reconnection points: Before each file push, before each video launch, before playback cleanup
  - Result: Seamless multi-video sequences even with device disconnects; system automatically recovers

- **Timezone Display Offset** - Timestamps showed 5 hours behind actual Central Time
  - Root cause: JavaScript Date objects displaying in browser timezone instead of Central Time
  - Solution: Updated `formatTime()` and date displays to explicitly use `America/Chicago` timezone with `Intl.DateTimeFormat`
  - Files updated: Dashboard.js, MediaManager.js
  - Result: All timestamps now display correct Central Time

### Changed
- **ADB Connection Strategy** - Implemented proactive reconnection
  - Device disconnects are now expected behavior (Viewsonic resource management)
  - System automatically detects and reconnects rather than failing
  - Improves reliability for multi-device deployments with Viewsonic displays

## [2.3.0] - 2026-03-30

### Fixed
- **CRITICAL: Video Playback Cutting Off Early** - Videos were interrupted mid-play due to pre-launch logic attempting to launch LoadScreen while video was still playing
  - Root cause: 80% pre-launch strategy would switch device away from video player, cutting playback short
  - Solution: Videos now play to full COMPLETION without interruption, then immediately queue LoadScreen
  - Result: Seamless, uninterrupted multi-video playback with professional transitions
  
- **Device ADB Connection Instability** - ADB connection frequently dropping during push sequences
  - Root cause: Aggressive `pm list packages` loop (5x shell commands, 5s timeout each) destabilizing TCP connection
  - Solution: Deprecated player detection function; simplified to direct multi-strategy launch approach
  - Added protective delays (150ms) between rapid ADB commands to prevent connection storms
  - Connection now remains stable throughout entire push sequence

- **Old Content Replaying After New Assignment** - Device would flash back and replay previously assigned videos
  - Root cause: Old media files persisted on device storage; media player would replay them on cycle/reset
  - Solution: `adb_clear_old_media()` deletes old .mp4 files (preserves LoadScreen.mp4) at push START
  - Result: Device has clean slate; only assigned content plays; no residual files

- **Video Player Lingering in Background** - After playback ended, video player app remained in Android recents with cached state
  - Root cause: Player app launched but never force-stopped; cached playback state persisted
  - Solution: `adb_force_stop_video_player()` force-stops player app after Vizabli launches
  - Result: No app in recents; zero background state; completely clean device handoff

### Changed
- **Playback Timing** - Completely redesigned playback logic for reliability
  - Videos play to FULL duration (not partial)
  - ZERO buffer between video end and next content launch (prevents device timeout)
  - LoadScreen launches AFTER video completes (not during)
  - Timestamps no longer create idle windows where device times out
  
- **ADB Command Protection** - Added safety measures to prevent connection storms
  - 150ms delay between consecutive ADB launch commands
  - 150ms delay between consecutive file pushes
  - Allows device TCP connection to settle between rapid state changes
  
- **Cleanup Sequence Redesigned**
  - Step 1: Connect to device
  - Step 1b: Clear old media files (NEW)
  - Step 2: Push LoadScreen + media files
  - Step 3: Sequential playback (video → LoadScreen → video → ...)
  - Step 4: Launch Vizabli, force-stop media player (NEW force-stop), device clean

### Technical
- New function `adb_clear_old_media()` - Safely removes old .mp4 files while preserving LoadScreen.mp4
- New function `adb_force_stop_video_player()` - Multi-strategy force-stop for RockVideoPlayer, VLC, MX Player, etc.
- New constant `ADB_COMMAND_DELAY = 0.15` - Protective gap between rapid ADB commands
- Deprecated `get_video_player_package()` - Removed dangerous player detection loop; now uses fallback-based launch
- Removed unused imports: `adb_stop_media_player`, `adb_clear_app_data`

### Removed
- Aggressive player detection logic (`pm list packages` loop)
- 80% pre-launch strategy (was interrupting videos)
- Unused media player control functions

### Testing
- ✅ Single video playback (no LoadScreen, direct to Vizabli)
- ✅ Multi-video playlists (video → LoadScreen → video → ... → Vizabli)
- ✅ No mid-playback interruptions
- ✅ No device timeout gaps
- ✅ ADB connection stable throughout
- ✅ No old content replay after new assignment
- ✅ Clean recents/multitasking view after playback
- ✅ All video durations preserved (no cutting off)

### Deployment Notes
- **BREAKING CHANGE** in playback timing (intentional fix)
- Rebuild container: `docker compose down && docker compose up -d --build`
- No database migrations required
- No environment variable changes required

---

## [2.2.1] - 2026-03-25

### Fixed
- **Critical Bug: Residual Video Playback** - Fixed issue where previous videos would resume/play unexpectedly
  - Root cause: LoadScreen.mp4 was not being pushed to device, causing media player state confusion
  - Loading screen now properly included in ADB push operation
  - Media player state is now correctly managed between videos
  - Eliminates race conditions and cached content interference
- **Loading Screen Implementation** - Corrected integration to use actual playback code path
  - Loading screen properly pushed to device before playback begins
  - Correct file handling with proper duration timing

### Changed
- **Push Service Enhanced** - LoadScreen.mp4 is now automatically pushed with media files
  - Ensures loading screen is always available on device
  - Proper error handling if loading screen push fails (playback continues)

### Technical
- Fixed code path: Now uses `push_service.py` (was accidentally using unused `playback_service.py`)
- Added os imports for file path handling
- Loading screen push happens before media file playback begins
- Improved error resilience for loading screen failures

---

## [2.2.0] - 2026-03-25

### Added
- **Loading Screen Between Videos**: New "Loading Next Video" screen displays automatically between playlist videos
  - Eliminates confusion during playback gaps between videos
  - Professional black screen with centered text and smooth transitions
  - Displays for 2.5 seconds (optimized for video buffer time)
  - Automatically skipped after the final video in a playlist

### Changed
- **Sequential Playback Logic**: Enhanced `launch_sequential_playback()` to include loading screen injection
  - More professional user experience during multi-video playback
  - Clearer indication that system is working and preparing the next video

### Fixed
- Video playback gaps no longer leave blank/confused end users
- Improved transparency in device-side playback status

### Fixed
- **Critical Bug: Residual Video Playback** - Fixed issue where previous videos would resume/play unexpectedly
  - Root cause: LoadScreen.mp4 was not being pushed to device, causing media player state confusion
  - Loading screen now properly included in ADB push operation
  - Media player state is now correctly managed between videos
  - Eliminates race conditions and cached content interference
- **Loading Screen Implementation** - Corrected integration to use actual playback code path
  - Loading screen properly pushed to device before playback begins
  - Correct file handling with proper duration timing

### Changed
- **Push Service Enhanced** - LoadScreen.mp4 is now automatically pushed with media files
  - Ensures loading screen is always available on device
  - Proper error handling if loading screen push fails (playback continues)

### Technical
- Fixed code path: Now uses `push_service.py` (was accidentally using unused `playback_service.py`)
- Added os imports for file path handling
- Loading screen push happens before media file playback begins
- Improved error resilience for loading screen failures

---

## [2.2.0] - 2026-03-25

### Added
- **Loading Screen Between Videos**: New "Loading Next Video" screen displays automatically between playlist videos
  - Eliminates confusion during playback gaps between videos
  - Professional black screen with centered text and smooth transitions
  - Displays for 2.5 seconds (optimized for video buffer time)
  - Automatically skipped after the final video in a playlist

### Changed
- **Sequential Playback Logic**: Enhanced `launch_sequential_playback()` to include loading screen injection
  - More professional user experience during multi-video playback
  - Clearer indication that system is working and preparing the next video

### Fixed
- Video playback gaps no longer leave blank/confused end users
- Improved transparency in device-side playback status

### Technical
- LoadScreen.mp4 introduced as system media file
- Configurable loading screen duration (2.5 seconds default)
- Seamless integration with existing ADB video launch mechanism

---

## [2.1.0] - 2026-03-24

### Added
- **Alairo Solutions Branding**: Integrated Alairo Solutions logo throughout the application
  - Professional logo added to login page and app header
  - "POWERED BY" text on login page
- **Environment-Based Configuration**: Consolidated all configurable variables to single `.env` file
  - Separate password variables for each user role: `REACT_APP_AUTH_USER_PW`, `REACT_APP_AUTH_ADMIN_PW`, `REACT_APP_AUTH_SUPERUSER_PW`
  - Clearer, more intuitive configuration for deployment across environments

### Changed
- **Login Page Redesign**: Complete visual overhaul with minimalist material design aesthetic
  - Removed demo credentials from login display (security improvement)
  - Restructured header with vertical stacking: CareStream → POWERED BY → Alairo Logo
  - Enhanced typography and spacing for professional appearance
- **Environment Configuration**: Migrated from hardcoded credentials to environment variables
  - Users no longer see demo credentials on login screen
  - Each role has individual password configuration

### Fixed
- Security vulnerability: Demo credentials no longer exposed on login screen
- Configuration clarity: Passwords now clearly separated by role instead of pipe-delimited format

### Security
- Removed sensitive demo information from UI
- Simplified credential management reduces misconfiguration risk

### Technical
- Docker build now passes authentication variables to frontend at build time
- Cleaner environment variable handling for both frontend and backend
- Improved separation of concerns with dedicated password variables

---

## [2.0.0] - 2026-03-24

### Added
- **Authentication System**: Three-tier login with role-based access control
  - `user`: Dashboard access only
  - `admin`: Dashboard & Media Manager access
  - `superuser`: Full access to all pages (Dashboard, Media Manager, Settings)
- **Login Page**: Styled login interface with credential validation
- **Session Persistence**: User authentication persists across page refreshes via localStorage
- **Logout Functionality**: Logout button in header for all authenticated users
- **Docker Data Persistence**: Implemented named volumes for robust data storage
  - `carestream-media`: For media files
  - `carestream-data`: For database and settings
- **Frontend Build**: Multi-stage Docker build for optimized production deployment

### Changed
- **Filter Bar Layout**: Updated to use CSS Grid matching room-grid column layout
  - Search, filters, and sorting controls now span full width with consistent alignment
- **Removed Filters**: "All Push Status" filter removed from dashboard filter bar
- **Docker Compose**: Migrated from bind mounts to Docker-managed named volumes

### Fixed
- Data loss prevention: Media files, database, and settings now survive `docker-compose down`
- Filter bar and room grid width alignment issues resolved

### Security
- Credentials stored in environment file
- Role-based access control prevents unauthorized page access
- Logout clears authentication state from localStorage

### Technical
- React Context API for authentication state management
- WebSocket support maintained through gunicorn + eventlet
- Python 3.11 backend with Flask
- Node.js 18 frontend build pipeline

---

## Upcoming Versions

### [Unreleased]

#### Planned Features
- [ ] Feature name and description
- [ ] Feature name and description

#### Planned Bug Fixes
- [ ] Bug description

---

## Version History Notes

When updating this changelog:
1. Use semantic versioning (MAJOR.MINOR.PATCH)
2. Update the date to match release date
3. Include sections for: Added, Changed, Fixed, Removed, Security, Technical
4. Keep entries user-friendly and organized
5. Link versions where applicable

