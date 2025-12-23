import logging
import ffmpeg
import os
import uuid
import cv2
import numpy as np
import requests
from typing import Tuple, Optional

# A lightweight face detection model (kept for backward compatibility)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# MediaPipe Selfie Segmentation
# Import will be done lazily in initialize_segmentation_model to handle import errors gracefully
selfie_segmentation = None

# Import segmentation configuration
from segmentation_config import (
    SEGMENTATION_THRESHOLD,
    MORPH_CLOSE_KERNEL_SIZE,
    MORPH_OPEN_KERNEL_SIZE,
    EROSION_KERNEL_SIZE,
    EROSION_ITERATIONS,
    POST_EROSION_CLOSE_KERNEL_SIZE,
    GAUSSIAN_BLUR_KERNEL_SIZE,
    GAUSSIAN_BLUR_SIGMA
)

# Runtime config overrides for testing (set via API)
_runtime_config = None

def set_runtime_config(config_overrides: dict):
    """Set runtime configuration overrides for testing.
    
    Args:
        config_overrides: Dictionary with config keys and values to override
    """
    global _runtime_config
    _runtime_config = config_overrides.copy() if config_overrides else None

def get_config_value(key: str, default_value):
    """Get config value, using runtime override if available."""
    if _runtime_config and key in _runtime_config:
        return _runtime_config[key]
    return default_value

        
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_temp_path():
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    random_filename = f"temp_{str(uuid.uuid4())[:8]}"
    return os.path.join(temp_dir, random_filename)


def download_model_if_needed(model_url: str, model_path: str) -> str:
    """Download model file if it doesn't exist."""
    if os.path.exists(model_path):
        return model_path
    
    try:
        logger.info(f"Downloading model from {model_url}...")
        response = requests.get(model_url, stream=True, timeout=60)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Model downloaded to {model_path}")
        return model_path
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        raise


def initialize_segmentation_model():
    """
    Initialize the MediaPipe Selfie Segmentation model using Tasks API.
    This should be called once at application startup.
    """
    global selfie_segmentation
    if selfie_segmentation is None:
        try:
            # Use MediaPipe 0.10.x Tasks API
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.vision.core import image as mp_image_module
            
            # Selfie segmentation model URL (MediaPipe's official model)
            model_url = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/1/selfie_segmenter.tflite"
            model_dir = os.path.join(os.path.dirname(__file__), "models")
            model_path = os.path.join(model_dir, "selfie_segmenter.tflite")
            
            # Download model if needed
            download_model_if_needed(model_url, model_path)
            
            # Create ImageSegmenter
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.ImageSegmenterOptions(
                base_options=base_options,
                output_confidence_masks=True
            )
            selfie_segmentation = vision.ImageSegmenter.create_from_options(options)
            logger.info("MediaPipe Selfie Segmentation model initialized using Tasks API")
        except ImportError as e:
            logger.error(f"Failed to import MediaPipe Tasks API: {e}")
            raise ImportError(f"MediaPipe Tasks API not available: {e}. Please ensure mediapipe>=0.10.0 is installed: pip install --upgrade mediapipe")
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe: {e}")
            raise ImportError(f"MediaPipe initialization failed: {e}")
    return selfie_segmentation


def segment_person(frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract person mask from a video frame using MediaPipe Selfie Segmentation.
    
    Args:
        frame: Input frame as numpy array (BGR format from OpenCV)
        
    Returns:
        Tuple of (mask, segmented_person):
        - mask: Binary mask where 1 = person, 0 = background
        - segmented_person: Original frame with person pixels only
    """
    if selfie_segmentation is None:
        initialize_segmentation_model()
    
    try:
        from mediapipe.tasks.python.vision.core import image as mp_image_module
        
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create MediaPipe Image
        mp_image = mp_image_module.Image(
            image_format=mp_image_module.ImageFormat.SRGB, 
            data=rgb_frame
        )
        
        # Process frame using Tasks API
        results = selfie_segmentation.segment(mp_image)
        
        # Get confidence masks (first mask is typically the person/foreground)
        if results.confidence_masks and len(results.confidence_masks) > 0:
            # Get the first confidence mask (person mask)
            mask_np = results.confidence_masks[0].numpy_view()
            # #region agent log
            logger.info(f"DEBUG: mask_np shape={mask_np.shape}, dtype={mask_np.dtype}, min={mask_np.min():.3f}, max={mask_np.max():.3f}, mean={mask_np.mean():.3f}")
            # #endregion
            
            # Use threshold from configuration to avoid including uncertain edge pixels
            # This helps reduce halo effects
            threshold = get_config_value('SEGMENTATION_THRESHOLD', SEGMENTATION_THRESHOLD)
            mask_binary = (mask_np > threshold).astype(np.uint8) * 255
            # #region agent log
            logger.info(f"DEBUG: mask_binary min={mask_binary.min()}, max={mask_binary.max()}, mean={mask_binary.mean():.1f}, non-zero pixels={np.count_nonzero(mask_binary)}/{mask_binary.size}")
            # #endregion
            
            # Apply morphological operations to clean up the mask
            # First, close small holes
            close_kernel_size = get_config_value('MORPH_CLOSE_KERNEL_SIZE', MORPH_CLOSE_KERNEL_SIZE)
            kernel_close = np.ones((close_kernel_size, close_kernel_size), np.uint8)
            mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel_close)
            
            # Then, open to remove small noise
            open_kernel_size = get_config_value('MORPH_OPEN_KERNEL_SIZE', MORPH_OPEN_KERNEL_SIZE)
            kernel_open = np.ones((open_kernel_size, open_kernel_size), np.uint8)
            mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_OPEN, kernel_open)
            
            # Slightly erode the mask to avoid edge artifacts (reduces halo)
            erosion_kernel_size = get_config_value('EROSION_KERNEL_SIZE', EROSION_KERNEL_SIZE)
            erosion_iterations = get_config_value('EROSION_ITERATIONS', EROSION_ITERATIONS)
            kernel_erode = np.ones((erosion_kernel_size, erosion_kernel_size), np.uint8)
            mask_binary = cv2.erode(mask_binary, kernel_erode, iterations=erosion_iterations)
            
            # CRITICAL: Close any holes created by erosion (prevents blue spots)
            # This is essential when EROSION_ITERATIONS > 1
            post_erosion_close_size = get_config_value('POST_EROSION_CLOSE_KERNEL_SIZE', POST_EROSION_CLOSE_KERNEL_SIZE)
            kernel_close_post_erode = np.ones((post_erosion_close_size, post_erosion_close_size), np.uint8)
            mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel_close_post_erode)
            
            # Apply Gaussian blur to create smooth edges (feathering)
            blur_kernel_size = get_config_value('GAUSSIAN_BLUR_KERNEL_SIZE', GAUSSIAN_BLUR_KERNEL_SIZE)
            blur_sigma = get_config_value('GAUSSIAN_BLUR_SIGMA', GAUSSIAN_BLUR_SIGMA)
            mask_binary = cv2.GaussianBlur(mask_binary, (blur_kernel_size, blur_kernel_size), blur_sigma)
            
        else:
            # Fallback: create empty mask
            logger.warning("DEBUG: No confidence masks returned from segmentation")
            mask_binary = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.uint8)
        
        # Ensure mask is 3-channel for blending
        mask_3channel = cv2.merge([mask_binary, mask_binary, mask_binary])
        
        # #region agent log
        logger.info(f"DEBUG: mask_3channel after morph - min={mask_3channel.min()}, max={mask_3channel.max()}, mean={mask_3channel.mean():.1f}")
        # #endregion
        
        # Extract person pixels
        segmented_person = cv2.bitwise_and(frame, mask_3channel)
        
        return mask_3channel, segmented_person
        
    except Exception as e:
        logger.error(f"Error in segment_person: {e}")
        # Return empty mask on error
        mask_3channel = np.zeros_like(frame)
        return mask_3channel, frame


def apply_grayscale_filter(frame: np.ndarray) -> np.ndarray:
    """
    Apply grayscale filter to a frame.
    
    Args:
        frame: Input frame in BGR format
        
    Returns:
        Grayscale frame converted back to BGR (3-channel)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def apply_sepia_filter(frame: np.ndarray) -> np.ndarray:
    """
    Apply sepia tone filter to a frame.
    
    Args:
        frame: Input frame in BGR format
        
    Returns:
        Frame with sepia tone applied
    """
    # Sepia transformation matrix
    sepia_matrix = np.array([
        [0.272, 0.534, 0.131],
        [0.349, 0.686, 0.168],
        [0.393, 0.769, 0.189]
    ])
    
    # Apply sepia transformation
    sepia_frame = cv2.transform(frame, sepia_matrix)
    
    # Clip values to valid range [0, 255]
    sepia_frame = np.clip(sepia_frame, 0, 255).astype(np.uint8)
    
    return sepia_frame


def apply_blur_filter(frame: np.ndarray, blur_strength: int = 15) -> np.ndarray:
    """
    Apply Gaussian blur filter to a frame.
    
    Args:
        frame: Input frame in BGR format
        blur_strength: Kernel size for Gaussian blur (must be odd)
        
    Returns:
        Blurred frame
    """
    # Ensure blur_strength is odd
    if blur_strength % 2 == 0:
        blur_strength += 1
    
    return cv2.GaussianBlur(frame, (blur_strength, blur_strength), 0)


def apply_background_filter(
    frame: np.ndarray, 
    mask: np.ndarray, 
    filter_type: str = "grayscale"
) -> np.ndarray:
    """
    Apply a visual filter to the background only, keeping the person in full color.
    
    Args:
        frame: Original video frame in BGR format
        mask: Binary mask where 255 = person, 0 = background
        filter_type: Type of filter to apply ("grayscale", "sepia", "blur")
        
    Returns:
        Processed frame with filtered background and original person
    """
    # Normalize mask to 0-1 range for blending
    # The mask is already smoothed with Gaussian blur, so this creates smooth transitions
    mask_normalized = mask.astype(np.float32) / 255.0
    # #region agent log
    logger.info(f"DEBUG apply_background_filter: mask_normalized min={mask_normalized.min():.3f}, max={mask_normalized.max():.3f}, mean={mask_normalized.mean():.3f}, filter_type={filter_type}")
    # #endregion
    
    # Apply filter to entire frame
    if filter_type == "grayscale":
        filtered_frame = apply_grayscale_filter(frame)
    elif filter_type == "sepia":
        filtered_frame = apply_sepia_filter(frame)
    elif filter_type == "blur":
        filtered_frame = apply_blur_filter(frame)
    else:
        logger.warning(f"Unknown filter type: {filter_type}, defaulting to grayscale")
        filtered_frame = apply_grayscale_filter(frame)
    
    # #region agent log
    logger.info(f"DEBUG: filtered_frame shape={filtered_frame.shape}, dtype={filtered_frame.dtype}, mean={filtered_frame.mean():.1f}")
    logger.info(f"DEBUG: original frame mean={frame.mean():.1f}")
    # #endregion
    
    # Use smooth blending with the normalized mask
    # This creates a natural transition between person and filtered background
    result = (
        frame.astype(np.float32) * mask_normalized + 
        filtered_frame.astype(np.float32) * (1 - mask_normalized)
    )
    
    # #region agent log
    logger.info(f"DEBUG: result mean={result.mean():.1f}, min={result.min()}, max={result.max()}")
    # #endregion
    
    return result.astype(np.uint8)


def process_frame(frame_bytes: bytes, filter_type: str = "grayscale") -> Tuple[bytes, float]:
    """
    Main processing function that takes a frame as bytes and returns processed frame.
    
    Args:
        frame_bytes: Frame image as bytes (JPEG or PNG)
        filter_type: Type of filter to apply ("grayscale", "sepia", "blur")
        
    Returns:
        Tuple of (processed_frame_bytes, processing_time_ms):
        - processed_frame_bytes: Processed frame as JPEG bytes
        - processing_time_ms: Time taken to process in milliseconds
    """
    import time
    start_time = time.time()
    
    try:
        # Decode frame from bytes
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise ValueError("Failed to decode frame from bytes")
        
        # Segment person from background
        mask, _ = segment_person(frame)
        
        # Apply background filter
        processed_frame = apply_background_filter(frame, mask, filter_type)
        
        # Encode processed frame to JPEG bytes
        _, encoded_image = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        processed_bytes = encoded_image.tobytes()
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"Frame processed with {filter_type} filter in {processing_time:.2f}ms")
        
        return processed_bytes, processing_time
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        raise


def process_video(video_path: str, output_path: str, filter_type: str = "grayscale", progress_callback=None):
    """
    Process an entire video file, applying background filter to all frames.
    
    Args:
        video_path: Path to input video file
        output_path: Path to save processed video
        filter_type: Type of filter to apply
        progress_callback: Optional callback function(progress_percent) for progress updates
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Initialize segmentation model
        initialize_segmentation_model()
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Create video writer with H.264 codec (more compatible with browsers)
        # Try H.264 first, fallback to mp4v if not available
        fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            logger.warning("H.264 codec not available, trying mp4v")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            raise ValueError("Failed to create video writer. Check codec availability.")
        
        frame_count = 0
        
        logger.info(f"Processing video: {total_frames} frames at {fps} FPS")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Segment person and apply filter
            mask, _ = segment_person(frame)
            processed_frame = apply_background_filter(frame, mask, filter_type)
            
            # Write processed frame
            out.write(processed_frame)
            frame_count += 1
            
            # Update progress
            if progress_callback and frame_count % 10 == 0:  # Update every 10 frames
                progress = int((frame_count / total_frames) * 100)
                progress_callback(progress)
        
        # Cleanup
        cap.release()
        out.release()
        
        logger.info(f"Video processing complete: {frame_count} frames processed")
        return True, f"Successfully processed {frame_count} frames"
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        return False, str(e)