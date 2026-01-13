"""
Logging utilities for the Green Screen Remover application.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


class ProcessingStats:
    """Track processing statistics."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_frames: int = 0
        self.processed_frames: int = 0
        self.errors: list[str] = []
    
    def start(self, total_frames: int):
        self.reset()
        self.start_time = datetime.now()
        self.total_frames = total_frames
    
    def update(self, processed: int):
        self.processed_frames = processed
    
    def finish(self):
        self.end_time = datetime.now()
    
    def add_error(self, error: str):
        self.errors.append(error)
    
    @property
    def duration(self) -> float:
        """Get processing duration in seconds."""
        if not self.start_time:
            return 0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    @property
    def fps(self) -> float:
        """Get processing FPS."""
        if self.duration == 0:
            return 0
        return self.processed_frames / self.duration
    
    @property
    def eta_seconds(self) -> float:
        """Estimated time remaining in seconds."""
        if self.processed_frames == 0 or self.fps == 0:
            return 0
        remaining = self.total_frames - self.processed_frames
        return remaining / self.fps
    
    @property
    def progress(self) -> float:
        """Get progress as percentage (0-100)."""
        if self.total_frames == 0:
            return 0
        return (self.processed_frames / self.total_frames) * 100


class AppLogger:
    """Application logger with optional GUI callback."""
    
    def __init__(self, name: str = "ChromaKey"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # Optional file handler
        try:
            log_dir = Path.home() / ".chromakey" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"chromakey_{datetime.now().strftime('%Y%m%d')}.log"
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        except Exception:
            pass  # File logging is optional
        
        # GUI callback for status updates
        self._gui_callback: Optional[Callable[[str, str], None]] = None
    
    def set_gui_callback(self, callback: Callable[[str, str], None]):
        """Set callback for GUI status updates. Callback receives (level, message)."""
        self._gui_callback = callback
    
    def _notify_gui(self, level: str, message: str):
        if self._gui_callback:
            try:
                self._gui_callback(level, message)
            except Exception:
                pass
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def info(self, message: str):
        self.logger.info(message)
        self._notify_gui("INFO", message)
    
    def warning(self, message: str):
        self.logger.warning(message)
        self._notify_gui("WARNING", message)
    
    def error(self, message: str):
        self.logger.error(message)
        self._notify_gui("ERROR", message)
    
    def success(self, message: str):
        self.logger.info(message)
        self._notify_gui("SUCCESS", message)


# Global logger instance
logger = AppLogger()
