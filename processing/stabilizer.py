"""
Video stabilization via pixel tracking.

Uses Lucas-Kanade optical flow to track a user-selected point across frames
and computes translation offsets to stabilize the video around that anchor.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List, Callable


@dataclass
class StabilizationSettings:
    """Settings for video stabilization."""
    enabled: bool = False
    tracking_point: Optional[Tuple[int, int]] = None  # (x, y) point to track
    border_mode: str = "transparent"  # "transparent", "replicate", "crop"
    smoothing: float = 0.0  # Future: trajectory smoothing (0 = raw, 1 = max smooth)


class PointStabilizer:
    """
    Stabilizes video by tracking a point and compensating for its movement.
    
    Usage:
        1. Create stabilizer with settings
        2. Call analyze_video() to compute offsets (first pass)
        3. Call get_stabilized_frame() for each frame (second pass)
    """
    
    def __init__(self, settings: Optional[StabilizationSettings] = None):
        self.settings = settings or StabilizationSettings()
        
        # Tracking state
        self._offsets: List[Tuple[float, float]] = []  # Per-frame (dx, dy) offsets
        self._tracking_positions: List[Tuple[float, float]] = []  # Tracked point per frame
        self._analyzed = False
        self._reference_point: Optional[Tuple[float, float]] = None
        
        # Lucas-Kanade optical flow parameters
        self._lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )
    
    @property
    def is_analyzed(self) -> bool:
        return self._analyzed
    
    @property
    def frame_count(self) -> int:
        return len(self._offsets)
    
    def set_tracking_point(self, x: int, y: int):
        """Set the anchor point to track."""
        self.settings.tracking_point = (x, y)
        self._reset_analysis()
    
    def _reset_analysis(self):
        """Clear analysis data."""
        self._offsets = []
        self._tracking_positions = []
        self._analyzed = False
        self._reference_point = None
    
    def analyze_video(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """
        First pass: Analyze video and compute stabilization offsets.
        
        Args:
            video_path: Path to video file
            progress_callback: Callback(progress: 0-1, status_message)
            
        Returns:
            True if analysis successful
        """
        if not self.settings.tracking_point:
            return False
        
        self._reset_analysis()
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Read first frame
            ret, prev_frame = cap.read()
            if not ret:
                return False
            
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            
            # Initialize tracking point
            x, y = self.settings.tracking_point
            self._reference_point = (float(x), float(y))
            prev_point = np.array([[x, y]], dtype=np.float32)
            
            # Store first frame offset (0, 0)
            self._offsets.append((0.0, 0.0))
            self._tracking_positions.append(self._reference_point)
            
            frame_idx = 1
            current_point = prev_point.copy()
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Track point using optical flow
                new_point, status, _ = cv2.calcOpticalFlowPyrLK(
                    prev_gray, gray, current_point, None, **self._lk_params
                )
                
                if status[0][0] == 1:
                    # Tracking successful
                    tracked_x, tracked_y = new_point[0]
                    self._tracking_positions.append((tracked_x, tracked_y))
                    
                    # Compute offset from reference
                    dx = self._reference_point[0] - tracked_x
                    dy = self._reference_point[1] - tracked_y
                    self._offsets.append((dx, dy))
                    
                    current_point = new_point
                else:
                    # Tracking lost - use previous offset
                    if self._offsets:
                        self._offsets.append(self._offsets[-1])
                        self._tracking_positions.append(self._tracking_positions[-1])
                    else:
                        self._offsets.append((0.0, 0.0))
                        self._tracking_positions.append(self._reference_point)
                
                prev_gray = gray
                frame_idx += 1
                
                if progress_callback and frame_idx % 10 == 0:
                    progress = frame_idx / total_frames
                    progress_callback(progress * 0.5, "Analyzing motion...")  # 0-50%
            
            self._analyzed = True
            return True
            
        finally:
            cap.release()
    
    def get_offset(self, frame_idx: int) -> Tuple[float, float]:
        """Get the stabilization offset for a specific frame."""
        if not self._analyzed or frame_idx >= len(self._offsets):
            return (0.0, 0.0)
        return self._offsets[frame_idx]
    
    def get_tracked_position(self, frame_idx: int) -> Optional[Tuple[float, float]]:
        """Get the tracked point position for a specific frame."""
        if not self._analyzed or frame_idx >= len(self._tracking_positions):
            return self.settings.tracking_point
        return self._tracking_positions[frame_idx]
    
    def apply_stabilization(
        self,
        frame: np.ndarray,
        frame_idx: int
    ) -> np.ndarray:
        """
        Apply stabilization offset to a frame.
        
        Args:
            frame: BGR or BGRA frame
            frame_idx: Frame index (0-based)
            
        Returns:
            Stabilized frame (same format as input, but BGRA if transparent border)
        """
        if not self._analyzed or frame_idx >= len(self._offsets):
            return frame
        
        dx, dy = self._offsets[frame_idx]
        
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return frame  # No significant offset
        
        h, w = frame.shape[:2]
        has_alpha = frame.shape[2] == 4 if len(frame.shape) > 2 else False
        
        # Build translation matrix
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        
        # Determine border mode
        if self.settings.border_mode == "transparent":
            # Convert to BGRA if needed for transparent borders
            if not has_alpha:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            
            # Apply translation with transparent border
            stabilized = cv2.warpAffine(
                frame, M, (w, h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)
            )
        elif self.settings.border_mode == "replicate":
            stabilized = cv2.warpAffine(
                frame, M, (w, h),
                borderMode=cv2.BORDER_REPLICATE
            )
        else:  # crop or unknown
            stabilized = cv2.warpAffine(
                frame, M, (w, h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0) if has_alpha else (0, 0, 0)
            )
        
        return stabilized
    
    def preview_stabilization(
        self,
        frame: np.ndarray,
        frame_idx: int,
        draw_tracking_point: bool = True,
        first_frame: np.ndarray = None
    ) -> np.ndarray:
        """
        Create a preview of stabilization for a single frame.
        
        Computes the offset on-the-fly by tracking from first_frame (if provided)
        or uses pre-computed offsets if analysis was done.
        
        Args:
            frame: BGR frame
            frame_idx: Frame index
            draw_tracking_point: Whether to draw a marker at the tracking point
            first_frame: First frame of video for on-the-fly tracking
            
        Returns:
            Preview frame with stabilization applied
        """
        result = frame.copy()
        
        if not self.settings.tracking_point:
            return result
        
        dx, dy = 0.0, 0.0
        tracked_pos = self.settings.tracking_point
        
        # Use pre-computed offset if available
        if self._analyzed and frame_idx < len(self._offsets):
            dx, dy = self._offsets[frame_idx]
            tracked_pos = self._tracking_positions[frame_idx]
        elif first_frame is not None and frame_idx > 0:
            # Compute offset on-the-fly by tracking from first frame
            offset, pos = self._track_single_frame(first_frame, frame)
            if offset:
                dx, dy = offset
                tracked_pos = pos
        
        # Apply stabilization offset
        if abs(dx) > 0.5 or abs(dy) > 0.5:
            h, w = result.shape[:2]
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            
            # Convert to BGRA for transparent borders
            if len(result.shape) < 3 or result.shape[2] == 3:
                result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
            
            result = cv2.warpAffine(
                result, M, (w, h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)  # Transparent
            )
        
        # Draw tracking point marker
        if draw_tracking_point and tracked_pos:
            x, y = int(tracked_pos[0]), int(tracked_pos[1])
            
            # Draw crosshair marker
            color = (0, 255, 255)  # Yellow
            thickness = 2
            size = 15
            
            cv2.line(result, (x - size, y), (x + size, y), color, thickness)
            cv2.line(result, (x, y - size), (x, y + size), color, thickness)
            cv2.circle(result, (x, y), 8, color, thickness)
        
        return result
    
    def _track_single_frame(
        self,
        first_frame: np.ndarray,
        current_frame: np.ndarray
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """
        Track the point from first_frame to current_frame.
        
        Returns:
            Tuple of (offset (dx, dy), tracked_position (x, y)) or (None, None) if tracking failed
        """
        if not self.settings.tracking_point:
            return None, None
        
        x, y = self.settings.tracking_point
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        
        # Track point
        prev_point = np.array([[x, y]], dtype=np.float32)
        new_point, status, _ = cv2.calcOpticalFlowPyrLK(
            gray1, gray2, prev_point, None, **self._lk_params
        )
        
        if status[0][0] == 1:
            tracked_x, tracked_y = new_point[0]
            dx = x - tracked_x
            dy = y - tracked_y
            return (dx, dy), (tracked_x, tracked_y)
        
        return None, None
    
    def reset(self):
        """Fully reset stabilizer state."""
        self.settings.tracking_point = None
        self._reset_analysis()
