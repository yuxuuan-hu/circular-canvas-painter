# Circular Canvas Painter

A minimalist painting application featuring a circular canvas and realistic pencil texture brush.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.7+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

- **Circular Canvas**: Unique circular drawing area with intuitive controls
- **Pencil Texture Brush**: Realistic pencil effect with grain simulation
- **Customizable Parameters**:
  - Brush size adjustment
  - Opacity control (0-100%)
  - Smoothing settings
- **Color Picker**: Built-in HSV color picker for precise color selection
- **Undo/Redo**: Support for multiple undo operations (up to 20 steps)
- **Save Options**: Export as PNG or JPEG format
- **Performance Optimized**: Frame-rate limiting (60 FPS) for smooth drawing

## Screenshots

### Drawing Demo
<img src="screenshots/drawing-demo.png" alt="Drawing Demo" width="400">

*Circular canvas with pencil texture brush in action*

### Color Picker
<img src="screenshots/color-picker.jpg" alt="Color Picker" width="400">

*Built-in HSV color picker for precise color selection*

## Requirements

- Python 3.7 or higher
- Pillow (PIL Fork)
- tkinter (usually included with Python)

## Installation

1. Clone this repository or download the source code:
```bash
git clone https://github.com/yuxuuan-hu/circular-canvas-painter.git
cd circular-canvas-painter
```

2. Install required dependencies:
```bash
pip install Pillow
```

## Usage

Run the application:
```bash
python3 test_fullcircle.py
```

### Controls

- **Left Mouse Button**: Draw with the brush
- **Color Indicator** (bottom of canvas): Click to open color picker
- **Undo Button** (left side): Undo last stroke
- **Clear Button** (right side): Clear entire canvas
- **Keyboard Shortcuts**:
  - `Ctrl+Z`: Undo
  - `Ctrl+S`: Save canvas
  - `Ctrl+N`: Clear canvas

### Brush Parameters

Adjust brush settings in real-time:
- **Size**: Control brush diameter (1-100 pixels)
- **Opacity**: Adjust transparency (1-100%)
- **Smoothing**: Control stroke interpolation (0.0-1.0)

## Technical Details

### Brush Rendering

The pencil texture brush uses a multi-layer rendering technique:

1. **Circular Mask**: Creates soft-edged circular base shape
2. **Noise Generation**: Simulates paper grain texture
3. **Brightness Enhancement**: Amplifies texture visibility
4. **Alpha Compositing**: Blends texture with mask for realistic effect

### Architecture

- **Canvas Size**: 720x720 pixels (configurable)
- **Color Space**: RGBA with 8-bit channels
- **Refresh Rate**: 60 FPS maximum (frame-rate limited)
- **Undo Stack**: 20 operations (configurable via `undo_limit`)

## Customization

### Adding Custom Brushes

The application supports custom brush loading (reserved for future extension). To add custom brushes:

1. Place brush image files (PNG with alpha channel) in the project directory
2. Update `BUILTIN_BRUSH_FILES` dictionary in the code:
```python
BUILTIN_BRUSH_FILES = {
    "My Custom Brush": "my_brush.png",
}
```

### Modifying Canvas Size

Edit the initialization parameters:
```python
self.W = self.H = 720  # Change to desired diameter
```

## Project Structure

```
application1_draw/
├── test_fullcircle.py    # Main application file
├── icon/                  # UI icon resources
│   ├── withdraw.jpg       # Undo button icon
│   └── delete.jpg         # Clear button icon
└── README.md             # This file
```

## Performance Tips

- Use lower opacity values for layered drawing effects
- Adjust smoothing for different stroke styles (lower = faster response)
- The canvas automatically clips strokes outside the circular boundary

## Troubleshooting

**Issue**: Icons not displaying
- Ensure `icon/` directory exists with `withdraw.jpg` and `delete.jpg`
- Icons will fallback to text buttons if missing

**Issue**: Slow performance on large brush sizes
- Reduce brush size or opacity
- Close other resource-intensive applications

**Issue**: tkinter not found
- Install tkinter: `sudo apt-get install python3-tk` (Linux)
- tkinter is included by default on Windows and macOS

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Future Enhancements

- [ ] Additional brush types (watercolor, marker, etc.)
- [ ] Layer support
- [ ] Pressure sensitivity for drawing tablets
- [ ] Canvas rotation and zoom
- [ ] Brush presets management
- [ ] Export to additional formats (SVG, PDF)

## License

This project is licensed under the MIT License - see below for details:

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Acknowledgments

- Built with Python and Pillow (PIL Fork)
- Inspired by traditional drawing applications with a modern twist

## Contact

For questions or feedback, please open an issue on the repository.

---

**Happy Drawing! 🎨**
