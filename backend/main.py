from flask import Flask, request, jsonify, send_from_directory
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


def process_video_async(job_id: str, video_url: str, filter_type: str):
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
        
        success, message = process_video(temp_input, temp_output, filter_type, progress_callback)
        
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
        "filter_type": "grayscale|sepia|blur"
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
        
        # Validate filter type
        valid_filters = ["grayscale", "sepia", "blur"]
        if filter_type not in valid_filters:
            return jsonify({"error": f"Invalid filter_type. Must be one of: {valid_filters}"}), 400
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Start async processing
        thread = threading.Thread(
            target=process_video_async,
            args=(job_id, video_url, filter_type)
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
        
        # Also check if this file is associated with any completed job
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



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
