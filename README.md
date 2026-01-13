# 🎬 Limeout

A professional-grade desktop application for removing green/blue screens from videos and exporting them as WebM files with transparency (alpha channel).

## ✨ Features

- **High-Quality Chroma Keying**: Advanced HSV-based color selection with edge feathering and spill suppression.
- **Real-Time Preview**: Instantly see technical adjustments on a live preview with custom background options (checkerboard, black, white, red, blue, magenta).
- **Precision Cropping**: Margin-based cropping (Left, Right, Top, Bottom) to clean up edges.
- **Frame Navigation**: Step through videos frame-by-frame for precise tuning.
- **WebM Export**: Exports high-quality WebM videos with preserved alpha transparency.
- **Modern UI**: Built with CustomTkinter for a sleek, dark-themed professional experience.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- OpenCV
- CustomTkinter
- NumPy
- Pillow

### Installation

1. Clone the repository

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. **Select Video**: Click the "Select Video" button or drag and drop a video file into the preview area.
3. **Adjust Color**: Use the "Color Range" tab to target your green/blue screen.
4. **Fine-Tune**: 
   - Use **Edge Feather** to soften the subject's edges.
   - Adjust **Spill Suppression** to remove color reflections from the subject.
5. **Crop**: Use the "Crop" tab to remove unwanted areas by adjusting the margins.
6. **Preview**: Switch to the "Preview" tab to check your work against different background colors.
7. **Export**: Click "Start Processing" and choose your output location.

## 🛠️ Configuration

The application stores settings and presets in `config.py` and `config.json`. Window dimensions and default paths can be adjusted there.

## 📄 License

MIT License
