"""
Core chroma key processing algorithms.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class ChromaKeySettings:
    """Settings for chroma key processing."""
    h_min: int = 35
    h_max: int = 85
    s_min: int = 50
    s_max: int = 255
    v_min: int = 50
    v_max: int = 255
    feather: int = 2
    spill_suppression: float = 0.5
    defringe_transparent: float = 0.0  # For semi-transparent areas like fins
    erode_size: int = 1
    dilate_size: int = 1


class ChromaKeyProcessor:
    """
    Professional chroma key processor with feathering and spill suppression.
    """
    
    def __init__(self, settings: Optional[ChromaKeySettings] = None):
        self.settings = settings or ChromaKeySettings()
    
    def create_mask(self, frame: np.ndarray) -> np.ndarray:
        """
        Create alpha mask from frame based on HSV color range.
        
        Args:
            frame: BGR frame from OpenCV
            
        Returns:
            Alpha mask (0-255) where 255 is fully opaque
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        lower = np.array([self.settings.h_min, self.settings.s_min, self.settings.v_min])
        upper = np.array([self.settings.h_max, self.settings.s_max, self.settings.v_max])
        
        # Create mask where green is white
        green_mask = cv2.inRange(hsv, lower, upper)
        
        # Invert so foreground (non-green) is white
        alpha = cv2.bitwise_not(green_mask)
        
        return alpha
    
    def refine_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Apply morphological operations to clean up the mask.
        
        Args:
            mask: Raw alpha mask
            
        Returns:
            Refined alpha mask
        """
        # Erode to remove green fringe
        if self.settings.erode_size > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, 
                (self.settings.erode_size * 2 + 1, self.settings.erode_size * 2 + 1)
            )
            mask = cv2.erode(mask, kernel, iterations=1)
        
        # Dilate to recover subject edges
        if self.settings.dilate_size > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (self.settings.dilate_size * 2 + 1, self.settings.dilate_size * 2 + 1)
            )
            mask = cv2.dilate(mask, kernel, iterations=1)
        
        return mask
    
    def apply_feathering(self, mask: np.ndarray) -> np.ndarray:
        """
        Apply edge feathering for smooth alpha transitions.
        
        Args:
            mask: Alpha mask
            
        Returns:
            Feathered alpha mask
        """
        if self.settings.feather <= 0:
            return mask
        
        # Calculate blur kernel size (must be odd)
        kernel_size = self.settings.feather * 2 + 1
        
        # Apply Gaussian blur for smooth edges
        feathered = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)
        
        return feathered
    
    def suppress_spill(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Remove green color spill from the subject edges.
        
        This reduces the green tint that often appears on subjects
        filmed against a green screen.
        
        Args:
            frame: BGR frame
            mask: Alpha mask (used to find edge regions)
            
        Returns:
            BGR frame with spill suppression applied
        """
        if self.settings.spill_suppression <= 0:
            return frame
        
        # Find edge region (where spill is most visible)
        kernel_size = 5
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
        # Edge is where mask transitions (dilated - eroded)
        dilated = cv2.dilate(mask, kernel, iterations=2)
        eroded = cv2.erode(mask, kernel, iterations=2)
        edge_mask = cv2.subtract(dilated, eroded)
        
        # Convert to float for processing
        frame_float = frame.astype(np.float32)
        
        # Split channels
        b, g, r = cv2.split(frame_float)
        
        # Calculate spill amount (how much greener than average of R and B)
        avg_rb = (r + b) / 2
        spill = np.maximum(0, g - avg_rb)
        
        # Apply suppression weighted by edge mask and setting
        edge_weight = edge_mask.astype(np.float32) / 255.0
        suppression_amount = spill * self.settings.spill_suppression * edge_weight
        
        # Reduce green channel in spill areas
        g_corrected = np.clip(g - suppression_amount, 0, 255)
        
        # Also boost red/blue slightly to compensate
        compensation = suppression_amount * 0.3
        r_corrected = np.clip(r + compensation, 0, 255)
        b_corrected = np.clip(b + compensation, 0, 255)
        
        result = cv2.merge([b_corrected, g_corrected, r_corrected])
        return result.astype(np.uint8)
    
    def defringe_transparent_areas(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        Remove green color contamination from semi-transparent areas.
        
        Uses professional color decontamination technique: estimates the amount
        of green screen "bleeding through" semi-transparent areas and removes it.
        
        Args:
            frame: BGR frame
            mask: Alpha mask (0-255 where partial values indicate transparency)
            
        Returns:
            BGR frame with green decontamination applied
        """
        if self.settings.defringe_transparent <= 0:
            return frame
        
        strength = self.settings.defringe_transparent
        
        # Convert to float
        frame_float = frame.astype(np.float32)
        b, g, r = cv2.split(frame_float)
        alpha = mask.astype(np.float32) / 255.0
        
        # === METHOD 1: Classic Despill (Green = max(R, B)) ===
        # This is the industry-standard approach used in Nuke, After Effects, etc.
        # Green should never exceed the maximum of red and blue in
        # properly decontaminated footage
        max_rb = np.maximum(r, b)
        
        # Calculate how much to pull green down
        # In areas where green > max(R,B), there's green contamination
        green_contamination = np.maximum(0, g - max_rb)
        
        # === METHOD 2: Alpha-weighted correction ===
        # Semi-transparent areas (alpha between 0.02 and 0.98) need more correction
        # because that's where the green screen shows through
        semi_transparent_weight = np.where(
            (alpha > 0.02) & (alpha < 0.98),
            # Bell curve: maximum at 50% transparency
            4.0 * alpha * (1.0 - alpha),  # Peaks at 0.5
            0.0
        )
        
        # Also apply to nearly-transparent areas that still have some visibility
        edge_weight = np.where(
            alpha < 0.3,
            alpha * 3.0,  # Linear ramp for very transparent areas
            0.0
        )
        
        combined_weight = np.maximum(semi_transparent_weight, edge_weight)
        
        # === Apply green removal ===
        # Base removal: always apply despill to contaminated areas
        base_removal = green_contamination * strength
        
        # Extra removal for semi-transparent areas
        extra_removal = green_contamination * combined_weight * strength * 2.0
        
        total_removal = base_removal + extra_removal
        
        # Clamp green channel
        g_new = np.clip(g - total_removal, 0, 255)
        
        # === Color compensation ===
        # When we remove green, also shift toward red/magenta to counter the green tint
        # This makes the result look more natural
        compensation = total_removal * 0.4
        r_new = np.clip(r + compensation * 0.6, 0, 255)  # Add some red
        b_new = np.clip(b + compensation * 0.4, 0, 255)  # Add some blue
        
        # === Additional: Force green <= max(R,B) in semi-transparent areas ===
        # This is a hard clamp that guarantees no green spill
        if strength > 0.5:
            max_rb_new = np.maximum(r_new, b_new)
            # Only apply in semi-transparent and transparent areas
            force_mask = (alpha < 0.95).astype(np.float32)
            g_clamped = np.minimum(g_new, max_rb_new)
            g_new = g_new * (1 - force_mask * (strength - 0.5) * 2) + g_clamped * (force_mask * (strength - 0.5) * 2)
            g_new = np.clip(g_new, 0, 255)
        
        result = cv2.merge([b_new, g_new, r_new])
        return result.astype(np.uint8)
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single frame to remove chroma key background.
        
        Args:
            frame: BGR frame from OpenCV
            
        Returns:
            RGBA frame with alpha channel
        """
        # Create and refine mask
        mask = self.create_mask(frame)
        mask = self.refine_mask(mask)
        mask = self.apply_feathering(mask)
        
        # Apply spill suppression (edge-based)
        processed_frame = self.suppress_spill(frame, mask)
        
        # Apply transparent defringe (alpha-based)
        processed_frame = self.defringe_transparent_areas(processed_frame, mask)
        
        # Convert BGR to RGB and add alpha
        r, g, b = cv2.split(processed_frame)[::-1]  # Reverse for RGB
        b_ch, g_ch, r_ch = cv2.split(processed_frame)
        
        rgba = np.dstack((r_ch, g_ch, b_ch, mask))
        
        # Wait, we need RGB not BGR for output
        # Re-order properly: OpenCV is BGR, output should be RGB
        rgba = np.dstack((
            processed_frame[:, :, 2],  # R
            processed_frame[:, :, 1],  # G  
            processed_frame[:, :, 0],  # B
            mask
        ))
        
        return rgba
    
    def preview_frame(self, frame: np.ndarray, show_checkerboard: bool = True, bg_color: Optional[str] = None) -> np.ndarray:
        """
        Create a preview of the processed frame with optional checkerboard or solid color background.
        
        Args:
            frame: BGR frame
            show_checkerboard: If True, show transparency as checkerboard pattern
            bg_color: Optional hex color string for solid background (e.g., '#FF0000')
            
        Returns:
            BGR frame for display
        """
        mask = self.create_mask(frame)
        mask = self.refine_mask(mask)
        mask = self.apply_feathering(mask)
        
        processed = self.suppress_spill(frame, mask)
        processed = self.defringe_transparent_areas(processed, mask)
        
        h, w = frame.shape[:2]
        
        if bg_color:
            # Use solid color background (parse hex color)
            # Convert hex to BGR
            hex_color = bg_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            background = np.zeros((h, w, 3), dtype=np.uint8)
            background[:] = [b, g, r]  # BGR format
            
            # Blend based on alpha
            alpha_normalized = mask.astype(np.float32) / 255.0
            alpha_3ch = np.dstack([alpha_normalized] * 3)
            
            result = (processed.astype(np.float32) * alpha_3ch + 
                     background.astype(np.float32) * (1 - alpha_3ch))
            return result.astype(np.uint8)
        elif show_checkerboard:
            # Create checkerboard pattern
            check_size = 10
            
            checkerboard = np.zeros((h, w, 3), dtype=np.uint8)
            for i in range(0, h, check_size):
                for j in range(0, w, check_size):
                    if (i // check_size + j // check_size) % 2 == 0:
                        checkerboard[i:i+check_size, j:j+check_size] = [200, 200, 200]
                    else:
                        checkerboard[i:i+check_size, j:j+check_size] = [150, 150, 150]
            
            # Blend based on alpha
            alpha_normalized = mask.astype(np.float32) / 255.0
            alpha_3ch = np.dstack([alpha_normalized] * 3)
            
            result = (processed.astype(np.float32) * alpha_3ch + 
                     checkerboard.astype(np.float32) * (1 - alpha_3ch))
            return result.astype(np.uint8)
        else:
            # Just mask out the green
            return cv2.bitwise_and(processed, processed, mask=mask)
