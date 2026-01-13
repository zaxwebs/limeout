# Configuration management for Green Screen Remover
"""
Centralized configuration and settings management.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class ChromaKeyPreset:
    """Preset for chroma key settings."""
    name: str
    h_min: int = 35
    h_max: int = 85
    s_min: int = 50
    s_max: int = 255
    v_min: int = 50
    v_max: int = 255
    feather: int = 2
    spill_suppression: float = 0.5
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChromaKeyPreset":
        return cls(**data)


# Default presets
GREEN_SCREEN_PRESET = ChromaKeyPreset(
    name="Green Screen",
    h_min=35, h_max=85,
    s_min=50, s_max=255,
    v_min=50, v_max=255
)

BLUE_SCREEN_PRESET = ChromaKeyPreset(
    name="Blue Screen",
    h_min=100, h_max=130,
    s_min=50, s_max=255,
    v_min=50, v_max=255
)


@dataclass
class AppConfig:
    """Application configuration."""
    # Window settings
    window_width: int = 1200
    window_height: int = 850
    appearance_mode: str = "Dark"
    color_theme: str = "blue"
    
    # Export settings
    default_codec: str = "libvpx"
    default_pixel_format: str = "yuva420p"
    default_fps: Optional[float] = None  # Use source FPS
    
    # Preview settings
    preview_max_height: int = 400
    preview_checkerboard_size: int = 10
    
    # Processing settings
    enable_spill_suppression: bool = True
    default_feather: int = 2
    
    # Stabilization settings
    enable_stabilization: bool = False
    stabilization_border_mode: str = "transparent"  # transparent, replicate, crop
    
    # File settings
    supported_formats: tuple = (".mp4", ".avi", ".mov", ".mkv", ".webm")
    
    def to_dict(self) -> dict:
        return asdict(self)


class ConfigManager:
    """Manages application configuration and presets."""
    
    CONFIG_DIR = Path.home() / ".chromakey"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PRESETS_FILE = CONFIG_DIR / "presets.json"
    
    def __init__(self):
        self.config = AppConfig()
        self.presets: list[ChromaKeyPreset] = [GREEN_SCREEN_PRESET, BLUE_SCREEN_PRESET]
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def load(self):
        """Load configuration and presets from files."""
        # Load config
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
            except (json.JSONDecodeError, IOError):
                pass  # Use defaults
        
        # Load presets
        if self.PRESETS_FILE.exists():
            try:
                with open(self.PRESETS_FILE, 'r') as f:
                    data = json.load(f)
                    self.presets = [ChromaKeyPreset.from_dict(p) for p in data]
            except (json.JSONDecodeError, IOError):
                pass  # Use defaults
    
    def save(self):
        """Save configuration and presets to files."""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            
            with open(self.PRESETS_FILE, 'w') as f:
                json.dump([p.to_dict() for p in self.presets], f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")
    
    def add_preset(self, preset: ChromaKeyPreset):
        """Add a new preset."""
        # Remove existing preset with same name
        self.presets = [p for p in self.presets if p.name != preset.name]
        self.presets.append(preset)
        self.save()
    
    def get_preset(self, name: str) -> Optional[ChromaKeyPreset]:
        """Get preset by name."""
        for preset in self.presets:
            if preset.name == name:
                return preset
        return None
    
    def delete_preset(self, name: str):
        """Delete a preset by name."""
        self.presets = [p for p in self.presets if p.name != name]
        self.save()


# Global config instance
config_manager = ConfigManager()
