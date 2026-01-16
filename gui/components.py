"""
Reusable GUI components for the ChromaKey application.
"""

import customtkinter as ctk
from tkinter import ttk
from typing import Optional, Callable, List
import json
from pathlib import Path


class SliderGroup(ctk.CTkFrame):
    """
    A labeled slider with value display - improved styling.
    """
    
    def __init__(
        self,
        parent,
        label: str,
        from_: float = 0,
        to_: float = 100,
        default: float = 50,
        command: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.command = command
        self._value = default
        self._label_text = label
        
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        
        # Label (left side)
        self.label = ctk.CTkLabel(
            self, 
            text=label,
            width=110,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        self.label.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        # Slider (middle)
        self.slider = ctk.CTkSlider(
            self,
            from_=from_,
            to=to_,
            command=self._on_change,
            height=16,
            button_length=12,
            progress_color=("#3B8ED0", "#2f81f7")  # GitHub Blue
        )
        self.slider.set(default)
        self.slider.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        # Value display (right side) - monospace for alignment
        self.value_label = ctk.CTkLabel(
            self,
            text=f"{int(default):>3}",
            width=40,
            anchor="e",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=("#3B8ED0", "#2f81f7")  # GitHub Blue
        )
        self.value_label.grid(row=0, column=2, sticky="e")
    
    def _on_change(self, value):
        self._value = value
        self.value_label.configure(text=f"{int(value):>3}")
        if self.command:
            self.command(value)
    
    def get(self) -> float:
        return self.slider.get()
    
    def set(self, value: float):
        self.slider.set(value)
        self._on_change(value)


class ToggleOption(ctk.CTkFrame):
    """
    A switch with label and optional description - improved styling.
    """
    
    def __init__(
        self,
        parent,
        label: str,
        description: str = "",
        default: bool = False,
        command: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.command = command
        self.grid_columnconfigure(0, weight=1)
        
        # Top row: Switch and label
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.grid_columnconfigure(0, weight=1)
        
        self.switch = ctk.CTkSwitch(
            top_frame,
            text=label,
            command=self._on_change,
            font=ctk.CTkFont(size=12),
            progress_color=("#28a745", "#238636"),  # GitHub Green
            button_color=("gray70", "gray85"),
            button_hover_color=("gray60", "gray95")
        )
        self.switch.grid(row=0, column=0, sticky="w")
        
        if default:
            self.switch.select()
        
        if description:
            self.desc_label = ctk.CTkLabel(
                self,
                text=description,
                font=ctk.CTkFont(size=11),
                text_color=("gray50", "gray60")
            )
            self.desc_label.grid(row=1, column=0, sticky="w", padx=(48, 0), pady=(2, 0))
    
    def _on_change(self):
        if self.command:
            self.command(self.get())
    
    def get(self) -> bool:
        return bool(self.switch.get())
    
    def set(self, value: bool):
        if value:
            self.switch.select()
        else:
            self.switch.deselect()


class ProgressPanel(ctk.CTkFrame):
    """
    Enhanced progress panel with status, ETA, and cancel button.
    """
    
    def __init__(
        self,
        parent,
        cancel_callback: Optional[Callable] = None,
        **kwargs
    ):

        super().__init__(parent, corner_radius=8, fg_color=("white", "#21262d"), **kwargs)  # GitHub Card
        
        self.cancel_callback = cancel_callback
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        
        # Header with icon
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header_frame.grid_columnconfigure(1, weight=1)
        
        self.status_label = ctk.CTkLabel(
            header_frame,
            text="Ready",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="w")
        
        # Progress bar with custom colors
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
            progress_color=("#28a745", "#238636"),  # GitHub Green
            border_color="#30363d",
            border_width=1
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        self.progress_bar.set(0)
        
        # Bottom row: percentage, ETA, and cancel button
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        
        self.percent_label = ctk.CTkLabel(
            self.bottom_frame,
            text="0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#3B8ED0", "#2f81f7")  # GitHub Blue
        )
        self.percent_label.grid(row=0, column=0, sticky="w")
        
        self.eta_label = ctk.CTkLabel(
            self.bottom_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.eta_label.grid(row=0, column=1, padx=10, sticky="w")
        
        self.cancel_btn = ctk.CTkButton(
            self.bottom_frame,
            text="✕ Cancel",
            width=80,
            height=28,
            fg_color=("gray85", "#21262d"),  # GitHub Secondary Button
            hover_color=("#dc3545", "#da3633"),  # GitHub Danger
            border_width=1,
            border_color=("gray70", "#30363d"),  # GitHub Border
            text_color=("gray10", "gray90"),
            font=ctk.CTkFont(size=11),
            corner_radius=6,
            command=self._on_cancel
        )
        self.cancel_btn.grid(row=0, column=2)
        self.cancel_btn.grid_remove()  # Hidden by default
    
    def _on_cancel(self):
        if self.cancel_callback:
            self.cancel_callback()
    
    def start(self, status: str = "Processing..."):
        """Start progress tracking."""
        self.status_label.configure(text=status)
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color=("#3B8ED0", "#2f81f7"))  # GitHub Blue
        self.percent_label.configure(text="0%")
        self.eta_label.configure(text="")
        self.cancel_btn.grid()  # Show cancel button
    
    def update(self, progress: float, eta_text: str = ""):
        """Update progress (0-1)."""
        self.progress_bar.set(progress)
        self.percent_label.configure(text=f"{int(progress * 100)}%")
        self.eta_label.configure(text=eta_text)
    
    def finish(self, status: str = "Complete!"):
        """Mark as complete."""
        self.progress_bar.set(1)
        self.progress_bar.configure(progress_color=("#28a745", "#238636"))  # GitHub Green
        self.percent_label.configure(text="100%")
        self.eta_label.configure(text="")
        self.status_label.configure(text=status)
        self.cancel_btn.grid_remove()  # Hide cancel button
    
    def reset(self):
        """Reset to initial state."""
        self.status_label.configure(text="Ready")
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color=("#28a745", "#238636"))  # GitHub Green
        self.percent_label.configure(text="0%")
        self.eta_label.configure(text="")
        self.cancel_btn.grid_remove()


class PresetSelector(ctk.CTkFrame):
    """
    Dropdown for selecting presets with save button - improved styling.
    """
    
    def __init__(
        self,
        parent,
        presets: List[str],
        on_select: Optional[Callable[[str], None]] = None,
        on_save: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.on_select = on_select
        self.on_save = on_save
        self._presets = presets
        
        self.grid_columnconfigure(1, weight=1)
        
        # Icon + Label
        self.label = ctk.CTkLabel(
            self, 
            text="🎨  Preset:",
            font=ctk.CTkFont(size=12)
        )
        self.label.grid(row=0, column=0, padx=(0, 10))
        
        # Dropdown
        self.dropdown = ctk.CTkOptionMenu(
            self,
            values=presets if presets else ["Default"],
            command=self._on_select,
            corner_radius=6,
            height=32,
            font=ctk.CTkFont(size=12)
        )
        self.dropdown.grid(row=0, column=1, sticky="ew")
        
        # Save button
        self.save_btn = ctk.CTkButton(
            self,
            text="Save",
            width=50,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=14),
            fg_color=("gray85", "#21262d"),  # GitHub Secondary
            hover_color=("gray75", "#30363d"),
            border_width=1,
            border_color=("gray70", "#30363d"),
            command=self._on_save
        )
        self.save_btn.grid(row=0, column=2, padx=(8, 0))
    
    def _on_select(self, value: str):
        if self.on_select:
            self.on_select(value)
    
    def _on_save(self):
        if self.on_save:
            current = self.dropdown.get()
            self.on_save(current)
    
    def update_presets(self, presets: List[str]):
        """Update the preset list."""
        self._presets = presets
        self.dropdown.configure(values=presets if presets else ["Default"])
    
    def set(self, preset_name: str):
        """Set the selected preset."""
        self.dropdown.set(preset_name)




class FrameTimeline(ctk.CTkFrame):
    """
    Frame scrubber with playback controls for navigating video frames.
    """
    
    def __init__(
        self,
        parent,
        total_frames: int = 100,
        on_frame_change: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.total_frames = max(1, total_frames)
        self.fps = 30
        self.on_frame_change = on_frame_change
        self._current_frame = 0
        
        self.grid_columnconfigure(2, weight=1)
        
        # Frame counter with icon
        frame_info = ctk.CTkFrame(self, fg_color="transparent")
        frame_info.grid(row=0, column=0, padx=(0, 12))
        
        ctk.CTkLabel(
            frame_info,
            text="🎬",
            font=ctk.CTkFont(size=14)
        ).grid(row=0, column=0, padx=(0, 4))
        
        self.frame_label = ctk.CTkLabel(
            frame_info,
            text="0 / 0",
            width=90,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            anchor="w"
        )
        self.frame_label.grid(row=0, column=1)
        
        # Previous frame button
        self.prev_btn = ctk.CTkButton(
            self,
            text="◀",
            width=32,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=("gray80", "#21262d"),  # GitHub Secondary
            text_color=("gray20", "#e6edf3"),   # GitHub Text
            font=ctk.CTkFont(size=14),
            command=self._go_prev_frame
        )
        self.prev_btn.grid(row=0, column=1, padx=(0, 4))
        
        # Slider
        self.slider = ctk.CTkSlider(
            self,
            from_=0,
            to=max(1, total_frames - 1),
            command=self._on_slider_change,
            height=16,
            button_length=14,
            progress_color=("#3B8ED0", "#2f81f7")  # GitHub Blue
        )
        self.slider.set(0)
        self.slider.grid(row=0, column=2, sticky="ew", padx=4)
        
        # Next frame button
        self.next_btn = ctk.CTkButton(
            self,
            text="▶",
            width=32,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            hover_color=("gray80", "#21262d"),  # GitHub Secondary
            text_color=("gray20", "#e6edf3"),   # GitHub Text
            font=ctk.CTkFont(size=14),
            command=self._go_next_frame
        )
        self.next_btn.grid(row=0, column=3, padx=(4, 0))
        
        # Time display
        self.time_label = ctk.CTkLabel(
            self,
            text="0:00.0",
            width=70,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=("gray50", "gray60")
        )
        self.time_label.grid(row=0, column=4, padx=(12, 0))
    
    def _go_prev_frame(self):
        """Go to previous frame."""
        prev_frame = max(0, self._current_frame - 1)
        if prev_frame != self._current_frame:
            self.set_frame(prev_frame)
            if self.on_frame_change:
                self.on_frame_change(prev_frame)
    
    def _go_next_frame(self):
        """Go to next frame."""
        next_frame = min(self.total_frames - 1, self._current_frame + 1)
        if next_frame != self._current_frame:
            self.set_frame(next_frame)
            if self.on_frame_change:
                self.on_frame_change(next_frame)
    
    def _on_slider_change(self, value):
        frame = int(value)
        if frame != self._current_frame:
            self._current_frame = frame
            self._update_labels()
            if self.on_frame_change:
                self.on_frame_change(frame)
    
    def _update_labels(self):
        self.frame_label.configure(text=f"{self._current_frame} / {self.total_frames}")
        
        # Calculate time
        if self.fps > 0:
            total_seconds = self._current_frame / self.fps
            minutes = int(total_seconds // 60)
            seconds = total_seconds % 60
            self.time_label.configure(text=f"{minutes}:{seconds:04.1f}")
    
    def set_total_frames(self, total: int, fps: float = 30):
        """Update total frames and FPS for time display."""
        self.total_frames = max(1, total)
        self.fps = fps
        self.slider.configure(to=max(1, total - 1))
        self._update_labels()
    
    def set_frame(self, frame: int):
        """Set current frame without triggering callback."""
        self._current_frame = frame
        self.slider.set(frame)
        self._update_labels()
    
    def get_frame(self) -> int:
        return self._current_frame


class StabilizationPanel(ctk.CTkFrame):
    """
    Panel for controlling video stabilization via object boundary tracking.
    """
    
    def __init__(
        self,
        parent,
        on_enable_change: Optional[Callable[[bool], None]] = None,
        on_select_point: Optional[Callable[[], None]] = None,
        on_reset: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.on_enable_change = on_enable_change
        self.on_select_point = on_select_point  # Also used for region selection
        self.on_reset = on_reset
        self._bounding_box: Optional[tuple] = None
        self._is_selecting = False
        
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkLabel(
            self,
            text="Stabilization",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        header.grid(row=0, column=0, sticky="w", pady=(0, 8))
        
        # Enable toggle
        self.enable_switch = ctk.CTkSwitch(
            self,
            text="Enable Stabilization",
            command=self._on_enable_change,
            font=ctk.CTkFont(size=12),
            progress_color=("#28a745", "#238636"),  # GitHub Green
        )
        self.enable_switch.grid(row=1, column=0, sticky="w", pady=(0, 8))
        
        # Description
        desc = ctk.CTkLabel(
            self,
            text="Draw a box around the object to track",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        desc.grid(row=2, column=0, sticky="w", padx=(24, 0), pady=(0, 10))
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        # Select Region button
        self.select_btn = ctk.CTkButton(
            btn_frame,
            text="Select Region",
            command=self._on_select_click,
            height=32,
            corner_radius=6,
            fg_color=("#3B8ED0", "#2f81f7"),  # GitHub Blue
            font=ctk.CTkFont(size=12)
        )
        self.select_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        
        # Reset button
        self.reset_btn = ctk.CTkButton(
            btn_frame,
            text="Reset",
            command=self._on_reset_click,
            height=32,
            corner_radius=6,
            fg_color=("gray75", "#21262d"),  # GitHub Secondary
            hover_color=("#dc3545", "#da3633"), # GitHub Danger
            border_width=1,
            border_color=("gray70", "#30363d"),
            font=ctk.CTkFont(size=12)
        )
        self.reset_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        
        # Tracking region display
        self.point_label = ctk.CTkLabel(
            self,
            text="No region selected",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=("gray50", "gray60")
        )
        self.point_label.grid(row=4, column=0, sticky="w", pady=(2, 0))
    
    def _on_enable_change(self):
        if self.on_enable_change:
            self.on_enable_change(self.get_enabled())
    
    def _on_select_click(self):
        if self._is_selecting:
            self._set_selecting(False)
        else:
            self._set_selecting(True)
            if self.on_select_point:
                self.on_select_point()
    
    def _on_reset_click(self):
        self._bounding_box = None
        self._reference_frame = None
        self._set_selecting(False)
        self.point_label.configure(text="No region selected")
        if self.on_reset:
            self.on_reset()
    
    def _set_selecting(self, selecting: bool):
        self._is_selecting = selecting
        if selecting:
            self.select_btn.configure(
                text="Draw on Preview...",
                fg_color=("#ffc107", "#d29922") # GitHub Warning (Yellow)
            )
            self.point_label.configure(text="Click and drag on preview...")
        else:
            self.select_btn.configure(
                text="Select Region",
                fg_color=("#3B8ED0", "#2f81f7")  # GitHub Blue
            )
            if not self._bounding_box:
                self.point_label.configure(text="No region selected")
    
    def set_bounding_box(self, x: int, y: int, w: int, h: int, frame: int = 0):
        """Set the bounding box coordinates and reference frame."""
        self._bounding_box = (x, y, w, h)
        self._reference_frame = frame
        self._set_selecting(False)
        self.point_label.configure(text=f"Region: ({x}, {y}) {w}×{h} @ frame {frame}")
    
    def set_tracking_point(self, x: int, y: int):
        """Set tracking point (creates default bounding box for backward compat)."""
        # Create a 50x50 box centered on the point
        box_size = 50
        box_x = max(0, x - box_size // 2)
        box_y = max(0, y - box_size // 2)
        self.set_bounding_box(box_x, box_y, box_size, box_size)
    
    def get_enabled(self) -> bool:
        return bool(self.enable_switch.get())
    
    def set_enabled(self, value: bool):
        if value:
            self.enable_switch.select()
        else:
            self.enable_switch.deselect()
    
    def get_bounding_box(self) -> Optional[tuple]:
        return self._bounding_box
    
    def get_tracking_point(self) -> Optional[tuple]:
        """Get center point of bounding box for backward compat."""
        if self._bounding_box:
            x, y, w, h = self._bounding_box
            return (x + w // 2, y + h // 2)
        return None
    
    def is_selecting(self) -> bool:
        return self._is_selecting


class SuccessDialog(ctk.CTkToplevel):
    """
    Dialog shown after successful processing with options to open/view file.
    """
    
    def __init__(self, parent, output_path: str, stats: str = "", **kwargs):
        super().__init__(parent, fg_color=("gray95", "#0d1117"), **kwargs)  # GitHub Canvas
        
        self.output_path = output_path
        self.title("Processing Complete")
        self.geometry("450x300")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Icon and Message
        self.label_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.label_frame.grid(row=0, column=0, pady=(20, 10), sticky="ew")
        self.label_frame.grid_columnconfigure(0, weight=1)
        
        self.msg_label = ctk.CTkLabel(
            self.label_frame,
            text="Video processed successfully!",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("gray10", "#e6edf3")
        )
        self.msg_label.grid(row=0, column=0, pady=(10, 5))
        
        # Stats label
        if stats:
            self.stats_label = ctk.CTkLabel(
                self.label_frame,
                text=stats,
                font=ctk.CTkFont(size=12),
                text_color=("#28a745", "#238636")  # GitHub Green
            )
            self.stats_label.grid(row=1, column=0, pady=(0, 5))
        
        # File path (truncated if too long)
        path = Path(output_path)
        display_path = path.name
        if len(display_path) > 40:
            display_path = display_path[:20] + "..." + display_path[-17:]
            
        self.path_label = ctk.CTkLabel(
            self,
            text=display_path,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.path_label.grid(row=1, column=0, pady=(0, 20))
        
        # Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        self.btn_frame.grid_columnconfigure(0, weight=1)
        
        # Open Folder button
        self.open_folder_btn = ctk.CTkButton(
            self.btn_frame,
            text="Open Folder",
            height=36,
            command=self._open_folder,
            fg_color=("gray75", "#21262d"),  # GitHub Secondary
            hover_color=("gray65", "#30363d"),
            text_color=("gray10", "#e6edf3"),
            border_width=1,
            border_color=("gray70", "#30363d")
        )
        self.open_folder_btn.grid(row=0, column=0, sticky="ew")
        
    def _open_folder(self):
        """Open the folder containing the file, or the folder itself for PNG sequences."""
        import subprocess
        import os
        try:
            abs_path = os.path.abspath(self.output_path)
            
            if os.path.isdir(abs_path):
                # PNG sequence: open the folder directly
                os.startfile(abs_path)
            else:
                # Video file: select the file in explorer
                subprocess.run(f'explorer /select,"{abs_path}"')
        except Exception as e:
            # Fallback to just opening the parent folder
            try:
                folder = self.output_path if os.path.isdir(self.output_path) else os.path.dirname(self.output_path)
                os.startfile(folder)
            except Exception:
                pass
        self.destroy()
