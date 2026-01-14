"""
Video stabilization via object boundary tracking.

Uses template matching to track a user-selected bounding box across frames
and computes translation offsets to stabilize the video around that anchor region.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List, Callable


@dataclass
class StabilizationSettings:
    """Settings for video stabilization."""
    enabled: bool = False
    bounding_box: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h) region to track
    reference_frame_idx: int = 0  # Frame index where the bounding box was selected
    border_mode: str = "transparent"  # "transparent", "replicate", "crop"
    smoothing: float = 0.0  # Future: trajectory smoothing (0 = raw, 1 = max smooth)
    match_threshold: float = 0.5  # Tracking confidence threshold (0.0-1.0)
    search_margin: int = 50  # Pixels to search around last position
    
    @property
    def tracking_point(self) -> Optional[Tuple[int, int]]:
        """Get the center point of the bounding box for backward compatibility."""
        if self.bounding_box:
            x, y, w, h = self.bounding_box
            return (x + w // 2, y + h // 2)
        return None


class PointStabilizer:
    """
    Stabilizes video by tracking a bounding box and compensating for its movement.
    
    Uses template matching to track the selected region across frames,
    with the bounding box center as the reference point for stabilization offsets.
    
    Usage:
        1. Create stabilizer with settings
        2. Call set_bounding_box() to define the region to track
        3. Call analyze_video() to compute offsets (first pass)
        4. Call get_stabilized_frame() for each frame (second pass)
    """
    
    def __init__(self, settings: Optional[StabilizationSettings] = None):
        self.settings = settings or StabilizationSettings()
        
        # Tracking state
        self._offsets: List[Tuple[float, float]] = []  # Per-frame (dx, dy) offsets
        self._tracking_boxes: List[Tuple[int, int, int, int]] = []  # Tracked box per frame
        self._analyzed = False
        self._reference_center: Optional[Tuple[float, float]] = None
        self._template: Optional[np.ndarray] = None  # Template image for matching
    
    @property
    def is_analyzed(self) -> bool:
        return self._analyzed
    
    @property
    def frame_count(self) -> int:
        return len(self._offsets)
    
    def set_bounding_box(self, x: int, y: int, w: int, h: int, reference_frame_idx: int = 0):
        """Set the bounding box region to track.
        
        Args:
            x, y, w, h: Bounding box coordinates
            reference_frame_idx: Frame index where the box was selected
        """
        self.settings.bounding_box = (x, y, w, h)
        self.settings.reference_frame_idx = reference_frame_idx
        self._reset_analysis()
    
    def set_tracking_point(self, x: int, y: int):
        """
        Set tracking using a point (creates a default-sized bounding box).
        For backward compatibility with point-based selection.
        """
        # Create a 50x50 box centered on the point
        box_size = 50
        box_x = max(0, x - box_size // 2)
        box_y = max(0, y - box_size // 2)
        self.set_bounding_box(box_x, box_y, box_size, box_size)
    
    def _reset_analysis(self):
        """Clear analysis data."""
        self._offsets = []
        self._tracking_boxes = []
        self._analyzed = False
        self._reference_center = None
        self._template = None
    
    def _extract_template(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """Extract template region from frame."""
        x, y, w, h = bbox
        # Ensure bounds
        h_frame, w_frame = frame.shape[:2]
        x = max(0, min(x, w_frame - w))
        y = max(0, min(y, h_frame - h))
        
        template = frame[y:y+h, x:x+w].copy()
        return template
    
    def _match_template(
        self, 
        frame: np.ndarray, 
        template: np.ndarray,
        search_region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Find template in frame using template matching.
        
        Returns:
            Matched bounding box (x, y, w, h) or None if no good match
        """
        # Convert to grayscale for matching
        if len(frame.shape) == 3:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame_gray = frame
            
        if len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template
        
        h_template, w_template = template_gray.shape[:2]
        h_frame, w_frame = frame_gray.shape[:2]
        
        # Define search region (expand around expected location)
        if search_region:
            sx, sy, sw, sh = search_region
            # Ensure search region is within frame bounds
            sx = max(0, sx)
            sy = max(0, sy)
            sw = min(sw, w_frame - sx)
            sh = min(sh, h_frame - sy)
            
            if sw < w_template or sh < h_template:
                search_area = frame_gray
                offset_x, offset_y = 0, 0
            else:
                search_area = frame_gray[sy:sy+sh, sx:sx+sw]
                offset_x, offset_y = sx, sy
        else:
            search_area = frame_gray
            offset_x, offset_y = 0, 0
        
        # Perform template matching
        if search_area.shape[0] < h_template or search_area.shape[1] < w_template:
            return None
            
        result = cv2.matchTemplate(search_area, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # Threshold for good match
        if max_val < self.settings.match_threshold:
            return None
        
        # Get matched location
        match_x = max_loc[0] + offset_x
        match_y = max_loc[1] + offset_y
        
        return (match_x, match_y, w_template, h_template)
    
    def analyze_video(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """
        First pass: Analyze video and compute stabilization offsets using template matching.
        
        Args:
            video_path: Path to video file
            progress_callback: Callback(progress: 0-1, status_message)
            
        Returns:
            True if analysis successful
        """
        if not self.settings.bounding_box:
            return False
        
        self._reset_analysis()
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            reference_frame_idx = self.settings.reference_frame_idx
            
            bbox = self.settings.bounding_box
            x, y, w, h = bbox
            
            # Seek to reference frame to extract template
            if reference_frame_idx > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, reference_frame_idx)
            
            ret, reference_frame = cap.read()
            if not ret:
                return False
            
            # Extract template from reference frame
            self._template = self._extract_template(reference_frame, bbox)
            
            # Calculate reference center (center of initial bounding box)
            self._reference_center = (float(x + w / 2), float(y + h / 2))
            
            # Reset to beginning and process all frames
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            frame_idx = 0
            last_box = bbox
            search_margin = 50  # Pixels to expand search area
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Define search region around last known position
                lx, ly, lw, lh = last_box
                search_region = (
                    lx - search_margin,
                    ly - search_margin,
                    lw + 2 * search_margin,
                    lh + 2 * search_margin
                )
                
                # Find template in current frame
                matched_box = self._match_template(frame, self._template, search_region)
                
                # Fallback to full frame search if tracking lost
                if not matched_box:
                    matched_box = self._match_template(frame, self._template, None)
                
                if matched_box:
                    tx, ty, tw, th = matched_box
                    self._tracking_boxes.append(matched_box)
                    
                    # Compute center of matched box
                    tracked_center_x = tx + tw / 2
                    tracked_center_y = ty + th / 2
                    
                    # Compute offset from reference center
                    dx = self._reference_center[0] - tracked_center_x
                    dy = self._reference_center[1] - tracked_center_y
                    self._offsets.append((dx, dy))
                    
                    last_box = matched_box
                else:
                    # Tracking lost - use previous values
                    if self._offsets:
                        self._offsets.append(self._offsets[-1])
                        self._tracking_boxes.append(self._tracking_boxes[-1])
                    else:
                        self._offsets.append((0.0, 0.0))
                        self._tracking_boxes.append(bbox)
                
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
    
    def get_tracked_box(self, frame_idx: int) -> Optional[Tuple[int, int, int, int]]:
        """Get the tracked bounding box position for a specific frame."""
        if not self._analyzed or frame_idx >= len(self._tracking_boxes):
            return self.settings.bounding_box
        return self._tracking_boxes[frame_idx]
    
    def get_tracked_position(self, frame_idx: int) -> Optional[Tuple[float, float]]:
        """Get the tracked center point position for a specific frame."""
        box = self.get_tracked_box(frame_idx)
        if box:
            x, y, w, h = box
            return (float(x + w / 2), float(y + h / 2))
        return self.settings.tracking_point
    
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
            draw_tracking_point: Whether to draw a marker at the tracking region
            first_frame: First frame of video for on-the-fly tracking
            
        Returns:
            Preview frame with stabilization applied
        """
        result = frame.copy()
        
        if not self.settings.bounding_box:
            return result
        
        dx, dy = 0.0, 0.0
        tracked_box = self.settings.bounding_box
        
        # Ensure reference center is set (for marker drawing)
        if self._reference_center is None and self.settings.bounding_box:
            x, y, w, h = self.settings.bounding_box
            self._reference_center = (float(x + w / 2), float(y + h / 2))
        
        # Use pre-computed offset if available
        if self._analyzed and frame_idx < len(self._offsets):
            dx, dy = self._offsets[frame_idx]
            tracked_box = self._tracking_boxes[frame_idx]
        elif first_frame is not None and frame_idx != self.settings.reference_frame_idx:
            # Compute offset on-the-fly by tracking from reference frame
            offset, box = self._track_single_frame(first_frame, frame)
            if offset:
                dx, dy = offset
                tracked_box = box
        
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
        
        # Draw reference point marker (fixed position where tracked point is locked to)
        if draw_tracking_point and self._reference_center:
            # Draw at the reference center - this is where the tracked point should be locked
            cx, cy = int(self._reference_center[0]), int(self._reference_center[1])
            
            # Ensure we're in a drawable format
            if len(result.shape) < 3:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
            
            color = (0, 255, 255)  # Yellow in BGR
            if result.shape[2] == 4:
                color = (0, 255, 255, 255)
            
            thickness = 2
            size = 15
            
            # Draw crosshair at fixed reference position
            cv2.line(result, (cx - size, cy), (cx + size, cy), color, thickness)
            cv2.line(result, (cx, cy - size), (cx, cy + size), color, thickness)
            cv2.circle(result, (cx, cy), 8, color, thickness)
        
        return result
    
    def _track_single_frame(
        self,
        first_frame: np.ndarray,
        current_frame: np.ndarray
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[int, int, int, int]]]:
        """
        Track the bounding box from first_frame to current_frame.
        
        Returns:
            Tuple of (offset (dx, dy), tracked_box (x, y, w, h)) or (None, None) if tracking failed
        """
        if not self.settings.bounding_box:
            return None, None
        
        bbox = self.settings.bounding_box
        
        # Extract template from first frame
        template = self._extract_template(first_frame, bbox)
        
        # Find template in current frame
        matched_box = self._match_template(current_frame, template)
        
        if matched_box:
            tx, ty, tw, th = matched_box
            
            # Reference center (from initial box)
            ref_x = bbox[0] + bbox[2] / 2
            ref_y = bbox[1] + bbox[3] / 2
            
            # Tracked center
            tracked_x = tx + tw / 2
            tracked_y = ty + th / 2
            
            dx = ref_x - tracked_x
            dy = ref_y - tracked_y
            
            return (dx, dy), matched_box
        
        return None, None
    
    def reset(self):
        """Fully reset stabilizer state."""
        self.settings.bounding_box = None
        self._reset_analysis()

