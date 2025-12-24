# Video Background Processing Application

A full-stack application for video background manipulation using MediaPipe Selfie Segmentation. The application allows users to replace video backgrounds, apply filters, and clip videos with real-time processing.

## Features

- **Background Replacement**: Replace video backgrounds with custom images
- **Background Filters**: Apply grayscale, sepia, or blur filters to backgrounds
- **No Change Mode**: Process video without applying any background changes
- **Video Clipping**: Trim videos to specific time ranges
- **Video Upload**: Upload and process your own video files (MP4, MOV, AVI, MKV, WebM, M4V)
- **Flexible View Modes**: Switch between side-by-side, original, or edited views (even during processing)
- **Real-time Progress**: Monitor video processing progress with percentage and status updates
- **Audio Preservation**: Maintains original audio in processed videos (requires FFmpeg)
- **Parallel Processing**: Optimized batch processing for faster video rendering

## Project Structure

```
Technical-Assessment/
├── backend/                 # Python Flask backend
│   ├── main.py            # Flask application and API endpoints
│   ├── helpers.py         # Video processing logic and segmentation
│   ├── segmentation_config.py  # Segmentation parameters configuration
│   ├── models/            # MediaPipe model files
│   └── temp/              # Temporary video files (auto-generated)
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── App.tsx        # Main application component
│   │   ├── components/    # React components (Sidebar, Navbar, VideoPlayer, etc.)
│   │   ├── hooks/         # Custom React hooks (useVideoProcessor)
│   │   ├── utils/         # Utility functions
│   │   └── consts.ts      # Application constants
│   └── public/            # Static assets
└── requirements.txt       # Python dependencies
```

## Prerequisites

- **Python 3.8+**
- **Node.js 16+** and npm
- **FFmpeg** (required for audio preservation)
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use Chocolatey: `choco install ffmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Linux**: `sudo apt-get install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (CentOS/RHEL)
  - **Important**: Ensure FFmpeg is in your system PATH

## Installation & Setup

### Backend Setup

1. **Navigate to project root**:
   ```bash
   cd Technical-Assessment
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify FFmpeg installation**:
   ```bash
   ffmpeg -version
   ```
   If this fails, install FFmpeg and add it to your PATH. Without FFmpeg, videos will process but audio won't be preserved.

5. **Start the backend server**:
   ```bash
   cd backend
   python main.py
   ```
   The backend will run on `http://127.0.0.1:8080`

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

3. **Start the React development server**:
   ```bash
   npm start
   ```
   The frontend will run on `http://localhost:3000`

## Usage

1. **Start both servers** (backend and frontend)
2. **Open browser** to `http://localhost:3000`
3. **Select video source**:
   - Use the default sample video, or
   - Upload your own video file
4. **Configure processing**:
   - **Background Mode**: Choose "Background Image", "Background Filter", or "No Change"
   - **Background Image**: Upload an image or select from the image library
   - **Background Filter**: Choose grayscale, sepia, or blur
   - **Video Clipping**: Set start and end times using the interactive slider
5. **Click "Edit Video"** to process
   - Progress bar appears below the button showing percentage and status
   - You can switch view modes even while processing
6. **View results**: Toggle between "Side-by-side", "Original", or "Edited" views in the navbar
7. **Download**: Click the download button to save the processed video

## API Endpoints

### Backend Routes

- `POST /process-video` - Process a video with background effects
  - Request body: `{ video_url, filter_type?, clip_start?, clip_end?, background_image? }`
  - Returns: `{ job_id, status, message }`

- `GET /process-status/<job_id>` - Get processing status
  - Returns: `{ status, progress, message, result_url?, error? }`

- `POST /upload-video` - Upload a video file
  - Form data: `video` (file)
  - Returns: `{ video_url, filename }`

- `GET /video/<filename>` - Serve processed/uploaded videos

- `GET /health` - Health check endpoint

## Configuration

### Segmentation Parameters

Edit `backend/segmentation_config.py` to adjust segmentation quality:
- `SEGMENTATION_THRESHOLD`: Mask confidence threshold (0.65-0.67 recommended, default: 0.67)
- `EROSION_ITERATIONS`: Edge tightness (4-5 recommended, default: 4)
- `MASK_EXPANSION_SCALE`: Mask expansion (1.02-1.05 recommended, default: 1.04)
- `GAUSSIAN_BLUR_KERNEL_SIZE`: Edge feathering (adaptive based on resolution: 17-25px)

### Processing Performance

The application uses batch processing with parallel I/O for optimal performance:
- Batch size adapts to CPU core count
- Separate threads for reading, processing, and writing frames
- Temporal smoothing maintains quality across frames

## Testing

### Manual Testing

1. **Test video upload**:
   - Upload a video file (MP4, MOV, etc.)
   - Verify it loads and plays correctly

2. **Test background replacement**:
   - Select "Background Image" mode
   - Upload or select a background image
   - Process the video and verify the background is replaced

3. **Test background filters**:
   - Select "Background Filter" mode
   - Choose a filter (grayscale, sepia, blur)
   - Process and verify the filter is applied

4. **Test video clipping**:
   - Set clip start and end times
   - Process and verify only the selected range is included

5. **Test audio preservation**:
   - Process a video with audio
   - Verify audio is present in the output

### Troubleshooting

- **FFmpeg not found**: Install FFmpeg and ensure it's in your PATH
- **Video processing fails**: Check backend logs for errors
- **Audio missing**: Verify FFmpeg installation
- **Poor edge quality**: Adjust parameters in `segmentation_config.py`
- **Slow processing**: Ensure you have sufficient CPU cores (processing is parallelized)

## Technologies Used

- **Backend**:
  - Python 3.8+
  - Flask (web framework)
  - OpenCV (video processing)
  - MediaPipe (person segmentation)
  - FFmpeg (audio handling)
  - NumPy (image processing)

- **Frontend**:
  - React 18+ with TypeScript
  - HTML5 Video API
  - CSS3 with modern responsive design

## Development Notes

### Code Structure

- **Backend**: 
  - `main.py`: API endpoints and request handling
  - `helpers.py`: Core video processing, segmentation, and batch processing logic
  - `segmentation_config.py`: Tunable segmentation parameters

- **Frontend**:
  - `App.tsx`: Main application state and orchestration
  - `components/Sidebar.tsx`: User controls and settings
  - `components/VideoPlayer.tsx`: Video playback component
  - `hooks/useVideoProcessor.ts`: Video processing API integration

### Key Implementation Details

- **Segmentation**: Uses MediaPipe Selfie Segmentation with temporal smoothing
- **Parallel Processing**: Batch processing with producer-consumer pattern for I/O
- **Audio Handling**: Extracts audio with FFmpeg and muxes it back into processed video
- **Edge Quality**: Configurable erosion, expansion, and blur for optimal edge detection

## License

This project is designed for technical assessment purposes.
