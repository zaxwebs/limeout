"""
Limeout - Professional Green Screen Removal

Entry point for the application.
"""

import sys
from pathlib import Path

# Add project root to path for proper imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    """Run the ChromaKey application."""
    try:
        from gui.app import ChromaKeyApp
        
        app = ChromaKeyApp()
        app.mainloop()
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("\nPlease ensure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
