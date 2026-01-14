# Limeout

Limeout is a professional-grade desktop application designed for removing green and blue screens from videos. It provides advanced chroma keying capabilities, video stabilization, and high-quality WebM export with transparency.

## Features

- **Professional Chroma Keying**: Advanced HSV-based color selection with edge feathering, spill suppression, and defringing for semi-transparent details.
- **Video Stabilization**: Lock your footage to a tracked object (like a subject's eye or specific feature) to eliminate camera movement.
- **Real-Time Preview**: Inspect adjustments instantly with zoom, pan, and customizable backgrounds (checkerboard or solid colors).
- **Precision Cropping**: Margin-based cropping to clean up frame edges and remove unwanted tracking artifacts.
- **WebM Export**: Exports high-efficiency WebM videos with preserved alpha channel transparency, ready for compositing.
- **Modern Interface**: A clean, dark-themed GUI built for efficient workflow.

## Getting Started

### Prerequisites

- Python 3.10+
- OpenCV
- CustomTkinter
- NumPy
- Pillow

### Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. **Select Video**: Open a video file using the file dialog or by dragging and dropping it into the application window.
3. **Color Range**: Use the "Color Range" tab to select the background color to remove.
4. **Effects**:
   - **Edge Feather**: Soften the boundaries of the subject.
   - **Spill Suppression**: Remove reflected green/blue spill from the subject.
   - **Defringe**: Clean up semi-transparent areas (hair, glass, smoke).
5. **Stabilize**:
   - Go to the "Stabilize" tab.
   - Click "Select Region" and draw a box around a distinct feature on the subject.
   - Enable stabilization to lock the frame to that feature.
6. **Crop**: Trim unwanted edges or transparent borders caused by stabilization using the "Crop" tab.
7. **Export**: Click "Start Processing" to render the final video with transparency.

## Configuration

The application settings, including window dimensions and default paths, can be modified in `config.py` or the generated `config.json` file.

## License

MIT License
