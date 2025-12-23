# ============================================================================
# SEGMENTATION MASK PROCESSING CONFIGURATION
# ============================================================================
# Based on research and production best practices for MediaPipe segmentation
# All parameters can be modified here for easy testing and tuning

# Mask threshold: 
# - 0.5-0.55: Standard for production systems (balanced accuracy/coverage)
# - 0.6-0.65: More conservative, better for removing edge artifacts
# - 0.7+: Too aggressive, may miss edges and create artifacts
# Current: 0.6 (selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60)
SEGMENTATION_THRESHOLD = 0.6

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
# - 5+: Very aggressive, likely to create holes (blue spots)
# Current: 3 (selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60)
EROSION_KERNEL_SIZE = 3  # Must be odd number
EROSION_ITERATIONS = 3  # Selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60

# Post-erosion closing: CRITICAL - Fills holes created by erosion
# - 3-5: Standard range
# - Essential when EROSION_ITERATIONS > 1
# Current: 5 (selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60)
POST_EROSION_CLOSE_KERNEL_SIZE = 5  # Must be odd number

# Gaussian blur: Creates smooth edge transitions (feathering)
# - 9-15: Standard range for smooth transitions
# - 15: Good for very smooth edges
# Current: 13 (selected from testing: config_ERO3_GAU13_MOR9_POS5_SEG60)
GAUSSIAN_BLUR_KERNEL_SIZE = 13  # Must be odd number
GAUSSIAN_BLUR_SIGMA = 0  # 0 = auto-calculated based on kernel size
# ============================================================================

