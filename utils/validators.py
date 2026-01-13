"""
Input validation utilities.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

SUPPORTED_VIDEO_FORMATS = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")
SUPPORTED_OUTPUT_FORMATS = (".webm",)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_video_path(path: str) -> Path:
    """
    Validate that a video file exists and has a supported format.
    
    Args:
        path: Path to the video file
        
    Returns:
        Validated Path object
        
    Raises:
        ValidationError: If validation fails
    """
    if not path:
        raise ValidationError("No video file specified")
    
    video_path = Path(path)
    
    if not video_path.exists():
        raise ValidationError(f"Video file not found: {path}")
    
    if not video_path.is_file():
        raise ValidationError(f"Path is not a file: {path}")
    
    if video_path.suffix.lower() not in SUPPORTED_VIDEO_FORMATS:
        raise ValidationError(
            f"Unsupported video format: {video_path.suffix}\n"
            f"Supported formats: {', '.join(SUPPORTED_VIDEO_FORMATS)}"
        )
    
    return video_path


def validate_output_path(path: str) -> Path:
    """
    Validate output path for saving.
    
    Args:
        path: Output path
        
    Returns:
        Validated Path object
        
    Raises:
        ValidationError: If validation fails
    """
    if not path:
        raise ValidationError("No output path specified")
    
    output_path = Path(path)
    
    # Check directory exists or can be created
    parent = output_path.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValidationError(f"Cannot create output directory: {e}")
    
    # Check write permissions
    if not os.access(parent, os.W_OK):
        raise ValidationError(f"No write permission for: {parent}")
    
    # Validate extension
    if output_path.suffix.lower() not in SUPPORTED_OUTPUT_FORMATS:
        raise ValidationError(
            f"Output must be WebM format for transparency support.\n"
            f"Got: {output_path.suffix}"
        )
    
    return output_path


def validate_hsv_range(
    h_min: int, h_max: int,
    s_min: int, s_max: int,
    v_min: int, v_max: int
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """
    Validate HSV color range values.
    
    Returns:
        Tuple of (lower_bound, upper_bound) as (H, S, V) tuples
        
    Raises:
        ValidationError: If values are out of range
    """
    # Hue: 0-179 in OpenCV
    if not (0 <= h_min <= 179):
        raise ValidationError(f"H min must be 0-179, got: {h_min}")
    if not (0 <= h_max <= 179):
        raise ValidationError(f"H max must be 0-179, got: {h_max}")
    
    # Saturation and Value: 0-255
    if not (0 <= s_min <= 255):
        raise ValidationError(f"S min must be 0-255, got: {s_min}")
    if not (0 <= s_max <= 255):
        raise ValidationError(f"S max must be 0-255, got: {s_max}")
    if not (0 <= v_min <= 255):
        raise ValidationError(f"V min must be 0-255, got: {v_min}")
    if not (0 <= v_max <= 255):
        raise ValidationError(f"V max must be 0-255, got: {v_max}")
    
    return ((h_min, s_min, v_min), (h_max, s_max, v_max))


def validate_crop_region(
    x: int, y: int, width: int, height: int,
    frame_width: int, frame_height: int
) -> Tuple[int, int, int, int]:
    """
    Validate and clamp crop region to frame bounds.
    
    Returns:
        Validated (x, y, width, height) tuple
    """
    # Clamp to valid ranges
    x = max(0, min(x, frame_width - 1))
    y = max(0, min(y, frame_height - 1))
    
    # Ensure minimum size of 1
    width = max(1, min(width, frame_width - x))
    height = max(1, min(height, frame_height - y))
    
    return (x, y, width, height)


def validate_feather_amount(feather: int) -> int:
    """Validate feather amount (0-20 pixels)."""
    return max(0, min(20, feather))


def validate_spill_suppression(amount: float) -> float:
    """Validate spill suppression amount (0.0-1.0)."""
    return max(0.0, min(1.0, amount))
