"""
Video processing with proper resource management and cancellation support.
"""

import cv2
import numpy as np
import imageio
import threading
from pathlib import Path
from typing import Optional, Callable, Tuple
from dataclasses import dataclass

from processing.chroma_key import ChromaKeyProcessor, ChromaKeySettings
from processing.stabilizer import PointStabilizer
from utils.logger import logger, ProcessingStats
from utils.validators import (
    validate_video_path, 
    validate_output_path,
    validate_crop_region,
    ValidationError
)


@dataclass
class ProcessingOptions:
    """Options for video processing."""
    crop: Optional[Tuple[int, int, int, int]] = None  # (x, y, width, height)
    target_fps: Optional[float] = None  # None = use source FPS
    stabilizer: Optional[PointStabilizer] = None  # Stabilizer with tracking point set
    resize_width: Optional[int] = None  # Target output width (height scales to maintain aspect ratio)
    stacked_mask: bool = False  # Export with mask stacked (Top=RGB, Bottom=Mask)


class VideoProcessor:
    """
    Video processor with cancellation support and progress tracking.
    """
    
    def __init__(self):
        self.stats = ProcessingStats()
        self._cancel_event = threading.Event()
        self._is_processing = False
    
    @property
    def is_processing(self) -> bool:
        return self._is_processing
    
    def cancel(self):
        """Request cancellation of current processing."""
        if self._is_processing:
            self._cancel_event.set()
            logger.info("Cancellation requested...")
    
    def get_video_info(self, video_path: str) -> dict:
        """
        Get video metadata.
        
        Returns:
            Dict with 'width', 'height', 'fps', 'frame_count', 'duration'
        """
        path = validate_video_path(video_path)
        
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValidationError(f"Cannot open video: {video_path}")
        
        try:
            info = {
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            }
            info['duration'] = info['frame_count'] / info['fps'] if info['fps'] > 0 else 0
            return info
        finally:
            cap.release()
    
    def get_frame_at(self, video_path: str, frame_number: int) -> Optional[np.ndarray]:
        """
        Get a specific frame from the video.
        
        Args:
            video_path: Path to video file
            frame_number: Frame index (0-based)
            
        Returns:
            BGR frame or None if failed
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            return frame if ret else None
        finally:
            cap.release()
    
    def process(
        self,
        input_path: str,
        output_path: str,
        settings: ChromaKeySettings,
        options: Optional[ProcessingOptions] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """
        Process video with chroma key removal.
        
        Args:
            input_path: Source video path
            output_path: Output WebM path
            settings: Chroma key settings
            options: Processing options (crop, fps, etc.)
            progress_callback: Callback(progress: 0-1, status_message)
            
        Returns:
            True if successful, False if cancelled or failed
        """
        options = options or ProcessingOptions()
        self._cancel_event.clear()
        self._is_processing = True
        
        cap = None
        writer = None
        
        try:
            # Validate paths
            input_file = validate_video_path(input_path)
            output_file = validate_output_path(output_path)
            
            logger.info(f"Opening video: {input_file.name}")
            
            # Open video
            cap = cv2.VideoCapture(str(input_file))
            if not cap.isOpened():
                raise ValidationError("Failed to open video file")
            
            # Get video properties
            fps = options.target_fps or cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Validate and apply crop
            if options.crop:
                crop = validate_crop_region(
                    *options.crop, frame_width, frame_height
                )
                output_width = crop[2]
                output_height = crop[3]
            else:
                crop = None
                output_width = frame_width
                output_height = frame_height
            
            # Calculate final dimensions if resizing
            target_size = None
            if options.resize_width and options.resize_width < output_width:
                scale = options.resize_width / output_width
                target_width = int(options.resize_width)
                target_height = int(output_height * scale)
                
                # Ensure even dimensions (video codecs prefer even numbers)
                if target_width % 2 != 0: target_width -= 1
                if target_height % 2 != 0: target_height -= 1
                
                target_size = (target_width, target_height)
                logger.info(f"Output will be resized to: {target_width}x{target_height}")
                output_width, output_height = target_width, target_height
            
            # Initialize stats
            self.stats.start(total_frames)
            
            # Create processor
            processor = ChromaKeyProcessor(settings)
            
            # Stabilization analysis pass (if enabled)
            stabilizer = options.stabilizer
            if stabilizer and stabilizer.settings.enabled and stabilizer.settings.bounding_box:
                logger.info("Analyzing video for stabilization...")
                if not stabilizer.analyze_video(str(input_file), progress_callback):
                    logger.warning("Stabilization analysis failed, proceeding without stabilization")
                    stabilizer = None
                else:
                    logger.info("Stabilization analysis complete")
                    # Reset video to beginning
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                stabilizer = None
            
            # Create writer
            logger.info(f"Creating output: {output_file.name}")
            
            # Configure Output format
            
            if options.stacked_mask:
                # Opaque output, 2x height, HEVC MP4
                codec = 'libx265'
                pixelformat = 'yuv420p'
                output_params = ['-crf', '23', '-preset', 'medium'] # Good balance
                final_output_width = output_width
                final_output_height = output_height * 2
                logger.info("Using stacked RGB/Alpha export (HEVC MP4)")
            else:
                # Standard transparent output (WebM VP9)
                codec = 'libvpx-vp9'
                pixelformat = 'yuva420p'
                output_params = ['-auto-alt-ref', '0']  # Preserve transparency
                final_output_width = output_width
                final_output_height = output_height
                logger.info("Using user transparent export (WebM VP9)")

            writer = imageio.get_writer(
                str(output_file),
                fps=fps,
                codec=codec,
                pixelformat=pixelformat,
                macro_block_size=None,
                output_params=output_params
            )
            
            frame_count = 0
            
            while cap.isOpened():
                # Check for cancellation
                if self._cancel_event.is_set():
                    logger.warning("Processing cancelled by user")
                    return False
                
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Apply stabilization FIRST on full frame
                if stabilizer:
                    frame = stabilizer.apply_stabilization(frame, frame_count)
                    # Convert back to BGR if stabilizer returned BGRA
                    if len(frame.shape) > 2 and frame.shape[2] == 4:
                        # Keep alpha for later merge, but process BGR
                        stab_alpha = frame[:, :, 3]
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    else:
                        stab_alpha = None
                else:
                    stab_alpha = None
                
                # Apply crop AFTER stabilization (crops away transparent borders)
                if crop:
                    x, y, w, h = crop
                    frame = frame[y:y+h, x:x+w]
                    # Also crop stabilization alpha
                    if stab_alpha is not None:
                        stab_alpha = stab_alpha[y:y+h, x:x+w]
                
                # Process frame with chroma key
                rgba = processor.process_frame(frame)
                
                # Merge stabilization alpha (transparent borders) with chroma key alpha
                if stab_alpha is not None:
                    rgba[:, :, 3] = cv2.bitwise_and(rgba[:, :, 3], stab_alpha)
                
                # Resize if needed
                if target_size:
                    rgba = cv2.resize(rgba, target_size, interpolation=cv2.INTER_AREA)
                
                if options.stacked_mask:
                    # Create stacked frame
                    h, w = rgba.shape[:2]
                    stacked_frame = np.zeros((h * 2, w, 3), dtype=np.uint8)
                    
                    # Top side: RGB
                    # Apply alpha to RGB to matte against black
                    alpha_factor = rgba[:, :, 3] / 255.0
                    for c in range(3):
                       stacked_frame[:h, :, c] = rgba[:, :, c] * alpha_factor
                    
                    # Bottom side: Alpha channel as grayscale
                    # Replicate alpha to 3 channels
                    alpha = rgba[:, :, 3]
                    for c in range(3):
                        stacked_frame[h:, :, c] = alpha
                    
                    # Write stacked frame (it's RGB now)
                    writer.append_data(stacked_frame)
                    
                else:
                    # Optimization: Zero out RGB values for fully transparent pixels
                    # This significantly improves compression efficiency for the output video
                    transparent_mask = rgba[:, :, 3] == 0
                    rgba[transparent_mask] = [0, 0, 0, 0]

                    # Write frame
                    writer.append_data(rgba)
                
                frame_count += 1
                self.stats.update(frame_count)
                
                # Report progress
                if progress_callback and frame_count % 5 == 0:
                    progress = frame_count / total_frames
                    eta = self.stats.eta_seconds
                    eta_str = f"{int(eta)}s remaining" if eta > 0 else ""
                    progress_callback(progress, eta_str)
            
            self.stats.finish()
            logger.success(
                f"Processing complete: {frame_count} frames in {self.stats.duration:.1f}s "
                f"({self.stats.fps:.1f} fps)"
            )
            
            if progress_callback:
                progress_callback(1.0, "Complete!")
            
            return True
            
        except ValidationError as e:
            logger.error(str(e))
            raise
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise
        finally:
            # Clean up resources
            if cap is not None:
                cap.release()
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
            self._is_processing = False
    
    def export_image_sequence(
        self,
        input_path: str,
        output_folder: str,
        settings: ChromaKeySettings,
        options: Optional[ProcessingOptions] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """
        Export video frames as an image sequence (PNG) with transparency.
        
        Args:
            input_path: Source video path
            output_folder: Output folder path (will be created if it doesn't exist)
            settings: Chroma key settings
            options: Processing options (crop, fps, etc.)
            progress_callback: Callback(progress: 0-1, status_message)
            
        Returns:
            True if successful, False if cancelled or failed
        """
        options = options or ProcessingOptions()
        self._cancel_event.clear()
        self._is_processing = True
        
        cap = None
        
        try:
            # Validate input
            input_file = validate_video_path(input_path)
            
            # Create output folder
            output_path_obj = Path(output_folder)
            output_path_obj.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Opening video: {input_file.name}")
            logger.info(f"Output folder: {output_path_obj} (Format: PNG)")
            
            # Open video
            cap = cv2.VideoCapture(str(input_file))
            if not cap.isOpened():
                raise ValidationError("Failed to open video file")
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Validate and apply crop
            if options.crop:
                crop = validate_crop_region(
                    *options.crop, frame_width, frame_height
                )
                output_width = crop[2]
                output_height = crop[3]
            else:
                crop = None
                output_width = frame_width
                output_height = frame_height
            
            # Calculate final dimensions if resizing
            target_size = None
            if options.resize_width and options.resize_width < output_width:
                scale = options.resize_width / output_width
                target_width = int(options.resize_width)
                target_height = int(output_height * scale)
                target_size = (target_width, target_height)
                logger.info(f"Output will be resized to: {target_width}x{target_height}")
            
            # Initialize stats
            self.stats.start(total_frames)
            
            # Create processor
            processor = ChromaKeyProcessor(settings)
            
            # Stabilization analysis pass (if enabled)
            stabilizer = options.stabilizer
            if stabilizer and stabilizer.settings.enabled and stabilizer.settings.bounding_box:
                logger.info("Analyzing video for stabilization...")
                if not stabilizer.analyze_video(str(input_file), progress_callback):
                    logger.warning("Stabilization analysis failed, proceeding without stabilization")
                    stabilizer = None
                else:
                    logger.info("Stabilization analysis complete")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                stabilizer = None
            
            # Calculate padding for frame numbers
            num_digits = len(str(total_frames))
            
            logger.info(f"Exporting {total_frames} frames as PNG sequence...")
            
            frame_count = 0
            
            while cap.isOpened():
                # Check for cancellation
                if self._cancel_event.is_set():
                    logger.warning("Export cancelled by user")
                    return False
                
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Apply stabilization FIRST on full frame
                if stabilizer:
                    frame = stabilizer.apply_stabilization(frame, frame_count)
                    if len(frame.shape) > 2 and frame.shape[2] == 4:
                        stab_alpha = frame[:, :, 3]
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    else:
                        stab_alpha = None
                else:
                    stab_alpha = None
                
                # Apply crop AFTER stabilization
                if crop:
                    x, y, w, h = crop
                    frame = frame[y:y+h, x:x+w]
                    if stab_alpha is not None:
                        stab_alpha = stab_alpha[y:y+h, x:x+w]
                
                # Process frame with chroma key
                rgba = processor.process_frame(frame)
                
                # Merge stabilization alpha with chroma key alpha
                if stab_alpha is not None:
                    rgba[:, :, 3] = cv2.bitwise_and(rgba[:, :, 3], stab_alpha)
                
                # Resize if needed
                if target_size:
                    rgba = cv2.resize(rgba, target_size, interpolation=cv2.INTER_AREA)
                
                # Optimization: Zero out RGB for fully transparent pixels
                transparent_mask = rgba[:, :, 3] == 0
                rgba[transparent_mask] = [0, 0, 0, 0]
                
                # Save frame
                frame_filename = output_path_obj / f"frame_{str(frame_count).zfill(num_digits)}.png"
                
                # Use OpenCV for PNG (faster, standard)
                # Convert RGBA to BGRA for OpenCV save
                bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
                cv2.imwrite(str(frame_filename), bgra)
                
                frame_count += 1
                self.stats.update(frame_count)
                
                # Report progress
                if progress_callback and frame_count % 5 == 0:
                    progress = frame_count / total_frames
                    eta = self.stats.eta_seconds
                    eta_str = f"{int(eta)}s remaining" if eta > 0 else ""
                    progress_callback(progress, eta_str)
            
            self.stats.finish()
            logger.success(
                f"Export complete: {frame_count} PNG frames in {self.stats.duration:.1f}s "
                f"({self.stats.fps:.1f} fps)"
            )
            
            if progress_callback:
                progress_callback(1.0, "Complete!")
            
            return True
            
        except ValidationError as e:
            logger.error(str(e))
            raise
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
        finally:
            if cap is not None:
                cap.release()
            self._is_processing = False

    def export_png_sequence(
        self,
        input_path: str,
        output_folder: str,
        settings: ChromaKeySettings,
        options: Optional[ProcessingOptions] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """Wrapper for backward compatibility"""
        return self.export_image_sequence(
            input_path, output_folder, settings, options, progress_callback
        )


# Backwards compatibility function
def process_video(
    input_path: str, 
    output_path: str, 
    h_min: int, s_min: int, v_min: int,
    h_max: int, s_max: int, v_max: int,
    crop: Optional[Tuple[int, int, int, int]] = None,
    progress_callback: Optional[Callable[[float], None]] = None
):
    """
    Legacy interface for video processing.
    Maintains backwards compatibility with the old processor.py API.
    """
    settings = ChromaKeySettings(
        h_min=h_min, h_max=h_max,
        s_min=s_min, s_max=s_max,
        v_min=v_min, v_max=v_max
    )
    
    options = ProcessingOptions(crop=crop)
    
    # Wrap old-style callback
    def wrapped_callback(progress: float, status: str):
        if progress_callback:
            progress_callback(progress)
    
    processor = VideoProcessor()
    processor.process(input_path, output_path, settings, options, wrapped_callback)
