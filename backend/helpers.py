import logging
import ffmpeg
import os
import uuid
import cv2
import numpy as np
import requests
from typing import Tuple, Optional, List
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing
import pickle
from queue import Queue, Empty
import threading

# A lightweight face detection model (kept for backward compatibility)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# MediaPipe Selfie Segmentation
# Import will be done lazily in initialize_segmentation_model to handle import errors gracefully
selfie_segmentation = None
# Lock to protect thread-unsafe MediaPipe model access
_segmentation_lock = threading.Lock()

# Import segmentation configuration
from segmentation_config import (
    SEGMENTATION_THRESHOLD,
    MORPH_CLOSE_KERNEL_SIZE,
    MORPH_OPEN_KERNEL_SIZE,
    EROSION_KERNEL_SIZE,
    EROSION_ITERATIONS,
    POST_EROSION_CLOSE_KERNEL_SIZE,
    GAUSSIAN_BLUR_KERNEL_SIZE,
    GAUSSIAN_BLUR_SIGMA,
    MASK_EXPANSION_SCALE,
    TEMPORAL_ALPHA,
    FRAME_PROCESSING_WIDTH
)

# Runtime config overrides for testing (set via API)
# Use thread-local storage to prevent race conditions between concurrent requests
# Each thread (request handler or video processing thread) has its own config
_runtime_config_storage = threading.local()

def set_runtime_config(config_overrides: Optional[dict]):
    """Set runtime configuration overrides for testing.
    
    Thread-safe: Uses thread-local storage so each thread has its own config.
    This prevents race conditions where a config set in one request thread
    could affect concurrent video processing threads.
    
    Args:
        config_overrides: Dictionary with config keys and values to override.
                         If None, clears the config for this thread.
                         If empty dict {}, sets an empty config (no overrides).
    """
    if config_overrides is None:
        # Clear config for this thread
        if hasattr(_runtime_config_storage, 'config'):
            delattr(_runtime_config_storage, 'config')
    else:
        # Set config (even if empty dict - means no overrides but config is set)
        _runtime_config_storage.config = config_overrides.copy()

def get_config_value(key: str, default_value):
    """Get config value, using runtime override if available.
    
    Thread-safe: Reads from thread-local storage, so each thread sees only
    its own config overrides. Video processing threads that never set config
    will always use default values.
    
    Args:
        key: Configuration key to look up
        default_value: Default value to return if no override is set
        
    Returns:
        Override value if set for this thread, otherwise default_value
    """
    if hasattr(_runtime_config_storage, 'config'):
        config = _runtime_config_storage.config
        if config and key in config:
            return config[key]
    return default_value

        
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_temp_path():
    temp_dir = os.path.join(os.path.dirname(__file__), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    random_filename = f"temp_{str(uuid.uuid4())[:8]}"
    return os.path.join(temp_dir, random_filename)


def find_ffmpeg() -> Optional[str]:
    """
    Find FFmpeg executable in system PATH and common installation locations.
    
    Returns:
        Path to ffmpeg executable if found, None otherwise
    """
    import shutil
    import platform
    
    # First, check if ffmpeg is in PATH
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
    
    # Try ffmpeg.exe explicitly (Windows)
    if platform.system() == 'Windows':
        ffmpeg_path = shutil.which('ffmpeg.exe')
        if ffmpeg_path:
            return ffmpeg_path
        
        # Check common Windows installation locations
        common_paths = [
            os.path.join(os.environ.get('ProgramFiles', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.expanduser(os.path.join('~', 'ffmpeg', 'bin', 'ffmpeg.exe')),
        ]
        
        for path in common_paths:
            if path and os.path.exists(path):
                return path
    
    return None


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


def get_adaptive_blur_kernel(frame_height: int) -> int:
    """
    Calculate adaptive Gaussian blur kernel size based on frame resolution.
    
    Args:
        frame_height: Height of the frame in pixels
        
    Returns:
        Kernel size (always odd number)
    """
    # Determine resolution tier
    # Increased blur sizes for softer edge transitions
    if frame_height <= 480:
        kernel_size = 17  # Increased for softer edges
    elif frame_height <= 720:
        kernel_size = 21  # Increased for softer edges
    else:  # 1080p and above
        kernel_size = 25  # Increased for softer edges
    
    # Ensure kernel size is odd
    if kernel_size % 2 == 0:
        kernel_size += 1
    
    return kernel_size


def has_many_holes(mask: np.ndarray, threshold_ratio: float = 0.02) -> bool:
    """
    Fast detection if mask has many holes that need aggressive closing.
    Uses a lightweight approximation for performance.
    
    Args:
        mask: Binary mask (uint8, 0-255)
        threshold_ratio: Ratio of holes to total pixels to consider "many holes"
        
    Returns:
        True if mask has many holes, False otherwise
    """
    # Fast approximation: check if mask has many small gaps
    # Use morphological opening on inverted mask to detect small holes
    # This is much faster than full connected components analysis
    
    # Sample a smaller region for speed (check center region)
    h, w = mask.shape[:2]
    sample_h, sample_w = h // 2, w // 2
    start_h, start_w = h // 4, w // 4
    mask_sample = mask[start_h:start_h + sample_h, start_w:start_w + sample_w]
    
    # Quick check: count background pixels in sample
    # If there are many small isolated background regions, it likely has holes
    mask_inv_sample = 255 - mask_sample
    total_sample_pixels = mask_sample.size
    
    # Use a small opening to detect isolated background pixels (potential holes)
    kernel_small = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(mask_inv_sample, cv2.MORPH_OPEN, kernel_small)
    
    # Count isolated background pixels (potential holes)
    isolated_bg = np.sum(opened > 0)
    hole_ratio = isolated_bg / total_sample_pixels if total_sample_pixels > 0 else 0
    
    return hole_ratio > threshold_ratio


def expand_mask(mask: np.ndarray, scale: float = 1.05) -> np.ndarray:
    """
    Expand the segmentation mask to capture hair, shoulders, and edges.
    Uses conservative expansion to minimize background inclusion.
    
    Args:
        mask: Binary mask (uint8, 0-255)
        scale: Expansion scale (1.0 = no expansion, 1.05 = 5% expansion)
        
    Returns:
        Expanded mask
    """
    if scale <= 1.0:
        return mask
    
    # Calculate dilation kernel size based on scale
    # Use a more conservative calculation to minimize background inclusion
    # For scale 1.05, we want minimal expansion (only 2-3 pixels typically)
    h, w = mask.shape[:2]
    min_dim = min(h, w)
    # Moderate expansion: balanced multiplier for better edge coverage
    kernel_size = max(3, int(min_dim * (scale - 1.0) * 0.25))  # Increased from 0.2 to 0.25 for better coverage
    
    # Cap kernel size to prevent excessive expansion
    kernel_size = min(kernel_size, 6)  # Maximum 6x6 kernel (slightly increased from 5)
    
    # Ensure kernel size is odd
    if kernel_size % 2 == 0:
        kernel_size += 1
    
    # Dilate the mask with minimal iterations
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    expanded_mask = cv2.dilate(mask, kernel, iterations=1)
    
    return expanded_mask


def initialize_segmentation_model():
    """
    Initialize the MediaPipe Selfie Segmentation model using Tasks API.
    This should be called once at application startup.
    Thread-safe: uses a lock to prevent concurrent initialization.
    """
    global selfie_segmentation, _segmentation_lock
    with _segmentation_lock:
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


def segment_person(frame: np.ndarray, previous_mask: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract person mask from a video frame using MediaPipe Selfie Segmentation.
    Thread-safe: uses a lock to protect MediaPipe model access.
    
    Args:
        frame: Input frame as numpy array (BGR format from OpenCV)
        previous_mask: Optional previous frame mask for temporal smoothing (3-channel, float32 0-1)
        
    Returns:
        Tuple of (mask, segmented_person):
        - mask: Binary mask where 1 = person, 0 = background (3-channel, uint8 0-255)
        - segmented_person: Original frame with person pixels only
    """
    global selfie_segmentation, _segmentation_lock
    # Double-checked locking pattern: fast path check outside lock, initialization protected inside
    if selfie_segmentation is None:
        initialize_segmentation_model()
    
    try:
        from mediapipe.tasks.python.vision.core import image as mp_image_module
        
        # Store original frame dimensions
        original_height, original_width = frame.shape[:2]
        processing_width = get_config_value('FRAME_PROCESSING_WIDTH', FRAME_PROCESSING_WIDTH)
        
        # Resize frame if needed (only downscale, never upscale)
        frame_resized = frame
        resize_scale = 1.0
        if original_width > processing_width:
            resize_scale = processing_width / original_width
            new_height = int(original_height * resize_scale)
            frame_resized = cv2.resize(frame, (processing_width, new_height), interpolation=cv2.INTER_LINEAR)
            # Removed verbose logging - only log once per video, not per frame
        
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        
        # Create MediaPipe Image
        mp_image = mp_image_module.Image(
            image_format=mp_image_module.ImageFormat.SRGB, 
            data=rgb_frame
        )
        
        # Process frame using Tasks API - protected by lock for thread-safety
        # MediaPipe models are not thread-safe, so we must synchronize access
        with _segmentation_lock:
            results = selfie_segmentation.segment(mp_image)
        
        # Get confidence masks (first mask is typically the person/foreground)
        if results.confidence_masks and len(results.confidence_masks) > 0:
            # Get the first confidence mask (person mask)
            mask_np = results.confidence_masks[0].numpy_view()
            
            # Use threshold from configuration to avoid including uncertain edge pixels
            # Higher threshold = more conservative, reduces background inclusion
            threshold = get_config_value('SEGMENTATION_THRESHOLD', SEGMENTATION_THRESHOLD)
            mask_binary = (mask_np > threshold).astype(np.uint8) * 255
            
            # Apply morphological operations to clean up the mask FIRST
            # This refines the mask before any expansion to create tighter boundaries
            
            # CONDITIONAL OPTIMIZATION: Detect if mask needs aggressive processing
            needs_aggressive_processing = has_many_holes(mask_binary)
            
            # First, close small holes to get a solid mask
            # Use smaller kernel if mask is clean (faster), larger if it has many holes
            base_close_size = get_config_value('MORPH_CLOSE_KERNEL_SIZE', MORPH_CLOSE_KERNEL_SIZE)
            close_kernel_size = base_close_size if needs_aggressive_processing else max(5, base_close_size - 2)
            kernel_close = np.ones((close_kernel_size, close_kernel_size), np.uint8)
            mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel_close)
            
            # Then, open to remove small noise and isolated pixels
            # Use smaller kernel if mask is clean
            base_open_size = get_config_value('MORPH_OPEN_KERNEL_SIZE', MORPH_OPEN_KERNEL_SIZE)
            open_kernel_size = base_open_size if needs_aggressive_processing else max(3, base_open_size - 2)
            kernel_open = np.ones((open_kernel_size, open_kernel_size), np.uint8)
            mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_OPEN, kernel_open)
            
            # CRITICAL: Erode the mask to create tighter boundaries and reduce halo
            # This removes uncertain edge pixels that cause background bleed-through
            # ALWAYS use full erosion - this is critical for quality and halo reduction
            erosion_kernel_size = get_config_value('EROSION_KERNEL_SIZE', EROSION_KERNEL_SIZE)
            erosion_iterations = get_config_value('EROSION_ITERATIONS', EROSION_ITERATIONS)
            kernel_erode = np.ones((erosion_kernel_size, erosion_kernel_size), np.uint8)
            mask_binary = cv2.erode(mask_binary, kernel_erode, iterations=erosion_iterations)
            
            # CRITICAL: Close any holes created by erosion (prevents artifacts)
            # This is essential when EROSION_ITERATIONS > 1
            # Use smaller kernel if mask is clean, but ensure it's at least 3
            base_post_close_size = get_config_value('POST_EROSION_CLOSE_KERNEL_SIZE', POST_EROSION_CLOSE_KERNEL_SIZE)
            post_erosion_close_size = base_post_close_size if needs_aggressive_processing else max(3, base_post_close_size - 2)
            kernel_close_post_erode = np.ones((post_erosion_close_size, post_erosion_close_size), np.uint8)
            mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel_close_post_erode)
            
            # MINIMAL expansion AFTER refinement to capture hair/edges if needed
            # Only expand if scale > 1.0, and keep it minimal to avoid background inclusion
            expansion_scale = get_config_value('MASK_EXPANSION_SCALE', MASK_EXPANSION_SCALE)
            if expansion_scale > 1.0:
                # Use a more conservative expansion that only slightly extends the refined mask
                mask_binary = expand_mask(mask_binary, expansion_scale)
            
            # Apply adaptive Gaussian blur based on resolution (feathering)
            blur_kernel_size = get_adaptive_blur_kernel(mask_binary.shape[0])
            blur_sigma = get_config_value('GAUSSIAN_BLUR_SIGMA', GAUSSIAN_BLUR_SIGMA)
            mask_binary = cv2.GaussianBlur(mask_binary, (blur_kernel_size, blur_kernel_size), blur_sigma)
            
            # Scale mask back to original dimensions if frame was resized
            if resize_scale < 1.0:
                mask_binary = cv2.resize(mask_binary, (original_width, original_height), interpolation=cv2.INTER_LINEAR)
                # Re-normalize after resize (may have values outside 0-255)
                mask_binary = np.clip(mask_binary, 0, 255).astype(np.uint8)
            
            # Apply temporal smoothing if previous mask is provided
            if previous_mask is not None:
                # Convert previous_mask to single channel if needed
                if len(previous_mask.shape) == 3:
                    prev_mask_1ch = previous_mask[:, :, 0]
                else:
                    prev_mask_1ch = previous_mask
                
                # Ensure previous mask is same size as current
                if prev_mask_1ch.shape != mask_binary.shape:
                    prev_mask_1ch = cv2.resize(prev_mask_1ch, (mask_binary.shape[1], mask_binary.shape[0]), interpolation=cv2.INTER_LINEAR)
                
                # Convert previous_mask from float32 0-1 to uint8 0-255 if needed
                if prev_mask_1ch.dtype == np.float32 and prev_mask_1ch.max() <= 1.0:
                    prev_mask_1ch = (prev_mask_1ch * 255.0).astype(np.uint8)
                elif prev_mask_1ch.dtype != np.uint8:
                    prev_mask_1ch = np.clip(prev_mask_1ch, 0, 255).astype(np.uint8)
                
                # Apply exponential moving average
                temporal_alpha = get_config_value('TEMPORAL_ALPHA', TEMPORAL_ALPHA)
                mask_binary = (temporal_alpha * prev_mask_1ch.astype(np.float32) + 
                              (1 - temporal_alpha) * mask_binary.astype(np.float32)).astype(np.uint8)
            
        else:
            # Fallback: create empty mask
            logger.warning("DEBUG: No confidence masks returned from segmentation")
            mask_binary = np.zeros((original_height, original_width), dtype=np.uint8)
        
        # Ensure mask is 3-channel for blending
        mask_3channel = cv2.merge([mask_binary, mask_binary, mask_binary])
        
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
    Apply grayscale filter to a frame with slight brightness boost to reduce contrast.
    
    Args:
        frame: Input frame in BGR format
        
    Returns:
        Grayscale frame converted back to BGR (3-channel) with reduced contrast
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Add slight brightness boost to reduce contrast near edges
    gray = cv2.addWeighted(gray, 1.0, gray, 0, 10)  # Add 10 to brightness
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
    # Note: OpenCV uses BGR format, so columns correspond to [B, G, R] input channels
    # Swapped first and third columns from RGB matrix to match BGR input order
    sepia_matrix = np.array([
        [0.131, 0.534, 0.272],  # B' = 0.131*B + 0.534*G + 0.272*R
        [0.168, 0.686, 0.349],  # G' = 0.168*B + 0.686*G + 0.349*R
        [0.189, 0.769, 0.393]   # R' = 0.189*B + 0.769*G + 0.393*R
    ])
    
    # Apply sepia transformation
    sepia_frame = cv2.transform(frame, sepia_matrix)
    
    # Clip values to valid range [0, 255]
    sepia_frame = np.clip(sepia_frame, 0, 255).astype(np.uint8)
    
    return sepia_frame


def apply_blur_filter(frame: np.ndarray, blur_strength: int = 15) -> np.ndarray:
    """
    Apply Gaussian blur filter to a frame with very strong default strength for high visibility.
    
    Args:
        frame: Input frame in BGR format
        blur_strength: Kernel size for Gaussian blur (must be odd, default 15 for very strong effect)
        
    Returns:
        Blurred frame
    """
    # Use strong blur by default, but not too extreme
    if blur_strength == 15:  # Default value
        blur_strength = 51  # Strong blur, reduced from 101 for more moderate effect
    
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
    
    # Ensure mask_normalized is 3-channel for proper blending with BGR frame
    if len(mask_normalized.shape) == 2:
        mask_normalized = np.stack([mask_normalized, mask_normalized, mask_normalized], axis=2)
    elif mask_normalized.shape[2] == 1:
        mask_normalized = np.repeat(mask_normalized, 3, axis=2)
    
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
    
    # Use smooth blending with the normalized mask
    # This creates a natural transition between person and filtered background
    result = (
        frame.astype(np.float32) * mask_normalized + 
        filtered_frame.astype(np.float32) * (1.0 - mask_normalized)
    )
    
    return result.astype(np.uint8)


def apply_background_image(
    frame: np.ndarray,
    mask: np.ndarray,
    background_image: np.ndarray
) -> np.ndarray:
    """
    Composite person onto custom background image.
    
    Args:
        frame: Original video frame in BGR format
        mask: Binary mask where 255 = person, 0 = background (3-channel, uint8 0-255)
        background_image: Background image in BGR format
        
    Returns:
        Composited frame with person on custom background
    """
    # Normalize mask to 0-1 range for blending
    # The mask is already smoothed with Gaussian blur, so this creates smooth transitions
    mask_normalized = mask.astype(np.float32) / 255.0
    
    # Get frame dimensions
    frame_height, frame_width = frame.shape[:2]
    
    # Resize background image to match frame dimensions
    # Use crop-to-fit strategy to maintain aspect ratio while filling frame
    bg_height, bg_width = background_image.shape[:2]
    
    # Calculate scaling to cover frame (crop to fit)
    scale = max(frame_width / bg_width, frame_height / bg_height)
    new_bg_width = int(bg_width * scale)
    new_bg_height = int(bg_height * scale)
    
    # Resize background image
    bg_resized = cv2.resize(background_image, (new_bg_width, new_bg_height), interpolation=cv2.INTER_LINEAR)
    
    # Crop to frame dimensions (center crop)
    start_x = (new_bg_width - frame_width) // 2
    start_y = (new_bg_height - frame_height) // 2
    bg_cropped = bg_resized[start_y:start_y + frame_height, start_x:start_x + frame_width]
    
    # Ensure background is exactly frame size (safety check)
    if bg_cropped.shape[:2] != (frame_height, frame_width):
        bg_cropped = cv2.resize(background_image, (frame_width, frame_height), interpolation=cv2.INTER_LINEAR)
    
    # Ensure mask_normalized is 3-channel for proper blending
    if len(mask_normalized.shape) == 2:
        mask_normalized = np.stack([mask_normalized, mask_normalized, mask_normalized], axis=2)
    elif mask_normalized.shape[2] == 1:
        mask_normalized = np.repeat(mask_normalized, 3, axis=2)
    
    # Composite: person * mask + background * (1 - mask)
    # This creates smooth blending between person and background
    result = (
        frame.astype(np.float32) * mask_normalized + 
        bg_cropped.astype(np.float32) * (1 - mask_normalized)
    )
    
    return result.astype(np.uint8)


def process_single_frame_parallel(frame: np.ndarray, previous_mask: Optional[np.ndarray], 
                                  apply_background: bool, apply_filter: bool,
                                  filter_type: str, background_image: Optional[np.ndarray]) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Process a single frame - designed for parallel processing.
    
    Args:
        frame: Input frame
        previous_mask: Previous frame mask for temporal smoothing
        apply_background: Whether to apply background image
        apply_filter: Whether to apply filter
        filter_type: Type of filter to apply
        background_image: Background image if applying background
        
    Returns:
        Tuple of (processed_frame, final_mask)
    """
    if apply_background:
        mask, _ = segment_person(frame, previous_mask)
        mask_1ch = mask[:, :, 0].astype(np.float32) / 255.0
        processed_frame = apply_background_image(frame, mask, background_image)
        return processed_frame, mask_1ch
    elif apply_filter:
        mask, _ = segment_person(frame, previous_mask)
        mask_1ch = mask[:, :, 0].astype(np.float32) / 255.0
        processed_frame = apply_background_filter(frame, mask, filter_type)
        return processed_frame, mask_1ch
    else:
        processed_frame = frame
        if apply_background or apply_filter:
            mask, _ = segment_person(frame, previous_mask)
            mask_1ch = mask[:, :, 0].astype(np.float32) / 255.0
            return processed_frame, mask_1ch
        else:
            return processed_frame, None


def process_frame_batch(frames_data: List[Tuple[int, np.ndarray, float]], 
                        previous_mask: Optional[np.ndarray],
                        apply_background: bool, apply_filter: bool,
                        filter_type: str, background_image: Optional[np.ndarray]) -> List[Tuple[int, np.ndarray, Optional[np.ndarray]]]:
    """
    Process a batch of frames with optimized parallel processing while maintaining temporal smoothing.
    
    Uses parallel processing for frame preparation and I/O operations, but maintains
    sequential processing for segmentation to preserve temporal smoothing quality.
    
    Args:
        frames_data: List of (frame_index, frame, current_time) tuples
        previous_mask: Previous frame mask for temporal smoothing
        apply_background: Whether to apply background image
        apply_filter: Whether to apply filter
        filter_type: Type of filter
        background_image: Background image if applying
        
    Returns:
        List of (frame_index, processed_frame, final_mask) tuples in order
    """
    if not frames_data:
        return []
    
    results = []
    batch_previous_mask = previous_mask
    
    # Process frames sequentially to maintain temporal smoothing quality
    # The segmentation step requires the previous frame's mask, so we can't fully parallelize
    # However, we can optimize by pre-processing frames and using efficient numpy operations
    for frame_idx, frame, current_time in frames_data:
        # Process frame with temporal smoothing
        processed_frame, final_mask = process_single_frame_parallel(
            frame, batch_previous_mask, apply_background, apply_filter,
            filter_type, background_image
        )
        
        results.append((frame_idx, processed_frame, final_mask))
        batch_previous_mask = final_mask
    
    return results


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
        
        # Removed verbose per-frame logging for performance
        
        return processed_bytes, processing_time
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        raise


def process_video(video_path: str, output_path: str, filter_type: str = "grayscale", progress_callback=None, clip_start: float = None, clip_end: float = None, background_image: Optional[np.ndarray] = None):
    """
    Process an entire video file, applying background filter or background image to all frames with temporal smoothing.
    Optionally clip the video to a specific time range.
    
    Args:
        video_path: Path to input video file
        output_path: Path to save processed video
        filter_type: Type of filter to apply (None or "none" for clipping only, no filter)
        progress_callback: Optional callback function(progress_percent) for progress updates
        clip_start: Optional start time in seconds for clipping
        clip_end: Optional end time in seconds for clipping
        background_image: Optional background image in BGR format (numpy array). If provided, replaces filter.
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    cap = None
    out = None
    try:
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps if fps > 0 else 0
        
        # Handle clipping parameters
        clip_start_time = clip_start if clip_start is not None else 0.0
        clip_end_time = clip_end if clip_end is not None else video_duration
        
        # Validate clip times
        if clip_start_time < 0:
            clip_start_time = 0.0
        if clip_end_time > video_duration:
            clip_end_time = video_duration
        if clip_end_time <= clip_start_time:
            raise ValueError(f"Invalid clip range: start={clip_start_time}, end={clip_end_time}")
        
        # Calculate clip frame range
        clip_start_frame = int(clip_start_time * fps)
        clip_end_frame = int(clip_end_time * fps)
        clip_total_frames = clip_end_frame - clip_start_frame
        
        # Determine if we need to apply filters or background image
        apply_filter = filter_type is not None and filter_type not in ["none", ""]
        apply_background = background_image is not None
        
        # Log processing mode for debugging
        if apply_background:
            logger.info(f"Processing with background image: {background_image.shape if background_image is not None else 'None'}, clip: {clip_start_time:.2f}s - {clip_end_time:.2f}s")
        elif apply_filter:
            logger.info(f"Processing with filter: {filter_type}, clip: {clip_start_time:.2f}s - {clip_end_time:.2f}s")
        else:
            logger.info(f"Processing clipping only: {clip_start_time:.2f}s - {clip_end_time:.2f}s")
        
        # Initialize segmentation model if applying filters or background image
        if apply_filter or apply_background:
            initialize_segmentation_model()
        
        # Seek to clip start if needed
        if clip_start_time > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, clip_start_time * 1000)
        
        logger.info(f"Processing video: {clip_total_frames} frames (clip: {clip_start_time:.2f}s - {clip_end_time:.2f}s) at {fps} FPS, filter={filter_type}")
        
        # Check if input video has audio and extract it if present
        has_audio = False
        audio_temp_path = None
        import subprocess
        
        # Find FFmpeg using enhanced detection
        ffmpeg_path = find_ffmpeg()
        
        if not ffmpeg_path:
            logger.warning(
                "FFmpeg not found. Audio will not be preserved in output video.\n"
                "To enable audio preservation:\n"
                "1. Install FFmpeg from https://ffmpeg.org/download.html\n"
                "2. Add FFmpeg to your system PATH, or\n"
                "3. Install FFmpeg to a standard location (Program Files\\ffmpeg\\bin on Windows)"
            )
        else:
            logger.info(f"FFmpeg found at: {ffmpeg_path}")
            # Configure ffmpeg-python to use the found binary path
            # ffmpeg-python will use PATH by default, but we can set it explicitly if needed
            import os as os_module
            # Add ffmpeg directory to PATH temporarily if not already there
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            if ffmpeg_dir not in os_module.environ.get('PATH', ''):
                os_module.environ['PATH'] = ffmpeg_dir + os.pathsep + os_module.environ.get('PATH', '')
            
            try:
                # Try using ffmpeg-python library first (it will now find FFmpeg in PATH)
                try:
                    probe = ffmpeg.probe(video_path)
                    audio_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']
                    has_audio = len(audio_streams) > 0
                except Exception as lib_error:
                    # Fallback to subprocess if ffmpeg-python fails
                    logger.warning(f"ffmpeg-python library failed, using subprocess fallback: {lib_error}")
                    try:
                        result = subprocess.run(
                            [ffmpeg_path, '-i', video_path, '-hide_banner'],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        # Check stderr for audio stream info
                        has_audio = 'Audio:' in result.stderr or 'Stream #0:1' in result.stderr
                    except Exception as subprocess_error:
                        logger.warning(f"Subprocess fallback also failed: {subprocess_error}")
                        has_audio = False
                
                if has_audio:
                    # Extract audio to temporary file
                    audio_temp_path = get_temp_path() + "_audio.aac"
                    try:
                        # Use clip parameters if provided
                        audio_clip_start = clip_start if clip_start is not None else 0.0
                        audio_clip_end = clip_end if clip_end is not None else (total_frames / fps if fps > 0 else 0)
                        
                        # Try ffmpeg-python first
                        try:
                            if audio_clip_start > 0 or (audio_clip_end < (total_frames / fps if fps > 0 else 0)):
                                # Extract clipped audio
                                (
                                    ffmpeg
                                    .input(video_path, ss=audio_clip_start, t=audio_clip_end - audio_clip_start)
                                    .output(audio_temp_path, acodec='copy', **{'map': '0:a'})
                                    .overwrite_output()
                                    .run(capture_stdout=True, capture_stderr=True, quiet=True)
                                )
                            else:
                                # Extract full audio
                                (
                                    ffmpeg
                                    .input(video_path)
                                    .output(audio_temp_path, acodec='copy', **{'map': '0:a'})
                                    .overwrite_output()
                                    .run(capture_stdout=True, capture_stderr=True, quiet=True)
                                )
                        except Exception as lib_error:
                            # Fallback to subprocess
                            logger.warning(f"Audio extraction via ffmpeg-python failed, using subprocess: {lib_error}")
                            if audio_clip_start > 0 or (audio_clip_end < (total_frames / fps if fps > 0 else 0)):
                                duration = audio_clip_end - audio_clip_start
                                subprocess.run(
                                    [ffmpeg_path, '-i', video_path, '-ss', str(audio_clip_start), 
                                     '-t', str(duration), '-vn', '-acodec', 'copy', 
                                     '-map', '0:a', audio_temp_path, '-y'],
                                    check=True,
                                    capture_output=True,
                                    timeout=60
                                )
                            else:
                                subprocess.run(
                                    [ffmpeg_path, '-i', video_path, '-vn', '-acodec', 'copy', 
                                     '-map', '0:a', audio_temp_path, '-y'],
                                    check=True,
                                    capture_output=True,
                                    timeout=60
                                )
                        
                        if os.path.exists(audio_temp_path) and os.path.getsize(audio_temp_path) > 0:
                            logger.info(f"Audio extracted successfully to {audio_temp_path}")
                        else:
                            logger.warning("Audio extraction completed but file is missing or empty")
                            has_audio = False
                            audio_temp_path = None
                    except Exception as e:
                        logger.warning(f"Failed to extract audio: {e}")
                        has_audio = False
                        audio_temp_path = None
            except Exception as e:
                logger.warning(f"Could not check video for audio: {e}")
        
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
        previous_mask = None  # Initialize temporal smoothing state
        current_time = clip_start_time
        
        # Batch processing for parallelization
        # Process frames in batches to enable parallel processing while maintaining temporal smoothing
        BATCH_SIZE = max(10, min(60, multiprocessing.cpu_count() * 5))  # Adaptive batch size
        frame_buffer = []
        
        logger.info(f"Using batch processing with batch size: {BATCH_SIZE} (CPU cores: {multiprocessing.cpu_count()})")
        
        # Use producer-consumer pattern with separate threads for I/O
        # This allows reading and writing to happen in parallel with processing
        frame_queue = Queue(maxsize=BATCH_SIZE * 2)  # Buffer for read frames
        processed_queue = Queue(maxsize=BATCH_SIZE * 2)  # Buffer for processed frames
        read_done = threading.Event()
        write_done = threading.Event()
        processing_error = [None]  # Use list to allow modification from nested function
        
        # Producer thread: Read frames ahead
        def read_frames():
            try:
                local_frame_count = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    local_current_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    if local_current_time >= clip_end_time:
                        break
                    
                    frame_queue.put((local_frame_count, frame, local_current_time))
                    local_frame_count += 1
            except Exception as e:
                processing_error[0] = e
                logger.error(f"Error reading frames: {e}")
            finally:
                read_done.set()
        
        # Consumer thread: Write processed frames
        def write_frames():
            try:
                local_frame_count = 0
                expected_frame = 0
                frame_dict = {}  # Buffer for out-of-order frames
                sentinel_received = False
                
                while True:
                    # Check if we're done: write_done is set, queue is empty, and we've written all frames
                    if write_done.is_set() and processed_queue.empty() and sentinel_received:
                        # Write any remaining buffered frames
                        while expected_frame in frame_dict:
                            out.write(frame_dict.pop(expected_frame))
                            expected_frame += 1
                            local_frame_count += 1
                        break
                    
                    try:
                        item = processed_queue.get(timeout=0.1)
                        if item is None:  # Sentinel value
                            sentinel_received = True
                            continue
                        
                        frame_idx, processed_frame = item
                        frame_dict[frame_idx] = processed_frame
                        
                        # Write frames in order
                        while expected_frame in frame_dict:
                            out.write(frame_dict.pop(expected_frame))
                            expected_frame += 1
                            local_frame_count += 1
                            
                            # Update progress
                            if progress_callback and local_frame_count % 10 == 0:
                                progress = int((local_frame_count / clip_total_frames) * 100) if clip_total_frames > 0 else 0
                                progress = min(100, max(0, progress))
                                progress_callback(progress)
                    except Empty:
                        # Timeout waiting for queue item - continue loop
                        continue
                    except Exception as e:
                        # Log unexpected errors but continue processing
                        logger.warning(f"Unexpected error in write_frames loop: {e}")
                        continue
            except Exception as e:
                processing_error[0] = e
                logger.error(f"Error writing frames: {e}")
        
        # Start I/O threads
        read_thread = threading.Thread(target=read_frames, daemon=True)
        write_thread = threading.Thread(target=write_frames, daemon=True)
        read_thread.start()
        write_thread.start()
        
        # Main processing loop: Process frames in batches
        while not read_done.is_set() or not frame_queue.empty():
            # Check for errors
            if processing_error[0]:
                raise processing_error[0]
            
            # Collect batch of frames
            frame_buffer = []
            try:
                while len(frame_buffer) < BATCH_SIZE:
                    if read_done.is_set() and frame_queue.empty():
                        break
                    frame_data = frame_queue.get(timeout=0.1)
                    frame_buffer.append(frame_data)
            except Empty:
                # Timeout waiting for queue item - continue to check if we should continue outer loop
                pass
            except Exception as e:
                # Log unexpected errors
                logger.warning(f"Unexpected error collecting frame batch: {e}")
                pass
            
            if not frame_buffer:
                continue
            
            # Process batch
            batch_results = process_frame_batch(
                frame_buffer, previous_mask, apply_background, apply_filter,
                filter_type, background_image
            )
            
            # Send processed frames to write queue
            for frame_idx, processed_frame, final_mask in batch_results:
                processed_queue.put((frame_idx, processed_frame))
                previous_mask = final_mask
                frame_count += 1
        
        # Signal write thread to finish by sending sentinel
        processed_queue.put(None)
        write_done.set()
        write_thread.join(timeout=30)
        
        # Wait for read thread
        read_thread.join(timeout=10)
        
        # Check for errors
        if processing_error[0]:
            raise processing_error[0]
        
        # Mux audio back into video if audio was extracted
        if has_audio and audio_temp_path and os.path.exists(audio_temp_path) and ffmpeg_path:
            try:
                # Create temporary output file for muxed video
                temp_muxed_path = output_path + ".muxed.mp4"
                
                # Try ffmpeg-python first
                try:
                    video_input = ffmpeg.input(output_path)
                    audio_input = ffmpeg.input(audio_temp_path)
                    
                    (
                        ffmpeg
                        .output(video_input, audio_input, temp_muxed_path, 
                               vcodec='copy', acodec='aac', 
                               **{'shortest': None})  # Use shortest stream to avoid sync issues
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True, quiet=True)
                    )
                except Exception as lib_error:
                    # Fallback to subprocess
                    logger.warning(f"Audio muxing via ffmpeg-python failed, using subprocess: {lib_error}")
                    subprocess.run(
                        [ffmpeg_path, '-i', output_path, '-i', audio_temp_path,
                         '-c:v', 'copy', '-c:a', 'aac', '-shortest', 
                         temp_muxed_path, '-y'],
                        check=True,
                        capture_output=True,
                        timeout=120
                    )
                
                # Replace original output with muxed version
                if os.path.exists(temp_muxed_path):
                    os.replace(temp_muxed_path, output_path)
                    logger.info("Audio successfully muxed into output video")
                else:
                    logger.warning("Muxed video file not created")
            except Exception as e:
                logger.error(f"Failed to mux audio: {e}")
            finally:
                # Clean up temporary audio file
                if audio_temp_path and os.path.exists(audio_temp_path):
                    try:
                        os.remove(audio_temp_path)
                    except OSError:
                        # Ignore errors during cleanup (file may already be deleted)
                        pass
        elif has_audio and not ffmpeg_path:
            logger.warning("Audio was detected but FFmpeg is not available. Audio will not be included in output.")
        
        logger.info(f"Video processing complete: {frame_count} frames processed")
        return True, f"Successfully processed {frame_count} frames"
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        return False, str(e)
    finally:
        # Always release resources to prevent file handle leaks
        if cap is not None:
            try:
                cap.release()
            except Exception as e:
                logger.warning(f"Error releasing VideoCapture: {e}")
        if out is not None:
            try:
                out.release()
            except Exception as e:
                logger.warning(f"Error releasing VideoWriter: {e}")