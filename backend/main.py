from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import base64
import threading
import uuid
import time
import os
import requests
from helpers import *

app = Flask(__name__)
# Configure CORS to allow requests from frontend
cors = CORS(app, 
    resources={
        r"/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": True,
            "max_age": 3600
        }
    }
)

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize segmentation model on startup (will be lazy-loaded if this fails)
try:
    initialize_segmentation_model()
    logger.info("Segmentation model initialized successfully")
except Exception as e:
    logger.warning(f"Segmentation model initialization deferred: {e}. It will be initialized on first use.")

# Check FFmpeg availability on startup
def check_ffmpeg_availability():
    """Check if FFmpeg is available and log status."""
    from helpers import find_ffmpeg
    import subprocess
    
    ffmpeg_path = find_ffmpeg()
    
    if ffmpeg_path:
        logger.info(f"FFmpeg found at: {ffmpeg_path}")
        # Test if it works
        try:
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                logger.info(f"FFmpeg is working: {version}")
                logger.info("Audio preservation is ENABLED")
                return True
            else:
                logger.warning(f"FFmpeg found but returned error code: {result.returncode}")
        except Exception as e:
            logger.warning(f"FFmpeg found but not working: {e}")
    else:
        logger.warning(
            "=" * 60 + "\n"
            "WARNING: FFmpeg not found. Audio will NOT be preserved in processed videos.\n"
            "To enable audio preservation, install FFmpeg:\n"
            "  Windows: winget install ffmpeg OR choco install ffmpeg\n"
            "  macOS: brew install ffmpeg\n"
            "  Linux: sudo apt-get install ffmpeg\n"
            "After installation, restart this server.\n"
            "=" * 60
        )
    return False

# Check FFmpeg on startup
ffmpeg_available = check_ffmpeg_availability()

# Job storage for async video processing
processing_jobs = {}
jobs_lock = threading.Lock()

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:3000")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        response.headers.add("Access-Control-Max-Age", "3600")
        return response

@app.route("/hello-world", methods=["GET", "OPTIONS"])
def hello_world():
    try:
        return jsonify({"Hello": "World"}), 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET", "OPTIONS"])
def health_check():
    """
    Health check endpoint that reports system status including FFmpeg availability.
    
    Returns:
    {
        "status": "ok",
        "ffmpeg": {
            "available": true/false,
            "path": "path/to/ffmpeg" or null,
            "working": true/false,
            "version": "version string" or null
        },
        "audio_support": true/false
    }
    """
    try:
        from helpers import find_ffmpeg
        import subprocess
        
        ffmpeg_path = find_ffmpeg()
        ffmpeg_status = {
            "available": ffmpeg_path is not None,
            "path": ffmpeg_path,
            "working": False,
            "version": None
        }
        
        if ffmpeg_path:
            try:
                result = subprocess.run(
                    [ffmpeg_path, '-version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    ffmpeg_status["working"] = True
                    ffmpeg_status["version"] = result.stdout.split('\n')[0]
            except Exception as e:
                logger.warning(f"Error testing FFmpeg: {e}")
        
        return jsonify({
            "status": "ok",
            "ffmpeg": ffmpeg_status,
            "audio_support": ffmpeg_status["available"] and ffmpeg_status["working"]
        }), 200
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/process-frame-with-config", methods=["POST", "OPTIONS"])
def process_frame_with_config_endpoint():
    """
    Process a single frame with custom segmentation config parameters (for testing).
    
    Request body:
    {
        "frame": "base64_encoded_image",
        "filter_type": "grayscale|sepia|blur",
        "config": {
            "SEGMENTATION_THRESHOLD": 0.6,
            "EROSION_ITERATIONS": 3,
            ...
        }
    }
    
    Returns:
    {
        "processed_frame": "base64_encoded_processed_image",
        "processing_time": 123.45
    }
    """
    try:
        data = request.get_json()
        
        if not data or "frame" not in data:
            return jsonify({"error": "Missing 'frame' in request body"}), 400
        
        frame_base64 = data.get("frame", "")
        filter_type = data.get("filter_type", "grayscale")
        config_overrides = data.get("config", {})
        
        # Validate filter type
        valid_filters = ["grayscale", "sepia", "blur"]
        if filter_type not in valid_filters:
            return jsonify({"error": f"Invalid filter_type. Must be one of: {valid_filters}"}), 400
        
        # Set runtime config overrides
        from helpers import set_runtime_config
        set_runtime_config(config_overrides)
        
        try:
            # Decode base64 frame
            try:
                # Remove data URL prefix if present
                if "," in frame_base64:
                    frame_base64 = frame_base64.split(",")[1]
                
                frame_bytes = base64.b64decode(frame_base64)
            except Exception as e:
                return jsonify({"error": f"Failed to decode base64 frame: {str(e)}"}), 400
            
            # Process frame
            processed_bytes, processing_time = process_frame(frame_bytes, filter_type)
            
            # Encode processed frame to base64
            processed_base64 = base64.b64encode(processed_bytes).decode('utf-8')
            
            return jsonify({
                "processed_frame": processed_base64,
                "processing_time": processing_time
            }), 200
        finally:
            # Clear runtime config after processing
            set_runtime_config(None)
        
    except Exception as e:
        logger.error(f"Error processing frame with config: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/process-frame", methods=["POST", "OPTIONS"])
def process_frame_endpoint():
    """
    Process a single video frame with background filter.
    
    Request body:
    {
        "frame": "base64_encoded_image",
        "filter_type": "grayscale|sepia|blur"
    }
    
    Returns:
    {
        "processed_frame": "base64_encoded_image",
        "processing_time": milliseconds
    }
    """
    try:
        data = request.get_json()
        
        if not data or "frame" not in data:
            return jsonify({"error": "Missing 'frame' in request body"}), 400
        
        frame_base64 = data.get("frame", "")
        filter_type = data.get("filter_type", "grayscale")
        
        # Validate filter type
        valid_filters = ["grayscale", "sepia", "blur"]
        if filter_type not in valid_filters:
            return jsonify({"error": f"Invalid filter_type. Must be one of: {valid_filters}"}), 400
        
        # Decode base64 frame
        try:
            # Remove data URL prefix if present
            if "," in frame_base64:
                frame_base64 = frame_base64.split(",")[1]
            
            frame_bytes = base64.b64decode(frame_base64)
        except Exception as e:
            return jsonify({"error": f"Failed to decode base64 frame: {str(e)}"}), 400
        
        # Process frame
        processed_bytes, processing_time = process_frame(frame_bytes, filter_type)
        
        # Encode processed frame to base64
        processed_base64 = base64.b64encode(processed_bytes).decode('utf-8')
        
        return jsonify({
            "processed_frame": processed_base64,
            "processing_time": processing_time
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        return jsonify({"error": str(e)}), 500


def download_video(url: str, save_path: str) -> bool:
    """Download video from URL to local path."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Video downloaded to {save_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download video: {str(e)}")
        return False


def process_video_async(job_id: str, video_url: str, filter_type: str, clip_start: float = None, clip_end: float = None, background_image_data: str = None):
    """Process video asynchronously in a background thread."""
    try:
        with jobs_lock:
            processing_jobs[job_id] = {
                "status": "processing",
                "progress": 0,
                "message": "Downloading video...",
                "result_url": None,
                "error": None
            }
        
        # Download video
        temp_input = get_temp_path() + ".mp4"
        if not download_video(video_url, temp_input):
            with jobs_lock:
                processing_jobs[job_id] = {
                    "status": "error",
                    "progress": 0,
                    "message": "Failed to download video",
                    "result_url": None,
                    "error": "Failed to download video from URL"
                }
            return
        
        # Process video
        temp_output = get_temp_path() + "_processed.mp4"
        
        def progress_callback(progress):
            with jobs_lock:
                if job_id in processing_jobs:
                    processing_jobs[job_id]["progress"] = progress
                    processing_jobs[job_id]["message"] = f"Processing video... {progress}%"
        
        # Decode background image if provided
        background_image = None
        if background_image_data:
            try:
                import numpy as np
                import cv2
                
                # Check if it's a URL (starts with http:// or https://)
                if background_image_data.startswith(('http://', 'https://')):
                    # Download image from URL
                    logger.info(f"Downloading background image from URL: {background_image_data[:50]}...")
                    response = requests.get(background_image_data, timeout=30)
                    response.raise_for_status()
                    image_bytes = response.content
                else:
                    # It's base64 data
                    # Remove data URL prefix if present
                    bg_data = background_image_data
                    if "," in bg_data:
                        bg_data = bg_data.split(",")[1]
                    
                    # Decode base64 to bytes
                    image_bytes = base64.b64decode(bg_data)
                
                # Convert bytes to numpy array
                nparr = np.frombuffer(image_bytes, np.uint8)
                background_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if background_image is None:
                    logger.warning("Failed to decode background image, proceeding without it")
                    background_image = None
                else:
                    logger.info(f"Background image loaded successfully: {background_image.shape}")
            except Exception as e:
                logger.warning(f"Error processing background image: {e}, proceeding without it")
                background_image = None
        
        success, message = process_video(temp_input, temp_output, filter_type, progress_callback, clip_start, clip_end, background_image)
        
        if success:
            # Generate a URL to serve the processed video
            # Extract just the filename from the path
            filename = os.path.basename(temp_output)
            result_url = f"http://127.0.0.1:8080/video/{filename}"
            
            with jobs_lock:
                processing_jobs[job_id] = {
                    "status": "completed",
                    "progress": 100,
                    "message": "Video processing complete",
                    "result_url": result_url,
                    "error": None,
                    "file_path": temp_output  # Store actual path for serving
                }
            
            # Cleanup input file
            try:
                os.remove(temp_input)
            except:
                pass
        else:
            with jobs_lock:
                processing_jobs[job_id] = {
                    "status": "error",
                    "progress": 0,
                    "message": "Video processing failed",
                    "result_url": None,
                    "error": message
                }
            
            # Cleanup
            try:
                os.remove(temp_input)
            except:
                pass
    
    except Exception as e:
        logger.error(f"Error in async video processing: {str(e)}")
        with jobs_lock:
            processing_jobs[job_id] = {
                "status": "error",
                "progress": 0,
                "message": "Unexpected error during processing",
                "result_url": None,
                "error": str(e)
            }


@app.route("/process-video", methods=["POST", "OPTIONS"])
def process_video_endpoint():
    """
    Start processing an entire video with background filter (async).
    
    Request body:
    {
        "video_url": "https://...",
        "filter_type": "grayscale|sepia|blur|null" (null for clipping only),
        "clip_start": 0.0 (optional, in seconds),
        "clip_end": 10.0 (optional, in seconds)
    }
    
    Returns:
    {
        "job_id": "unique_job_id",
        "status": "processing",
        "message": "Video processing started"
    }
    """
    try:
        data = request.get_json()
        
        if not data or "video_url" not in data:
            return jsonify({"error": "Missing 'video_url' in request body"}), 400
        
        video_url = data.get("video_url", "")
        filter_type = data.get("filter_type", "grayscale")
        clip_start = data.get("clip_start", None)
        clip_end = data.get("clip_end", None)
        
        # Validate filter type (allow null for clipping only)
        valid_filters = ["grayscale", "sepia", "blur", None, "none"]
        if filter_type not in valid_filters:
            return jsonify({"error": f"Invalid filter_type. Must be one of: {valid_filters}"}), 400
        
        # Normalize filter_type: convert "none" or None to None
        if filter_type in [None, "none"]:
            filter_type = None
        
        # Validate clip times if provided
        if clip_start is not None and clip_end is not None:
            if clip_start < 0:
                return jsonify({"error": "clip_start must be >= 0"}), 400
            if clip_end <= clip_start:
                return jsonify({"error": "clip_end must be > clip_start"}), 400
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Get background image if provided
        background_image_data = data.get("background_image", None)
        
        # Start async processing
        thread = threading.Thread(
            target=process_video_async,
            args=(job_id, video_url, filter_type, clip_start, clip_end, background_image_data)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "status": "processing",
            "message": "Video processing started"
        }), 202  # 202 Accepted for async processing
    
    except Exception as e:
        logger.error(f"Error starting video processing: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/process-status/<job_id>", methods=["GET", "OPTIONS"])
def process_status_endpoint(job_id):
    """
    Check the status of a video processing job.
    
    Returns:
    {
        "job_id": "job_id",
        "status": "processing|completed|error",
        "progress": 0-100,
        "message": "Status message",
        "result_url": "url_to_processed_video" (if completed),
        "error": "error_message" (if error)
    }
    """
    try:
        with jobs_lock:
            if job_id not in processing_jobs:
                return jsonify({
                    "error": "Job not found"
                }), 404
            
            job_status = processing_jobs[job_id].copy()
            job_status["job_id"] = job_id
        
        return jsonify(job_status), 200
    
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/video/<filename>", methods=["GET", "OPTIONS"])
def serve_video(filename):
    """
    Serve processed video files.
    
    Args:
        filename: Name of the video file to serve
        
    Returns:
        Video file with appropriate headers
    """
    try:
        # Security: Only allow files from temp directory
        temp_dir = os.path.join(os.path.dirname(__file__), "temp")
        file_path = os.path.join(temp_dir, filename)
        
        # Verify file exists and is in temp directory (security check)
        if not os.path.exists(file_path):
            return jsonify({"error": "Video file not found"}), 404
        
        # Ensure the file is actually in the temp directory (prevent directory traversal)
        real_path = os.path.realpath(file_path)
        real_temp_dir = os.path.realpath(temp_dir)
        if not real_path.startswith(real_temp_dir):
            return jsonify({"error": "Invalid file path"}), 403
        
        # Check if this file is associated with any completed job OR is an uploaded video
        # Uploaded videos start with "uploaded_" prefix
        is_uploaded_video = filename.startswith("uploaded_")
        
        if not is_uploaded_video:
            # For processed videos, check if associated with a job
            with jobs_lock:
                file_found = False
                for job_id, job_data in processing_jobs.items():
                    if job_data.get("file_path") == file_path and job_data.get("status") == "completed":
                        file_found = True
                        break
            
            if not file_found:
                # File exists but not associated with any job - might be orphaned, but we'll still serve it
                logger.warning(f"Serving video file not associated with any job: {filename}")
        
        # Serve the file with appropriate headers for video streaming
        response = send_from_directory(temp_dir, filename, mimetype='video/mp4', as_attachment=False)
        # Set headers (use direct assignment to avoid duplicates)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Type'] = 'video/mp4'
        # Add CORS headers for video streaming
        origin = request.headers.get('Origin')
        if origin in ['http://localhost:3000', 'http://127.0.0.1:3000']:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range'
        # Set Content-Disposition only if not already set (for inline playback)
        if 'Content-Disposition' not in response.headers:
            response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f"Error serving video: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/upload-video", methods=["POST", "OPTIONS"])
def upload_video_endpoint():
    """
    Upload a video file for processing.
    
    Request: multipart/form-data with 'video' field
    Returns: {
        "video_url": "http://127.0.0.1:8080/video/uploaded_filename.mp4",
        "filename": "uploaded_filename.mp4"
    }
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # Check if video file is in request
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        
        # Check if file was actually selected
        if video_file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Validate file type
        allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        file_ext = os.path.splitext(video_file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({"error": f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"}), 400
        
        # Validate file size (500MB limit)
        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
        video_file.seek(0, os.SEEK_END)
        file_size = video_file.tell()
        video_file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({"error": f"File too large. Maximum size: 500MB"}), 400
        
        if file_size == 0:
            return jsonify({"error": "File is empty"}), 400
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        safe_filename = secure_filename(video_file.filename)
        filename_base, filename_ext = os.path.splitext(safe_filename)
        unique_filename = f"uploaded_{unique_id}{filename_ext}"
        
        # Ensure temp directory exists
        temp_dir = os.path.join(os.path.dirname(__file__), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(temp_dir, unique_filename)
        video_file.save(file_path)
        
        logger.info(f"Video uploaded successfully: {unique_filename} ({file_size / (1024*1024):.2f} MB)")
        
        # Return video URL
        video_url = f"http://127.0.0.1:8080/video/{unique_filename}"
        
        return jsonify({
            "video_url": video_url,
            "filename": unique_filename
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        return jsonify({"error": f"Failed to upload video: {str(e)}"}), 500


if __name__ == "__main__":
    # Re-check FFmpeg if server is restarted
    if not ffmpeg_available:
        logger.info("Re-checking FFmpeg availability...")
        check_ffmpeg_availability()
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
