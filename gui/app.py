"""
Main ChromaKey application with improved UI and features.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
from typing import Optional
from pathlib import Path

# Try to import drag and drop support (optional)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from gui.components import (
    SliderGroup,
    ProgressPanel,
    StatusLog,
    FrameTimeline
)
from gui.preview import PreviewWidget
from processing.chroma_key import ChromaKeyProcessor, ChromaKeySettings
from processing.video_processor import VideoProcessor, ProcessingOptions
from config import config_manager
from utils.logger import logger
from utils.validators import ValidationError, validate_video_path


# Create appropriate base class depending on DnD availability
if HAS_DND:
    class AppBase(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self):
            super().__init__()
            self.TkdndVersion = TkinterDnD._require(self)
else:
    class AppBase(ctk.CTk):
        def __init__(self):
            super().__init__()


class ChromaKeyApp(AppBase):
    """
    Professional Chroma Key Remover application with enhanced UX.
    """
    
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("ChromaKey Remover Pro")
        self.geometry(f"{config_manager.config.window_width}x{config_manager.config.window_height}")
        self.minsize(1000, 750)
        
        # Configure appearance
        ctk.set_appearance_mode(config_manager.config.appearance_mode)
        ctk.set_default_color_theme(config_manager.config.color_theme)
        
        # State
        self.video_path: Optional[str] = None
        self.processor = VideoProcessor()
        self.chroma_settings = ChromaKeySettings()
        
        # Setup UI
        self._setup_layout()
        self._setup_sidebar()
        self._setup_main_area()
        
        # Setup logger callback
        logger.set_gui_callback(self._on_log_message)
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_layout(self):
        """Configure the main grid layout."""
        self.grid_columnconfigure(0, weight=0, minsize=280)  # Sidebar
        self.grid_columnconfigure(1, weight=1)  # Main content
        self.grid_rowconfigure(0, weight=1)
    
    def _setup_sidebar(self):
        """Create the sidebar with controls."""
        self.sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray92", "gray14"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        
        # ═══════════════════════════════════════════════════════════════
        # ACTION BUTTONS
        # ═══════════════════════════════════════════════════════════════
        btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_frame.grid(row=0, column=0, padx=16, pady=(20, 10), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        
        self.btn_select = ctk.CTkButton(
            btn_frame,
            text="📂  Select Video",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("gray78", "gray28"),
            hover_color=("gray70", "gray35"),
            text_color=("gray10", "gray90"),
            command=self._select_video
        )
        self.btn_select.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        
        self.btn_process = ctk.CTkButton(
            btn_frame,
            text="▶  Start Processing",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#28a745", "#22963E"),
            hover_color=("#218838", "#1E7E34"),
            command=self._start_processing,
            state="disabled"
        )
        self.btn_process.grid(row=1, column=0, sticky="ew")
        
        # ═══════════════════════════════════════════════════════════════
        # PROGRESS PANEL
        # ═══════════════════════════════════════════════════════════════
        self.progress_panel = ProgressPanel(
            self.sidebar,
            cancel_callback=self._cancel_processing
        )
        self.progress_panel.grid(row=1, column=0, padx=12, pady=15, sticky="ew")
        
        # ═══════════════════════════════════════════════════════════════
        # SPACER
        # ═══════════════════════════════════════════════════════════════
        self.sidebar.grid_rowconfigure(2, weight=1)
        
        # ═══════════════════════════════════════════════════════════════
        # STATUS LOG
        # ═══════════════════════════════════════════════════════════════
        self.status_log = StatusLog(self.sidebar, max_lines=50)
        self.status_log.grid(row=3, column=0, padx=12, pady=10, sticky="ew")
        
        # ═══════════════════════════════════════════════════════════════
        # VIDEO INFO FOOTER
        # ═══════════════════════════════════════════════════════════════
        footer_frame = ctk.CTkFrame(self.sidebar, fg_color=("gray88", "gray18"), corner_radius=0)
        footer_frame.grid(row=4, column=0, sticky="ew")
        footer_frame.grid_columnconfigure(0, weight=1)
        
        self.video_info_label = ctk.CTkLabel(
            footer_frame,
            text="No video loaded",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.video_info_label.grid(row=0, column=0, padx=16, pady=12)
    
    def _setup_main_area(self):
        """Create the main content area."""
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # ═══════════════════════════════════════════════════════════════
        # FRAME TIMELINE
        # ═══════════════════════════════════════════════════════════════
        self.timeline = FrameTimeline(
            self.main_frame,
            total_frames=1,
            on_frame_change=self._on_frame_change
        )
        self.timeline.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 10))
        
        # ═══════════════════════════════════════════════════════════════
        # PREVIEW WIDGET
        # ═══════════════════════════════════════════════════════════════
        self.preview_widget = PreviewWidget(
            self.main_frame,
            max_height=config_manager.config.preview_max_height
        )
        self.preview_widget.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Setup drag and drop on preview if available
        if HAS_DND:
            try:
                self.preview_widget.drop_target_register(DND_FILES)
                self.preview_widget.dnd_bind('<<Drop>>', self._on_drop)
                self.preview_widget.dnd_bind('<<DragEnter>>', lambda e: self.preview_widget.show_drop_highlight(True))
                self.preview_widget.dnd_bind('<<DragLeave>>', lambda e: self.preview_widget.show_drop_highlight(False))
            except Exception:
                pass
        
        # ═══════════════════════════════════════════════════════════════
        # CONTROLS - TABBED INTERFACE
        # ═══════════════════════════════════════════════════════════════
        self.controls_tabs = ctk.CTkTabview(
            self.main_frame,
            height=300,
            corner_radius=10,
            segmented_button_selected_color=("#3B8ED0", "#1F6AA5"),
            segmented_button_selected_hover_color=("#36749E", "#1A5A8A")
        )
        self.controls_tabs.grid(row=2, column=0, sticky="ew", padx=5, pady=(10, 0))
        
        # Create tabs
        self.controls_tabs.add("🎨 Color Range")
        self.controls_tabs.add("✨ Effects")
        self.controls_tabs.add("✂️ Crop")
        self.controls_tabs.add("🖼️ Preview")
        
        # ─────────────────────────────────────────────────────────────
        # TAB 1: COLOR RANGE (HSV)
        # ─────────────────────────────────────────────────────────────
        color_tab = self.controls_tabs.tab("🎨 Color Range")
        color_tab.grid_columnconfigure(0, weight=1)
        
        # Section header
        ctk.CTkLabel(
            color_tab,
            text="Adjust the HSV values to target the background color",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(5, 10))
        
        # Sliders container
        sliders_frame = ctk.CTkFrame(color_tab, fg_color="transparent")
        sliders_frame.grid(row=1, column=0, sticky="ew", padx=10)
        sliders_frame.grid_columnconfigure(0, weight=1)
        
        self.h_min_slider = SliderGroup(
            sliders_frame, "Hue Min", 0, 179, 35, self._on_setting_change
        )
        self.h_min_slider.grid(row=0, column=0, sticky="ew", pady=4)
        
        self.h_max_slider = SliderGroup(
            sliders_frame, "Hue Max", 0, 179, 85, self._on_setting_change
        )
        self.h_max_slider.grid(row=1, column=0, sticky="ew", pady=4)
        
        self.s_min_slider = SliderGroup(
            sliders_frame, "Saturation Min", 0, 255, 50, self._on_setting_change
        )
        self.s_min_slider.grid(row=2, column=0, sticky="ew", pady=4)
        
        self.v_min_slider = SliderGroup(
            sliders_frame, "Value Min", 0, 255, 50, self._on_setting_change
        )
        self.v_min_slider.grid(row=3, column=0, sticky="ew", pady=4)
        
        # ─────────────────────────────────────────────────────────────
        # TAB 2: EFFECTS
        # ─────────────────────────────────────────────────────────────
        effects_tab = self.controls_tabs.tab("✨ Effects")
        effects_tab.grid_columnconfigure(0, weight=1)
        
        # Section header
        ctk.CTkLabel(
            effects_tab,
            text="Fine-tune the output with edge and color corrections",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(5, 10))
        
        effects_frame = ctk.CTkFrame(effects_tab, fg_color="transparent")
        effects_frame.grid(row=1, column=0, sticky="ew", padx=10)
        effects_frame.grid_columnconfigure(0, weight=1)
        
        self.feather_slider = SliderGroup(
            effects_frame, "Edge Feather", 0, 20, 2, self._on_setting_change
        )
        self.feather_slider.grid(row=0, column=0, sticky="ew", pady=4)
        
        self.spill_slider = SliderGroup(
            effects_frame, "Spill Suppression", 0, 100, 50, self._on_setting_change
        )
        self.spill_slider.grid(row=1, column=0, sticky="ew", pady=4)
        
        # ─────────────────────────────────────────────────────────────
        # TAB 3: CROP
        # ─────────────────────────────────────────────────────────────
        crop_tab = self.controls_tabs.tab("✂️ Crop")
        crop_tab.grid_columnconfigure(0, weight=1)
        
        # Crop controls container (crop is always enabled)
        self.crop_frame = ctk.CTkFrame(crop_tab, fg_color="transparent")
        self.crop_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.crop_frame.grid_columnconfigure(0, weight=1)
        
        self._setup_crop_sliders()
        
        # ─────────────────────────────────────────────────────────────
        # TAB 4: PREVIEW
        # ─────────────────────────────────────────────────────────────
        preview_tab = self.controls_tabs.tab("🖼️ Preview")
        preview_tab.grid_columnconfigure(0, weight=1)
        
        # Section header
        ctk.CTkLabel(
            preview_tab,
            text="Preview background color (for visualization only, not exported)",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 10))
        
        # Color picker frame
        color_frame = ctk.CTkFrame(preview_tab, fg_color="transparent")
        color_frame.grid(row=1, column=0, sticky="ew", padx=10)
        
        # Preset colors
        self.preview_bg_color = "checkerboard"  # Default
        
        ctk.CTkLabel(
            color_frame,
            text="Background:",
            font=ctk.CTkFont(size=12)
        ).grid(row=0, column=0, padx=(0, 10))
        
        # Checkerboard button (default)
        self.bg_checker_btn = ctk.CTkButton(
            color_frame,
            text="▦",
            width=36,
            height=36,
            corner_radius=6,
            fg_color=("#3B8ED0", "#1F6AA5"),
            font=ctk.CTkFont(size=16),
            command=lambda: self._set_preview_bg("checkerboard")
        )
        self.bg_checker_btn.grid(row=0, column=1, padx=2)
        
        # Black
        self.bg_black_btn = ctk.CTkButton(
            color_frame,
            text="",
            width=36,
            height=36,
            corner_radius=6,
            fg_color="#000000",
            hover_color="#333333",
            command=lambda: self._set_preview_bg("#000000")
        )
        self.bg_black_btn.grid(row=0, column=2, padx=2)
        
        # White
        self.bg_white_btn = ctk.CTkButton(
            color_frame,
            text="",
            width=36,
            height=36,
            corner_radius=6,
            fg_color="#FFFFFF",
            hover_color="#DDDDDD",
            border_width=1,
            border_color="gray60",
            command=lambda: self._set_preview_bg("#FFFFFF")
        )
        self.bg_white_btn.grid(row=0, column=3, padx=2)
        
        # Red
        self.bg_red_btn = ctk.CTkButton(
            color_frame,
            text="",
            width=36,
            height=36,
            corner_radius=6,
            fg_color="#FF0000",
            hover_color="#CC0000",
            command=lambda: self._set_preview_bg("#FF0000")
        )
        self.bg_red_btn.grid(row=0, column=4, padx=2)
        
        # Blue
        self.bg_blue_btn = ctk.CTkButton(
            color_frame,
            text="",
            width=36,
            height=36,
            corner_radius=6,
            fg_color="#0066FF",
            hover_color="#0055DD",
            command=lambda: self._set_preview_bg("#0066FF")
        )
        self.bg_blue_btn.grid(row=0, column=5, padx=2)
        
        # Magenta (common for preview)
        self.bg_magenta_btn = ctk.CTkButton(
            color_frame,
            text="",
            width=36,
            height=36,
            corner_radius=6,
            fg_color="#FF00FF",
            hover_color="#DD00DD",
            command=lambda: self._set_preview_bg("#FF00FF")
        )
        self.bg_magenta_btn.grid(row=0, column=6, padx=2)
    
    def _setup_crop_sliders(self):
        """Setup crop sliders using left/right/top/bottom margins."""
        self.crop_left = SliderGroup(self.crop_frame, "Left", 0, 1920, 0, self._on_setting_change)
        self.crop_left.grid(row=0, column=0, sticky="ew", pady=4)
        
        self.crop_right = SliderGroup(self.crop_frame, "Right", 0, 1920, 0, self._on_setting_change)
        self.crop_right.grid(row=1, column=0, sticky="ew", pady=4)
        
        self.crop_top = SliderGroup(self.crop_frame, "Top", 0, 1080, 0, self._on_setting_change)
        self.crop_top.grid(row=2, column=0, sticky="ew", pady=4)
        
        self.crop_bottom = SliderGroup(self.crop_frame, "Bottom", 0, 1080, 0, self._on_setting_change)
        self.crop_bottom.grid(row=3, column=0, sticky="ew", pady=4)
    
    def _set_preview_bg(self, color: str):
        """Set the preview background color."""
        self.preview_bg_color = color
        
        # Update button highlighting - reset all, then highlight selected
        default_color = ("gray78", "gray28")
        selected_color = ("#3B8ED0", "#1F6AA5")
        
        self.bg_checker_btn.configure(fg_color=selected_color if color == "checkerboard" else default_color)
        self.bg_black_btn.configure(fg_color="#000000" if color != "#000000" else selected_color)
        self.bg_white_btn.configure(fg_color="#FFFFFF" if color != "#FFFFFF" else selected_color)
        self.bg_red_btn.configure(fg_color="#FF0000" if color != "#FF0000" else selected_color)
        self.bg_blue_btn.configure(fg_color="#0066FF" if color != "#0066FF" else selected_color)
        self.bg_magenta_btn.configure(fg_color="#FF00FF" if color != "#FF00FF" else selected_color)
        
        # Update preview
        self._update_preview()
    
    def _on_drop(self, event):
        """Handle file drop."""
        file_path = event.data
        # Clean up path (remove braces if present)
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        
        self.preview_widget.show_drop_highlight(False)
        
        if file_path:
            self._load_video(file_path)
    
    def _select_video(self):
        """Open file dialog to select video."""
        filetypes = [
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm *.m4v"),
            ("All files", "*.*")
        ]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self._load_video(filename)
    
    def _load_video(self, video_path: str):
        """Load video and update UI."""
        try:
            # Validate
            validate_video_path(video_path)
            
            # Load
            info = self.preview_widget.load_video(video_path)
            self.video_path = video_path
            
            # Update timeline
            self.timeline.set_total_frames(info['frame_count'], info['fps'])
            self.timeline.set_frame(0)
            
            # Update crop slider ranges based on video dimensions
            self.crop_left.slider.configure(to=info['width'] - 1)
            self.crop_right.slider.configure(to=info['width'] - 1)
            self.crop_top.slider.configure(to=info['height'] - 1)
            self.crop_bottom.slider.configure(to=info['height'] - 1)
            # Reset to 0 (no crop margins)
            self.crop_left.set(0)
            self.crop_right.set(0)
            self.crop_top.set(0)
            self.crop_bottom.set(0)
            
            # Update info label with icon
            duration = info['frame_count'] / info['fps'] if info['fps'] > 0 else 0
            self.video_info_label.configure(
                text=f"📹 {info['width']}×{info['height']} • {info['fps']:.1f}fps • {duration:.1f}s",
                text_color=("gray30", "gray70")
            )
            
            # Enable processing
            self.btn_process.configure(state="normal")
            
            # Update preview
            self._update_preview()
            
            logger.info(f"Loaded: {Path(video_path).name}")
            
        except ValidationError as e:
            messagebox.showerror("Error", str(e))
            logger.error(str(e))
    
    def _on_setting_change(self, _=None):
        """Handle any setting change."""
        self._update_chroma_settings()
        self._update_preview()
    
    def _on_frame_change(self, frame_number: int):
        """Handle timeline frame change."""
        self._update_preview()
    
    def _update_chroma_settings(self):
        """Update chroma settings from sliders."""
        self.chroma_settings = ChromaKeySettings(
            h_min=int(self.h_min_slider.get()),
            h_max=int(self.h_max_slider.get()),
            s_min=int(self.s_min_slider.get()),
            s_max=255,
            v_min=int(self.v_min_slider.get()),
            v_max=255,
            feather=int(self.feather_slider.get()),
            spill_suppression=self.spill_slider.get() / 100
        )
    
    def _update_preview(self):
        """Update the preview display."""
        if not self.video_path:
            return
        
        processor = ChromaKeyProcessor(self.chroma_settings)
        
        # Crop using left/right/top/bottom margins
        # Convert margins to (x, y, w, h) format
        left = int(self.crop_left.get())
        right = int(self.crop_right.get())
        top = int(self.crop_top.get())
        bottom = int(self.crop_bottom.get())
        
        # Get video dimensions
        video_info = self.preview_widget.video_info
        if video_info and video_info.get('width', 0) > 0:
            w = video_info['width'] - left - right
            h = video_info['height'] - top - bottom
            if w > 0 and h > 0:
                crop = (left, top, w, h)
            else:
                crop = None  # Invalid crop, skip
        else:
            crop = None
        
        frame_number = self.timeline.get_frame()
        
        # Determine if using checkerboard or solid color
        use_checkerboard = self.preview_bg_color == "checkerboard"
        bg_color = None if use_checkerboard else self.preview_bg_color
        
        self.preview_widget.update_preview(frame_number, processor, crop, use_checkerboard, bg_color)
    
    def _start_processing(self):
        """Start video processing in background thread."""
        if not self.video_path:
            return
        
        output_path = filedialog.asksaveasfilename(
            defaultextension=".webm",
            filetypes=[("WebM Video", "*.webm")]
        )
        
        if not output_path:
            return
        
        # Disable UI
        self.btn_process.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        
        # Start progress
        self.progress_panel.start("Processing video...")
        
        # Get settings
        settings = self.chroma_settings
        
        options = ProcessingOptions()
        # Crop using left/right/top/bottom margins
        left = int(self.crop_left.get())
        right = int(self.crop_right.get())
        top = int(self.crop_top.get())
        bottom = int(self.crop_bottom.get())
        
        # Get video dimensions and convert to (x, y, w, h)
        video_info = self.preview_widget.video_info
        if video_info and video_info.get('width', 0) > 0:
            w = video_info['width'] - left - right
            h = video_info['height'] - top - bottom
            if w > 0 and h > 0:
                options.crop = (left, top, w, h)
        
        # Process in thread
        def process_thread():
            try:
                success = self.processor.process(
                    self.video_path,
                    output_path,
                    settings,
                    options,
                    self._on_progress
                )
                
                self.after(0, lambda: self._on_processing_complete(success))
                
            except Exception as e:
                self.after(0, lambda: self._on_processing_error(str(e)))
        
        threading.Thread(target=process_thread, daemon=True).start()
    
    def _on_progress(self, progress: float, status: str):
        """Handle progress update from processing thread."""
        self.after(0, lambda: self.progress_panel.update(progress, status))
    
    def _on_processing_complete(self, success: bool):
        """Handle processing completion."""
        self.btn_process.configure(state="normal")
        self.btn_select.configure(state="normal")
        
        if success:
            self.progress_panel.finish("Complete!")
            messagebox.showinfo("Success", "Video processed successfully!")
        else:
            self.progress_panel.reset()
            logger.warning("Processing was cancelled")
    
    def _on_processing_error(self, error: str):
        """Handle processing error."""
        self.btn_process.configure(state="normal")
        self.btn_select.configure(state="normal")
        self.progress_panel.reset()
        
        messagebox.showerror("Error", error)
        logger.error(error)
    
    def _cancel_processing(self):
        """Cancel current processing."""
        self.processor.cancel()
    
    def _on_log_message(self, level: str, message: str):
        """Handle log message callback."""
        self.after(0, lambda: self.status_log.log(message, level))
    
    def _on_close(self):
        """Handle window close."""
        if self.processor.is_processing:
            if not messagebox.askyesno(
                "Processing in Progress",
                "Video is still processing. Cancel and exit?"
            ):
                return
            self.processor.cancel()
        
        # Save config
        config_manager.save()
        
        # Cleanup
        self.preview_widget.clear()
        
        self.destroy()
