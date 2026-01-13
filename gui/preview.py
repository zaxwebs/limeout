"""
Video preview handling with frame navigation and checkerboard backgrounds.
"""

import cv2
import numpy as np
from PIL import Image, ImageTk
from typing import Optional, Tuple
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
        bg_color: Optional[str] = None
    ) -> np.ndarray:
        """
        Create a preview frame with chroma key applied.
        
        Args:
            frame: BGR frame
            processor: ChromaKeyProcessor with current settings
            crop: Optional (x, y, w, h) crop region
            show_checkerboard: Show transparency as checkerboard
            bg_color: Optional hex color string for solid background (e.g., '#FF0000')
            
        Returns:
            BGR frame for display
        """
        # Apply crop
        if crop:
            x, y, w, h = crop
            x2 = min(x + w, frame.shape[1])
            y2 = min(y + h, frame.shape[0])
            frame = frame[y:y2, x:x2]
        
        if frame.size == 0:
            return np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Resize for preview
        height, width = frame.shape[:2]
        if height > self.max_height:
            scale = self.max_height / height
            new_width = int(width * scale)
            frame = cv2.resize(frame, (new_width, self.max_height))
        
        # Create preview with checkerboard or solid color
        return processor.preview_frame(frame, show_checkerboard, bg_color)
    
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
        super().__init__(parent, corner_radius=12, **kwargs)
        
        self.preview = VideoPreview(max_height=max_height)
        self._current_image = None
        self._pil_image = None  # Store original PIL image for zooming
        self._is_drop_target = False
        
        # Zoom and Pan state
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._drag_start = None
        
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
            bg="#2b2b2b"  # Dark background to match theme
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
        bg_color: Optional[str] = None
    ):
        """Update the preview display."""
        frame = self.preview.get_frame(frame_number)
        
        if frame is None:
            return
        
        preview_frame = self.preview.create_preview(
            frame, processor, crop, show_checkerboard, bg_color
        )
        
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
        
    def _reset_view(self):
        """Reset zoom and pan to defaults."""
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        
    def _on_mouse_down(self, event):
        """Handle mouse button down."""
        self.canvas.scan_mark(event.x, event.y)
        self._drag_start = (event.x, event.y)
        
    def _on_mouse_drag(self, event):
        """Handle mouse drag."""
        if self._drag_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            
            self._pan_x += dx
            self._pan_y += dy
            
            self._drag_start = (event.x, event.y)
            self._redraw_image()
            
    def _on_mouse_up(self, event):
        """Handle mouse button release."""
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
