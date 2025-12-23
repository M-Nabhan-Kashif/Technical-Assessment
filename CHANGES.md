# Implementation Changes Log

This document tracks all changes made to the original codebase during the Video Background Filter implementation.

## Overview
Converting the face detection technical assessment into a video background filter system that applies visual effects to the background while keeping the speaker in full color.

---

## Changes Made

### Iteration 1: Dependencies Update
**Date:** Initial implementation  
**Files Modified:**
- `requirements.txt`

**Changes:**
- Added `mediapipe` dependency for selfie segmentation model
- Added `numpy` dependency for array operations with OpenCV

**Reason:**
MediaPipe provides a lightweight selfie segmentation model that can distinguish between a person (foreground) and background. NumPy is required for efficient array operations when processing video frames with OpenCV.

---

### Iteration 2: Segmentation and Filtering Functions
**Date:** Implementation  
**Files Modified:**
- `backend/helpers.py`

**Changes:**
- Added MediaPipe imports and global segmentation model initialization
- Added `initialize_segmentation_model()`: Initializes MediaPipe Selfie Segmentation model (model_selection=1 for landscape/video)
- Added `segment_person(frame)`: Extracts person mask from video frame using MediaPipe, returns binary mask and segmented person
- Added `apply_grayscale_filter(frame)`: Converts frame to grayscale
- Added `apply_sepia_filter(frame)`: Applies sepia tone transformation using color matrix
- Added `apply_blur_filter(frame, blur_strength)`: Applies Gaussian blur with configurable strength
- Added `apply_background_filter(frame, mask, filter_type)`: Main filtering function that applies selected filter to background only while preserving person in full color
- Added `process_frame(frame_bytes, filter_type)`: Complete processing pipeline that decodes frame, segments person, applies filter, and returns processed frame as JPEG bytes with processing time

**Technical Details:**
- Uses MediaPipe Selfie Segmentation model (landscape mode) for person detection
- Applies morphological operations (close/open) to smooth mask edges
- Normalizes mask for proper blending between person and filtered background
- Supports three filter types: "grayscale", "sepia", "blur"
- Returns processing time in milliseconds for performance monitoring

**Reason:**
These functions provide the core video processing capabilities needed for background filtering. The segmentation model identifies the person, and the filtering functions apply visual effects only to the background pixels, creating the desired effect of keeping the speaker in color while filtering the background.

---

### Iteration 3: API Endpoints for Frame and Video Processing
**Date:** Implementation  
**Files Modified:**
- `backend/main.py`
- `backend/helpers.py`

**Changes:**

**In `backend/helpers.py`:**
- Added missing imports: `numpy`, `mediapipe`, `typing` (Tuple, Optional)
- Added `process_video(video_path, output_path, filter_type, progress_callback)`: Processes entire video file frame-by-frame with progress tracking

**In `backend/main.py`:**
- Added imports: `base64`, `threading`, `uuid`, `time`, `requests`
- Added segmentation model initialization on app startup
- Added job storage dictionary with thread-safe locking for async video processing
- Added `POST /process-frame` endpoint:
  - Accepts base64-encoded frame image and filter type
  - Returns processed frame as base64 with processing time
  - Validates filter type and handles errors gracefully
- Added `POST /process-video` endpoint:
  - Accepts video URL and filter type
  - Starts async video processing in background thread
  - Returns job ID for status tracking (HTTP 202 Accepted)
  - Downloads video, processes all frames, saves output
- Added `GET /process-status/<job_id>` endpoint:
  - Returns current status of video processing job
  - Provides progress percentage, status message, and result URL
  - Handles job not found errors
- Added helper function `download_video(url, save_path)`: Downloads video from URL to local filesystem
- Added helper function `process_video_async(job_id, video_url, filter_type)`: Background thread function for async video processing

**Technical Details:**
- Frame processing endpoint accepts base64 images (with or without data URL prefix)
- Video processing uses threading for async execution to avoid blocking the API
- Job status stored in-memory dictionary (thread-safe with locks)
- Progress updates every 10 frames during video processing
- Temporary files are cleaned up after processing
- Supports three filter types: "grayscale", "sepia", "blur"
- Error handling with appropriate HTTP status codes

**Reason:**
These endpoints provide the API interface for the frontend to interact with the video processing backend. The frame endpoint enables real-time frame-by-frame processing, while the video endpoint handles full video processing asynchronously to avoid timeouts. The status endpoint allows the frontend to track processing progress and retrieve results when complete.

---

### Iteration 4: Video Processing Utilities
**Date:** Implementation  
**Files Created:**
- `frontend/src/utils/videoProcessing.ts`

**Changes:**
- Created new utility file for video frame capture and base64 conversion functions
- Added `captureVideoFrame(video, canvas, timestamp?)`: Captures a frame from video element and draws it to canvas, with optional timestamp seeking
- Added `frameToBase64(canvas, format?, quality?)`: Converts canvas content to base64 string (removes data URL prefix)
- Added `base64ToImage(base64)`: Converts base64 string to HTMLImageElement Promise
- Added `drawImageToCanvas(image, canvas)`: Draws an image (ImageElement or base64) to canvas element
- Added `createCanvas(width, height)`: Helper function to create canvas elements
- Added `downloadFile(dataUrl, filename)`: Downloads a file from data URL
- Added `downloadProcessedVideo(blobUrl, filename)`: Downloads processed video from blob URL
- Added `getFrameAtTimestamp(video, timestamp)`: Gets video frame at specific timestamp as base64
- Added `processFrame(frameBase64, filterType, apiUrl)`: Sends frame to backend API for processing
- Added `captureAndProcessFrame(video, filterType, apiUrl)`: Complete workflow - captures frame and processes it through API

**Technical Details:**
- All functions are async/await based for proper promise handling
- Handles both base64 strings with and without data URL prefixes
- Canvas operations properly handle dimensions and context
- Video seeking is handled with event listeners for accurate frame capture
- Error handling with try/catch and promise rejections
- TypeScript typed with proper return types and parameter types
- Default API URL: `http://127.0.0.1:8080`

**Reason:**
These utilities provide the foundation for the frontend to interact with video elements, capture frames, convert between formats, and communicate with the backend API. They abstract away the complexity of canvas operations, base64 encoding/decoding, and API calls, making it easier to build the React components that will use these functions.

---

### Iteration 5: Video Processing React Hook
**Date:** Implementation  
**Files Created:**
- `frontend/src/hooks/useVideoProcessor.ts`

**Changes:**
- Created custom React hook for managing video processing state and logic
- Added comprehensive state management:
  - `isProcessing`: Boolean flag for single frame processing
  - `isProcessingFullVideo`: Boolean flag for full video processing
  - `progress`: Progress percentage (0-100) for video processing
  - `currentFilter`: Currently selected filter type ('grayscale', 'sepia', 'blur')
  - `processedFrames`: Array of processed frames with timestamps and processing times
  - `error`: Error message string or null
  - `videoJobId`: Job ID for async video processing
  - `processedVideoUrl`: URL to processed video when complete
- Added `processCurrentFrame()`: Captures and processes current video frame
- Added `processFrameAtTimestamp(timestamp)`: Processes frame at specific video timestamp
- Added `processFullVideo(videoUrl)`: Starts async full video processing with progress tracking
- Added `setFilter(filter)`: Updates current filter type
- Added `clearProcessedFrames()`: Clears all processed frames
- Added `clearError()`: Clears error state
- Added `getProcessedFrameAtTimestamp(timestamp)`: Retrieves processed frame closest to timestamp
- Added `displayProcessedFrame(canvas, frame)`: Displays processed frame on canvas
- Implemented polling mechanism for video processing status (1 second intervals)
- Automatic cleanup of polling intervals on unmount
- Error handling with user-friendly error messages
- TypeScript typed with proper interfaces and types

**Technical Details:**
- Uses React hooks: `useState`, `useRef`, `useCallback`, `useEffect`
- Integrates with `videoProcessing.ts` utilities
- Polls backend `/process-status` endpoint during video processing
- Manages canvas reference internally for frame processing
- Handles video readiness checks before processing
- Stores processed frames with timestamps for frame-by-frame playback
- Default API URL: `http://127.0.0.1:8080` (configurable)
- Polling interval: 1000ms (1 second)

**Reason:**
This hook centralizes all video processing logic and state management, making it easy for React components to integrate video processing functionality. It provides a clean API for processing individual frames or entire videos, managing loading states, tracking progress, and handling errors. The hook abstracts away the complexity of API calls, polling, and state synchronization, allowing components to focus on UI rendering.

---

### Iteration 6: Filter Selector Component
**Date:** Implementation  
**Files Created:**
- `frontend/src/components/FilterSelector.tsx`

**Files Modified:**
- `frontend/src/index.css`

**Changes:**

**In `frontend/src/components/FilterSelector.tsx`:**
- Created FilterSelector component for selecting background filter type
- Displays three filter options: Grayscale, Sepia, and Blur
- Each filter option shows:
  - Icon/emoji indicator
  - Filter name
  - Description text
  - Visual selection indicator (checkmark)
- Props:
  - `selectedFilter`: Currently selected filter type
  - `onFilterChange`: Callback when filter is changed
  - `disabled`: Optional flag to disable filter selection
- Uses card-based UI with hover effects
- Accessible with proper ARIA attributes (`aria-pressed` for selection state)

**In `frontend/src/index.css`:**
- Added `.filter-selector` styles: Container with white background, padding, and shadow
- Added `.filter-grid` styles: Responsive grid layout (auto-fit, min 180px columns)
- Added `.filter-card` styles: Card button with hover effects, transitions, and disabled states
- Added `.filter-card-selected` styles: Selected state with blue border and background tint
- Added `.filter-icon` styles: Large icon/emoji display
- Added `.filter-name` styles: Bold filter name text
- Added `.filter-description` styles: Smaller description text
- Added `.filter-checkmark` styles: Circular checkmark badge for selected state

**Technical Details:**
- Responsive grid layout that adapts to screen size
- Smooth transitions and hover effects for better UX
- Visual feedback for selected state (border, background, checkmark)
- Disabled state support for when processing is active
- TypeScript typed with FilterType from useVideoProcessor hook
- Follows existing design patterns (white cards, blue accents, shadows)

**Reason:**
The FilterSelector component provides an intuitive UI for users to choose which background filter to apply. The card-based design makes it easy to see all options at once, and the visual selection indicators provide clear feedback. The component integrates seamlessly with the useVideoProcessor hook and follows the existing design system.

---

### Iteration 7: Processed Video Player Component
**Date:** Implementation  
**Files Created:**
- `frontend/src/components/ProcessedVideoPlayer.tsx`

**Files Modified:**
- `frontend/src/index.css`

**Changes:**

**In `frontend/src/components/ProcessedVideoPlayer.tsx`:**
- Created ProcessedVideoPlayer component for displaying processed video frames on canvas
- Canvas-based rendering that syncs with original video playback
- Props:
  - `videoRef`: Reference to the original video element for synchronization
  - `processedFrames`: Array of processed frames from useVideoProcessor hook
  - `width`/`height`: Optional canvas dimensions (defaults to video dimensions)
  - `className`: Optional CSS class name
  - `showPlaceholder`: Whether to show placeholder text when no frame available
  - `placeholderText`: Custom placeholder text
- Features:
  - Automatic synchronization with video playback (play, pause, seek)
  - Frame matching: Finds closest processed frame within 0.5 seconds of current timestamp
  - RequestAnimationFrame loop for smooth frame updates during playback
  - Event listeners for timeupdate, play, pause, seeked events
  - Loading state indicator
  - Placeholder display when no processed frame is available
  - Automatic canvas dimension matching to video dimensions

**In `frontend/src/index.css`:**
- Added `.processed-video-container` styles: Container with black background, border-radius, and shadow
- Added `.processed-video-canvas` styles: Canvas styling with responsive width and black background
- Added `.processed-video-loading` styles: Loading indicator overlay with semi-transparent background

**Technical Details:**
- Uses refs to avoid infinite loops in useEffect dependencies
- RequestAnimationFrame for smooth 60fps updates during playback
- Frame matching algorithm finds closest frame within 0.5 second tolerance
- Canvas dimensions automatically match video dimensions on metadata load
- Proper cleanup of event listeners and animation frames on unmount
- Handles edge cases: no frames, video not loaded, seeking, etc.
- TypeScript typed with ProcessedFrame interface

**Reason:**
The ProcessedVideoPlayer component provides a canvas-based display for processed video frames that stays synchronized with the original video playback. This allows users to see the filtered background effect in real-time as the video plays. The component handles all the complexity of frame matching, canvas rendering, and synchronization, making it easy to integrate into the main application.

---

### Iteration 8: Main App Integration
**Date:** Implementation  
**Files Modified:**
- `frontend/src/App.tsx`
- `frontend/src/index.css`

**Changes:**

**In `frontend/src/App.tsx`:**
- Integrated all components: FilterSelector, ProcessedVideoPlayer, and useVideoProcessor hook
- Added view mode toggle: Original, Processed, or Side-by-Side view
- Added processing controls:
  - "Process Current Frame" button for single frame processing
  - "Process Full Video" button for async full video processing
  - "Clear Processed Frames" button to reset processed frames
- Added progress indicator for full video processing:
  - Visual progress bar (0-100%)
  - Status message display
  - Real-time progress updates
- Added error display with dismiss functionality
- Added processing statistics display:
  - Number of frames processed
  - Average processing time
  - Current filter type
- Removed old face detection code and ping backend functionality
- State management:
  - View mode state (original/processed/side-by-side)
  - Integrated with useVideoProcessor hook for all processing state
- UI layout:
  - Header with title
  - Filter selector at top
  - View mode toggle buttons
  - Video display area (responsive, supports side-by-side)
  - Control buttons
  - Progress/error/stats sections

**In `frontend/src/index.css`:**
- Added `.progress-container` styles: Container for progress indicators
- Added `.progress-bar` and `.progress-bar-fill` styles: Animated progress bar with percentage display
- Added `.error-message` styles: Error display container with red background
- Added `.error-close` styles: Close button for error messages with hover effect

**Technical Details:**
- Complete integration of all created components
- Responsive layout that works on different screen sizes
- Disabled states for buttons during processing
- Real-time synchronization between original and processed video
- Error handling with user-friendly messages
- Progress tracking for async video processing
- Statistics calculation (average processing time, frame count)
- Clean separation of concerns with hook-based state management

**Reason:**
This integration brings together all the components and functionality into a complete, working application. Users can now select filters, process frames or entire videos, view results in different modes, and track processing progress. The UI provides clear feedback at every step, making the video background filtering feature fully functional and user-friendly.

---

### Iteration 9: CORS Configuration and MediaPipe API Update
**Date:** Bug Fix  
**Files Modified:**
- `backend/main.py`
- `backend/helpers.py`

**Changes:**

**In `backend/main.py`:**
- Fixed CORS configuration to properly handle preflight OPTIONS requests
- Added explicit CORS configuration with:
  - Allowed origins: `http://localhost:3000` and `http://127.0.0.1:3000`
  - Allowed methods: GET, POST, OPTIONS, PUT, DELETE
  - Allowed headers: Content-Type, Authorization, X-Requested-With
  - Added max_age for preflight caching (3600 seconds)
- Added `@app.before_request` handler to explicitly handle OPTIONS preflight requests
- Added OPTIONS method to all route decorators (`/hello-world`, `/process-frame`, `/process-video`, `/process-status/<job_id>`)
- Made segmentation model initialization optional at startup (wrapped in try/except) to allow server to start even if MediaPipe fails initially

**In `backend/helpers.py`:**
- Updated MediaPipe integration to use Tasks API (MediaPipe 0.10.x compatible)
- Removed deprecated `solutions` API usage
- Added `download_model_if_needed()` function for automatic selfie segmentation model download
- Updated `initialize_segmentation_model()` to use `mediapipe.tasks.python.vision.ImageSegmenter`
- Model downloads automatically from MediaPipe's official repository on first use
- Model stored in `backend/models/selfie_segmenter.tflite` for caching
- Updated `segment_person()` function to use new Tasks API:
  - Uses `ImageSegmenter.segment()` instead of deprecated `process()`
  - Handles confidence masks from new API format
  - Converts MediaPipe Image format to numpy arrays
- Added `requests` import for model download functionality
- Improved error handling with graceful fallbacks

**Technical Details:**
- CORS preflight requests (OPTIONS) now return proper headers and 200 status
- MediaPipe 0.10.x uses Tasks API which requires model files (not bundled)
- Selfie segmentation model URL: `https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/1/selfie_segmenter.tflite`
- Model is downloaded once and cached locally
- Server can start without MediaPipe, model initializes on first use
- All API endpoints now properly handle CORS preflight requests

**Reason:**
The CORS fix resolves browser blocking issues when making requests from the frontend. The MediaPipe API update was necessary because MediaPipe 0.10.x removed the old `solutions` API in favor of the Tasks API. The new API requires downloading model files separately, which is now handled automatically. These fixes ensure the application works correctly with modern MediaPipe versions and proper CORS handling.

---

### Iteration 10: Segmentation Mask Processing Optimization
**Date:** Optimization  
**Files Modified:**
- `backend/helpers.py`
- `CHANGES.md`

**Changes:**

**In `backend/helpers.py`:**
- Optimized segmentation mask processing parameters based on research and production best practices
- **Configuration Updates:**
  - `SEGMENTATION_THRESHOLD`: Changed from 0.8 to 0.55 (standard production range: 0.5-0.55)
  - `MORPH_CLOSE_KERNEL_SIZE`: Changed from 9 to 7 (standard range: 5-7)
  - `EROSION_ITERATIONS`: Changed from 5 to 2 (standard: 1-2 iterations, 5+ causes artifacts)
  - `GAUSSIAN_BLUR_KERNEL_SIZE`: Changed from 19 to 15 (standard range: 9-15)
- **New Configuration Parameter:**
  - Added `POST_EROSION_CLOSE_KERNEL_SIZE = 5`: Critical parameter to fill holes created by erosion
- **Code Improvements:**
  - Added post-erosion closing operation in `segment_person()` function
  - This prevents blue spots and artifacts caused by aggressive erosion
  - Updated configuration documentation with research-based recommendations
- **Processing Pipeline Enhancement:**
  - Updated mask processing order: Close → Open → Erode → Close (post-erosion) → Blur
  - This follows modern production best practices for mask refinement

**Technical Details:**
- Research findings:
  - Standard confidence thresholds: 0.5-0.55 for production systems
  - Erosion iterations: 1-2 standard, 3+ requires post-erosion closing
  - Morphological kernel sizes: 3-7 for most applications
  - Post-erosion closing is critical when EROSION_ITERATIONS > 1
- Blue spot issue resolution:
  - Aggressive erosion (5 iterations) was creating holes in the mask
  - These holes allowed filtered background to show through
  - Post-erosion closing fills these holes, preventing blue spots
- Configuration documentation:
  - Added detailed comments explaining optimal ranges
  - Included research-based recommendations
  - Documented when to use different parameter values

**Reason:**
The previous configuration values were too aggressive, causing artifacts like blue spots and halo effects. Based on research into MediaPipe segmentation best practices and production system implementations (similar to Zoom, Teams background effects), the optimized values provide better balance between accuracy and artifact reduction. The addition of post-erosion closing is a critical fix that prevents holes in the mask, which was the root cause of blue spots appearing in processed frames.

---

### Iteration 11: Configuration Separation and API-Based Testing
**Date:** Testing Infrastructure  
**Files Modified:**
- `backend/segmentation_config.py` (new file)
- `backend/helpers.py`
- `backend/main.py`
- `tests/config_generator.py` (new file)
- `tests/config-comparison.spec.ts` (new file)
- `playwright.config.ts` (new file)
- `tests/README.md` (new file)
- `CHANGES.md`

**Changes:**

**New File: `backend/segmentation_config.py`:**
- Extracted all segmentation configuration parameters into a separate file
- Contains all tunable parameters: thresholds, kernel sizes, iterations, etc.
- Makes it easy to modify config values without touching core logic
- Well-documented with research-based recommendations

**In `backend/helpers.py`:**
- Removed inline configuration (moved to `segmentation_config.py`)
- Added imports from `segmentation_config` module
- Added runtime config override system:
  - `_runtime_config`: Global variable to store temporary config overrides
  - `set_runtime_config(config_overrides)`: Function to set runtime overrides
  - `get_config_value(key, default)`: Function to get config value (uses override if available)
- Updated `segment_person()` function to use `get_config_value()` for all parameters
- This allows API-based testing without modifying the config file

**In `backend/main.py`:**
- Added new endpoint `POST /process-frame-with-config`:
  - Accepts frame, filter_type, and optional `config` object
  - Sets runtime config overrides before processing
  - Clears overrides after processing (in finally block)
  - Returns processed frame and processing time
  - Enables testing different config combinations via API

**New File: `tests/config_generator.py`:**
- Python script to generate configuration test combinations
- Defines parameter ranges to test
- Generates all combinations (with sampling if too many)
- Creates unique config IDs for each combination
- Outputs `config_combinations.json` for Playwright tests

**New File: `tests/config-comparison.spec.ts`:**
- Playwright test suite for comparing config combinations
- Reads config combinations from JSON file
- Tests each combination at multiple video timestamps
- Tests with all filter types (grayscale, sepia, blur)
- Captures frames from video at specified timestamps
- Calls `/process-frame-with-config` API with custom config
- Takes snapshots of processed frames for visual comparison
- Organizes snapshots by config ID, timestamp, and filter type

**New File: `playwright.config.ts`:**
- Playwright configuration for running tests
- Configures web servers (backend and frontend) to start automatically
- Sets up sequential test execution to avoid conflicts
- Configures HTML reporter for test results

**New File: `tests/README.md`:**
- Documentation for the testing suite
- Setup instructions
- How to run tests
- How to customize test combinations
- Explanation of output format

**Technical Details:**
- Runtime config system uses thread-local storage concept (global variable)
- Config overrides are cleared after each API call to avoid cross-contamination
- Test combinations are generated using itertools.product
- Sampling reduces test combinations if too many (>20 by default)
- Snapshots are organized: `config_{id}_t{timestamp}_{filter}.png`
- API endpoint validates config parameters before use
- All config parameters support runtime overrides

**Reason:**
Separating configuration into its own file makes it easier to manage and modify settings. The API-based testing approach allows systematic comparison of different configuration combinations without manually editing files or restarting servers. This enables data-driven optimization of segmentation parameters by visually comparing results across many combinations. The Playwright test suite automates the process of testing multiple configs at different timestamps and filter types, generating snapshots for easy visual comparison.


