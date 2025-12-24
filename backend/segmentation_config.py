# ============================================================================
# SEGMENTATION MASK PROCESSING CONFIGURATION
# ============================================================================
# Based on research and production best practices for MediaPipe segmentation
# All parameters can be modified here for easy testing and tuning

# Mask threshold: 
# - 0.5-0.55: Standard for production systems (balanced accuracy/coverage)
# - 0.6-0.65: More conservative, better for removing edge artifacts
# - 0.67-0.68: Very conservative, excellent for tight edges
# - 0.7+: Too aggressive, may miss edges and create artifacts
# Current: 0.67 (increased to further reduce edge artifacts and background bleed-through)
SEGMENTATION_THRESHOLD = 0.67

# Morphological operations - used to clean up the mask
# Close kernel size: Fills holes in the mask
# - 5-7: Standard range for most applications
# - 9+: Only for very noisy masks, may over-expand
# Current: 9 (selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60)
MORPH_CLOSE_KERNEL_SIZE = 9  # Must be odd number

# Open kernel size: Removes noise
# - 3-5: Standard range
MORPH_OPEN_KERNEL_SIZE = 5  # Must be odd number

# Erosion: Reduces mask size to avoid edge artifacts (halo effect)
# - 1-2 iterations: Standard, minimal artifacts
# - 3+: Aggressive, requires post-erosion closing
# - 4: Good balance between tight boundaries and softer edges
# - 5: Very aggressive, creates very tight boundaries
# Current: 4 (reduced from 5 to create slightly softer edges)
EROSION_KERNEL_SIZE = 3  # Must be odd number
EROSION_ITERATIONS = 4  # Reduced from 5 to create slightly softer edges

# Post-erosion closing: CRITICAL - Fills holes created by erosion
# - 3-5: Standard range
# - Essential when EROSION_ITERATIONS > 1
# Current: 5 (selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60)
POST_EROSION_CLOSE_KERNEL_SIZE = 5  # Must be odd number

# Gaussian blur: Creates smooth edge transitions (feathering)
# - 9-15: Standard range for smooth transitions
# - 15-25: Good for very smooth, soft edges
# - Increased blur for softer edge transitions
# NOTE: This is now adaptive based on frame resolution (see get_adaptive_blur_kernel)
# Kept for backward compatibility, but will be overridden by adaptive calculation
GAUSSIAN_BLUR_KERNEL_SIZE = 15  # Increased for softer edges
GAUSSIAN_BLUR_SIGMA = 0  # 0 = auto-calculated based on kernel size

# Mask expansion: Expands the segmentation mask to capture hair, shoulders, edges
# - 1.0: No expansion, tightest boundaries
# - 1.02-1.05: Minimal expansion for hair/edges
# - 1.05-1.15: Standard range for segmentation masks
# - Higher values capture more area but may include background
# Current: 1.04 (4% expansion, increased for better edge coverage while keeping it moderate)
MASK_EXPANSION_SCALE = 1.04

# Temporal smoothing: Reduces flicker by averaging masks across frames
# - 0.5-0.8: Standard range
# - 0.7: Good balance (70% previous mask, 30% current)
# - Higher values = more smoothing but slower response to movement
# Current: 0.7
TEMPORAL_ALPHA = 0.7

# Frame processing width: Resize frames to this width before processing
# - 640: Good balance between quality and performance
# - Only applies if original width > this value (no upscaling)
# - Masks are scaled back to original dimensions after processing
# Current: 640
FRAME_PROCESSING_WIDTH = 640
# ============================================================================

