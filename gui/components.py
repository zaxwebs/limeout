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
            progress_color=("#3B8ED0", "#1F6AA5")
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
            text_color=("#3B8ED0", "#4DA6FF")
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
            progress_color=("#28a745", "#22963E"),
            button_color=("gray70", "gray30"),
            button_hover_color=("gray60", "gray40")
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
        super().__init__(parent, corner_radius=10, **kwargs)
        
        self.cancel_callback = cancel_callback
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        
        # Header with icon
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header_frame.grid_columnconfigure(1, weight=1)
        
        self.status_icon = ctk.CTkLabel(
            header_frame,
            text="⏸",
            font=ctk.CTkFont(size=16)
        )
        self.status_icon.grid(row=0, column=0, padx=(0, 8))
        
        self.status_label = ctk.CTkLabel(
            header_frame,
            text="Ready",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        self.status_label.grid(row=0, column=1, sticky="w")
        
        # Progress bar with custom colors
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
            progress_color=("#28a745", "#22963E")
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
            text_color=("#3B8ED0", "#4DA6FF")
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
            fg_color=("gray85", "gray25"),
            hover_color=("#dc3545", "#c82333"),
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
        self.status_icon.configure(text="▶")
        self.status_label.configure(text=status)
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color=("#3B8ED0", "#1F6AA5"))
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
        self.status_icon.configure(text="✓")
        self.progress_bar.set(1)
        self.progress_bar.configure(progress_color=("#28a745", "#22963E"))
        self.percent_label.configure(text="100%")
        self.eta_label.configure(text="")
        self.status_label.configure(text=status)
        self.cancel_btn.grid_remove()  # Hide cancel button
    
    def reset(self):
        """Reset to initial state."""
        self.status_icon.configure(text="⏸")
        self.status_label.configure(text="Ready")
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color=("#28a745", "#22963E"))
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
            text="💾",
            width=36,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=14),
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


class StatusLog(ctk.CTkFrame):
    """
    Scrollable status log with color-coded messages.
    """
    
    # Color mapping for log levels
    LEVEL_COLORS = {
        "ERROR": "#dc3545",
        "WARNING": "#ffc107", 
        "SUCCESS": "#28a745",
        "INFO": "#6c757d"
    }
    
    def __init__(self, parent, max_lines: int = 100, **kwargs):
        super().__init__(parent, corner_radius=8, **kwargs)
        
        self.max_lines = max_lines
        self._lines: List[tuple] = []  # (level, message)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header = ctk.CTkLabel(
            self,
            text="📋 Activity Log",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w"
        )
        header.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        
        # Text widget
        self.text = ctk.CTkTextbox(
            self,
            height=100,
            font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled",
            corner_radius=6
        )
        self.text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
    
    def log(self, message: str, level: str = "INFO"):
        """Add a message to the log."""
        level = level.upper()
        self._lines.append((level, message))
        
        # Trim if too long
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]
        
        # Update display
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        
        for lvl, msg in self._lines:
            prefix = {"ERROR": "✗", "WARNING": "⚠", "SUCCESS": "✓", "INFO": "•"}.get(lvl, "•")
            self.text.insert("end", f"{prefix} {msg}\n")
        
        self.text.see("end")
        self.text.configure(state="disabled")
    
    def clear(self):
        """Clear the log."""
        self._lines = []
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


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
            hover_color=("gray80", "gray30"),
            text_color=("gray20", "gray80"),
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
            button_length=14
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
            hover_color=("gray80", "gray30"),
            text_color=("gray20", "gray80"),
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
