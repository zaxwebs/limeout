"""
Video preview handling with frame navigation and checkerboard backgrounds.
"""

import cv2
import numpy as np
from PIL import Image, ImageTk
from typing import Optional, Tuple, Callable
import customtkinter as ctk

from processing.chroma_key import ChromaKeyProcessor, ChromaKeySettings


class VideoPreview:
    """
    Handles video preview with frame caching and checkerboard backgrounds.
    """
    
    def __init__(self, max_height: int = 400, checkerboard_size: int = 10):
        self.max_height = max_height
        self.checkerboard_size = checkerboard_size
        
        self._video_path: Optional[str] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_cache: dict[int, np.ndarray] = {}
        self._max_cache_size = 10
        
        self._video_info = {
            'width': 0,
            'height': 0,
            'fps': 0,
            'frame_count': 0
        }
    
    def load_video(self, video_path: str) -> dict:
        """
        Load a video file and return its info.
        
        Returns:
            Dict with video properties
        """
        self.close()
        self._frame_cache.clear()
        
        self._video_path = video_path
        self._cap = cv2.VideoCapture(video_path)
        
        if not self._cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        self._video_info = {
            'width': int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': self._cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        }
        
        return self._video_info
    
    @property
    def video_info(self) -> dict:
        return self._video_info
    
    def get_frame(self, frame_number: int) -> Optional[np.ndarray]:
        """
        Get a specific frame (BGR format).
        Uses caching for recently accessed frames.
        """
        if not self._cap or not self._cap.isOpened():
            return None
        
        # Check cache
        if frame_number in self._frame_cache:
            return self._frame_cache[frame_number]
        
        # Seek and read
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self._cap.read()
        
        if not ret:
            return None
        
        # Cache the frame
        if len(self._frame_cache) >= self._max_cache_size:
            # Remove oldest entry
            oldest = next(iter(self._frame_cache))
            del self._frame_cache[oldest]
        
        self._frame_cache[frame_number] = frame
        return frame
    
    def create_checkerboard(self, height: int, width: int) -> np.ndarray:
        """Create a checkerboard pattern for transparency preview."""
        checkerboard = np.zeros((height, width, 3), dtype=np.uint8)
        size = self.checkerboard_size
        
        for i in range(0, height, size):
            for j in range(0, width, size):
                if (i // size + j // size) % 2 == 0:
                    checkerboard[i:i+size, j:j+size] = [200, 200, 200]
                else:
                    checkerboard[i:i+size, j:j+size] = [150, 150, 150]
        
        return checkerboard
    
    def create_preview(
        self,
        frame: np.ndarray,
        processor: ChromaKeyProcessor,
        crop: Optional[Tuple[int, int, int, int]] = None,
        show_checkerboard: bool = True,
        bg_color: Optional[str] = None,
        stabilizer = None,
        frame_number: int = 0
    ) -> np.ndarray:
        """
        Create a preview frame with chroma key applied.
        
        Args:
            frame: BGR frame
            processor: ChromaKeyProcessor with current settings
            crop: Optional (x, y, w, h) crop region
            show_checkerboard: Show transparency as checkerboard
            bg_color: Optional hex color string for solid background (e.g., '#FF0000')
            stabilizer: Optional PointStabilizer for stabilization preview
            frame_number: Current frame number for stabilization
            
        Returns:
            BGR frame for display
        """
        # Apply stabilization FIRST on full frame if enabled
        stab_alpha = None
        stab_enabled = stabilizer and stabilizer.settings.enabled and stabilizer.settings.bounding_box
        
        if stab_enabled:
            # Get reference frame for on-the-fly tracking comparison
            ref_frame_idx = stabilizer.settings.reference_frame_idx
            ref_frame = self.get_frame(ref_frame_idx)
            
            if ref_frame is not None:
                # Stabilize the full frame (bounding box is in original frame space)
                frame = stabilizer.preview_stabilization(
                    frame, frame_number, draw_tracking_point=False, first_frame=ref_frame
                )
                    
            # If stabilization returned BGRA, extract and preserve alpha for later
            if len(frame.shape) > 2 and frame.shape[2] == 4:
                stab_alpha = frame[:, :, 3].copy()
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        # Apply crop AFTER stabilization (this crops away the transparent borders)
        if crop:
            x, y, w, h = crop
            x2 = min(x + w, frame.shape[1])
            y2 = min(y + h, frame.shape[0])
            frame = frame[y:y2, x:x2]
            # Also crop the stabilization alpha if we have it
            if stab_alpha is not None:
                stab_alpha = stab_alpha[y:y2, x:x2]
        
        if frame.size == 0:
            return np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Resize for preview
        height, width = frame.shape[:2]
        if height > self.max_height:
            scale = self.max_height / height
            new_width = int(width * scale)
            frame = cv2.resize(frame, (new_width, self.max_height))
            # Also resize the stabilization alpha if we have it
            if stab_alpha is not None:
                stab_alpha = cv2.resize(stab_alpha, (new_width, self.max_height))
        
        # Process with chroma key
        preview = processor.preview_frame(frame, show_checkerboard, bg_color)
        
        # If we have stabilization alpha (transparent borders), apply it to the preview
        if stab_alpha is not None:
            h, w = preview.shape[:2]
            alpha = stab_alpha.astype(float) / 255.0
            alpha = alpha[:, :, np.newaxis]  # Add channel dim
            
            if show_checkerboard:
                # Blend with checkerboard pattern
                background = self.create_checkerboard(h, w)
            elif bg_color:
                # Create solid color background
                # Parse hex color
                hex_color = bg_color.lstrip('#')
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                background = np.full((h, w, 3), [b, g, r], dtype=np.uint8)  # BGR
            else:
                # Default to black if somehow neither is set
                background = np.zeros((h, w, 3), dtype=np.uint8)
            
            # Blend preview with background using stabilization alpha
            preview = (preview * alpha + background * (1 - alpha)).astype(np.uint8)
        
        return preview
    
    def frame_to_photoimage(self, frame: np.ndarray) -> ImageTk.PhotoImage:
        """Convert BGR frame to PhotoImage for Tkinter display."""
        # Convert BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image and then to PhotoImage
        pil_image = Image.fromarray(rgb)
        return ImageTk.PhotoImage(image=pil_image)
    
    def close(self):
        """Release video resources."""
        if self._cap:
            self._cap.release()
            self._cap = None
        self._frame_cache.clear()
    
    def __del__(self):
        self.close()


import tkinter as tk

class PreviewWidget(ctk.CTkFrame):
    """
    A preview widget that displays processed video frames with enhanced styling.
    Supports zooming and panning.
    """
    
    def __init__(self, parent, max_height: int = 400, **kwargs):
        super().__init__(parent, corner_radius=12, fg_color=("gray92", "#161b22"), **kwargs)  # GitHub Surface
        
        self.preview = VideoPreview(max_height=max_height)
        self._current_image = None
        self._pil_image = None  # Store original PIL image for zooming
        self._is_drop_target = False
        
        # Zoom and Pan state
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_start = None
        
        # Point/Region selection mode
        self._point_selection_mode = False
        self._rect_selection_mode = False
        self._on_point_selected = None  # Callback(x, y) in original image coords
        self._on_rect_selected = None  # Callback(x, y, w, h) in original image coords
        self._tracking_point = None  # (x, y) to draw marker (deprecated)
        self._tracking_box = None  # (x, y, w, h) bounding box to draw
        self._stab_active = False  # Whether stabilization preview is active (skip canvas marker)
        self._preview_scale = 1.0  # Scale from original frame to preview image
        self._rect_start = None  # Starting point for rectangle drawing
        self._rect_current = None  # Current rectangle being drawn
        
        # Configure
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Empty state container
        self.empty_state = ctk.CTkFrame(self, fg_color="transparent")
        self.empty_state.grid(row=0, column=0, sticky="nsew")
        self.empty_state.grid_columnconfigure(0, weight=1)
        self.empty_state.grid_rowconfigure(0, weight=1)
        
        # Center content
        center_frame = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        center_frame.grid(row=0, column=0)
        
        # Icon
        icon_label = ctk.CTkLabel(
            center_frame,
            text="🎬",
            font=ctk.CTkFont(size=48)
        )
        icon_label.grid(row=0, column=0, pady=(0, 10))
        
        # Main text
        main_label = ctk.CTkLabel(
            center_frame,
            text="No Video Selected",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        main_label.grid(row=1, column=0, pady=(0, 8))
        
        # Sub text
        sub_label = ctk.CTkLabel(
            center_frame,
            text="Drag & drop a video file here\nor click 'Select Video' to begin",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
            justify="center"
        )
        sub_label.grid(row=2, column=0)
        
        # Supported formats hint
        format_label = ctk.CTkLabel(
            center_frame,
            text="Supports: MP4, AVI, MOV, MKV, WebM",
            font=ctk.CTkFont(size=10),
            text_color=("gray60", "gray50")
        )
        format_label.grid(row=3, column=0, pady=(15, 0))
        
        # Canvas for image display (hidden initially)
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            bg="#161b22"  # GitHub Surface
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.canvas.grid_remove()
        
        # Bind events
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)    # Linux scroll down
        self.canvas.bind("<Configure>", self._on_configure)     # specific to resizing
        
        # Drag & drop highlight border
        self._normal_fg = self.cget("fg_color")
    
    def show_drop_highlight(self, show: bool = True):
        """Show/hide drag & drop highlight."""
        if show:
            self.configure(border_width=3, border_color=("#3B8ED0", "#1F6AA5"))
        else:
            self.configure(border_width=0)
    
    def _on_configure(self, event):
        """Handle canvas resize."""
        if self._pil_image:
            self._redraw_image()
    
    def load_video(self, video_path: str) -> dict:
        """Load a video and return its info."""
        info = self.preview.load_video(video_path)
        
        # Reset view
        self._reset_view()
        
        # Switch from empty state to image display
        self.empty_state.grid_remove()
        self.canvas.grid()
        self.canvas.configure(bg=self._apply_appearance_mode(self.cget("fg_color")))
        
        return info
    
    def update_preview(
        self,
        frame_number: int,
        processor: ChromaKeyProcessor,
        crop: Optional[Tuple[int, int, int, int]] = None,
        show_checkerboard: bool = True,
        bg_color: Optional[str] = None,
        stabilizer = None
    ):
        """Update the preview display."""
        frame = self.preview.get_frame(frame_number)
        
        if frame is None:
            return
        
        # Track whether stabilization is active (to skip canvas marker drawing)
        stab_enabled = stabilizer and stabilizer.settings.enabled and stabilizer.settings.bounding_box
        self._stab_active = stab_enabled
        
        preview_frame = self.preview.create_preview(
            frame, processor, crop, show_checkerboard, bg_color, stabilizer, frame_number
        )
        
        # Track the scale from original to preview for coordinate conversion
        orig_h, orig_w = frame.shape[:2]
        prev_h, prev_w = preview_frame.shape[:2]
        self._preview_scale = prev_w / orig_w if orig_w > 0 else 1.0
        
        # Convert to PIL Image and store it
        rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
        self._pil_image = Image.fromarray(rgb)
        
        self._redraw_image()
        
    def _redraw_image(self):
        """Redraw the image on the canvas with current zoom and pan."""
        if self._pil_image is None:
            return
            
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return

        # Calculate new dimensions
        orig_width, orig_height = self._pil_image.size
        new_width = int(orig_width * self._zoom_level)
        new_height = int(orig_height * self._zoom_level)
        
        # Resize image (use efficient resizing)
        # For performance, only resize if changed significantly or if zoom is standard
        resized = self._pil_image.resize((new_width, new_height), Image.Resampling.NEAREST) # Nearest for speed during zoom
        
        self._current_image = ImageTk.PhotoImage(resized)
        
        # Calculate centered position + pan
        x = (canvas_width // 2) + self._pan_x
        y = (canvas_height // 2) + self._pan_y
        
        self.canvas.delete("all")
        self.canvas.create_image(x, y, image=self._current_image, anchor="center")
        
        # Draw tracking point marker if set
        self._draw_tracking_marker()
        
    def _reset_view(self):
        """Reset zoom and pan to defaults."""
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        
    def _on_mouse_down(self, event):
        """Handle mouse button down."""
        if self._rect_selection_mode:
            # Start drawing rectangle
            self._rect_start = (event.x, event.y)
            self._rect_current = (event.x, event.y)
            return
        
        if self._point_selection_mode:
            # Convert canvas coords to image coords
            img_coords = self._canvas_to_image_coords(event.x, event.y)
            if img_coords and self._on_point_selected:
                self._tracking_point = img_coords
                self._on_point_selected(img_coords[0], img_coords[1])
                self._point_selection_mode = False
                self._redraw_image()
            return
        
        self.canvas.scan_mark(event.x, event.y)
        self._drag_start = (event.x, event.y)
        
    def _on_mouse_drag(self, event):
        """Handle mouse drag."""
        if self._rect_selection_mode and self._rect_start:
            # Update rectangle preview
            self._rect_current = (event.x, event.y)
            self._redraw_image()
            self._draw_selection_rect()
            return
        
        if self._drag_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            
            self._pan_x += dx
            self._pan_y += dy
            
            self._drag_start = (event.x, event.y)
            self._redraw_image()
            
    def _on_mouse_up(self, event):
        """Handle mouse button release."""
        if self._rect_selection_mode and self._rect_start:
            # Finish rectangle selection
            start_coords = self._canvas_to_image_coords(*self._rect_start)
            end_coords = self._canvas_to_image_coords(event.x, event.y)
            
            if start_coords and end_coords and self._on_rect_selected:
                x1, y1 = start_coords
                x2, y2 = end_coords
                
                # Normalize to ensure positive width/height
                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)
                
                # Ensure minimum size
                if w >= 10 and h >= 10:
                    self._tracking_box = (x, y, w, h)
                    self._on_rect_selected(x, y, w, h)
                    self._rect_selection_mode = False
                    self.canvas.configure(cursor="")
            
            self._rect_start = None
            self._rect_current = None
            self._redraw_image()
            return
        
        self._drag_start = None
        
    def _on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming."""
        # Windows: event.delta, Linux: event.num
        if event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.1
            
        new_zoom = self._zoom_level * factor
        
        # Limit zoom
        if 0.1 < new_zoom < 10.0:
            self._zoom_level = new_zoom
            self._redraw_image()

    def clear(self):
        """Clear the preview."""
        self.canvas.delete("all")
        self._current_image = None
        self._pil_image = None
        self.canvas.grid_remove()
        self.empty_state.grid()
        self.preview.close()
    
    @property
    def video_info(self) -> dict:
        return self.preview.video_info
    
    def _canvas_to_image_coords(self, canvas_x: int, canvas_y: int) -> Optional[Tuple[int, int]]:
        """Convert canvas coordinates to original video frame coordinates."""
        if self._pil_image is None:
            return None
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Preview image size (displayed on canvas)
        preview_width, preview_height = self._pil_image.size
        
        # Current image center on canvas
        center_x = (canvas_width // 2) + self._pan_x
        center_y = (canvas_height // 2) + self._pan_y
        
        # Zoomed image dimensions
        zoom_width = preview_width * self._zoom_level
        zoom_height = preview_height * self._zoom_level
        
        # Image bounds on canvas
        img_left = center_x - zoom_width / 2
        img_top = center_y - zoom_height / 2
        
        # Relative position within zoomed preview image
        rel_x = (canvas_x - img_left) / self._zoom_level
        rel_y = (canvas_y - img_top) / self._zoom_level
        
        # Check bounds in preview space
        if 0 <= rel_x < preview_width and 0 <= rel_y < preview_height:
            # Convert from preview coordinates to original frame coordinates
            # by dividing by the preview scale factor
            orig_x = int(rel_x / self._preview_scale) if self._preview_scale > 0 else int(rel_x)
            orig_y = int(rel_y / self._preview_scale) if self._preview_scale > 0 else int(rel_y)
            return (orig_x, orig_y)
        return None
    
    def enable_point_selection(self, callback: Callable[[int, int], None]):
        """
        Enable point selection mode.
        
        When enabled, clicking on the preview will call the callback
        with the image coordinates instead of panning.
        
        Args:
            callback: Function to call with (x, y) when point is selected
        """
        self._point_selection_mode = True
        self._on_point_selected = callback
        self.canvas.configure(cursor="crosshair")
    
    def enable_rect_selection(self, callback: Callable[[int, int, int, int], None]):
        """
        Enable rectangle selection mode.
        
        When enabled, clicking and dragging on the preview will call the callback
        with the bounding box coordinates (x, y, w, h) in original image space.
        
        Args:
            callback: Function to call with (x, y, w, h) when region is selected
        """
        self._rect_selection_mode = True
        self._on_rect_selected = callback
        self.canvas.configure(cursor="crosshair")
    
    def disable_point_selection(self):
        """Disable point selection mode."""
        self._point_selection_mode = False
        self._on_point_selected = None
        self.canvas.configure(cursor="")
    
    def disable_rect_selection(self):
        """Disable rectangle selection mode."""
        self._rect_selection_mode = False
        self._on_rect_selected = None
        self._rect_start = None
        self._rect_current = None
        self.canvas.configure(cursor="")
    
    def set_tracking_point(self, x: int, y: int):
        """Set the tracking point to display a marker (deprecated, use set_tracking_box)."""
        # Convert point to small box for backward compatibility
        box_size = 50
        box_x = max(0, x - box_size // 2)
        box_y = max(0, y - box_size // 2)
        self.set_tracking_box(box_x, box_y, box_size, box_size)
    
    def set_tracking_box(self, x: int, y: int, w: int, h: int):
        """Set the tracking bounding box to display."""
        self._tracking_box = (x, y, w, h)
        self._tracking_point = None  # Clear old point
        self._redraw_image()
    
    def clear_tracking_point(self):
        """Clear the tracking marker."""
        self._tracking_point = None
        self._tracking_box = None
        self._redraw_image()
    
    def _draw_tracking_marker(self):
        """Draw a bounding box marker for the tracking region."""
        if self._pil_image is None:
            return
        
        # Skip drawing canvas marker if stabilization is active
        # (stabilizer draws its own fixed crosshair on the frame)
        if self._stab_active:
            return
        
        # Draw bounding box if set
        if self._tracking_box:
            self._draw_box_marker(self._tracking_box)
    
    def _draw_box_marker(self, box: Tuple[int, int, int, int]):
        """Draw a bounding box marker on the canvas."""
        x, y, w, h = box
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        center_x = (canvas_width // 2) + self._pan_x
        center_y = (canvas_height // 2) + self._pan_y
        
        orig_width, orig_height = self._pil_image.size
        zoom_width = orig_width * self._zoom_level
        zoom_height = orig_height * self._zoom_level
        
        img_left = center_x - zoom_width / 2
        img_top = center_y - zoom_height / 2
        
        # Scale coordinates for preview
        scale = self._preview_scale * self._zoom_level
        
        # Convert to canvas coordinates
        canvas_x1 = img_left + x * scale
        canvas_y1 = img_top + y * scale
        canvas_x2 = img_left + (x + w) * scale
        canvas_y2 = img_top + (y + h) * scale
        
        color = "#FFFF00"  # Yellow
        
        # Draw rectangle
        self.canvas.create_rectangle(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2,
            outline=color, width=2, tags="tracking_marker"
        )
        
        # Draw center crosshair
        cx = (canvas_x1 + canvas_x2) / 2
        cy = (canvas_y1 + canvas_y2) / 2
        size = 10
        
        self.canvas.create_line(
            cx - size, cy, cx + size, cy,
            fill=color, width=2, tags="tracking_marker"
        )
        self.canvas.create_line(
            cx, cy - size, cx, cy + size,
            fill=color, width=2, tags="tracking_marker"
        )
    
    def _draw_selection_rect(self):
        """Draw the rectangle being selected."""
        if not self._rect_start or not self._rect_current:
            return
        
        x1, y1 = self._rect_start
        x2, y2 = self._rect_current
        
        # Draw selection rectangle
        self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#00FF00", width=2, dash=(4, 4), tags="selection_rect"
        )
