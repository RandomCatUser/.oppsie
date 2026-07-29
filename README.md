# .oppsie Image Format & Converter App

A lightweight, fast, and simple image format called **.oppsie** (inspired by QOI - Quite OK Image Format), complete with a reference Python codec, batch format converter, and a pair of retro-styled desktop applications.

---

##  Features

- **Custom Format Spec (`.oppsie`)**: High-performance, simple byte-level encoding utilizing run-length encoding (RLE), color differences, luma differences, and a running palette of the last 64 seen pixels.
- **Lossless & Lossy Modes**: Native support for 1-7 bit color quantization in the flags header to dramatically reduce file sizes on photographs and gradients.
- **EXIF Metadata Passthrough**: Custom EXIF chunk injection at the tail of the pixel stream ensuring JPEG EXIF metadata is preserved in round-trip conversions.
- **GUI Converter App (PyQt5)**: A feature-rich Windows 95-themed conversion dashboard with:
  - Frameless rounded window with custom title bar.
  - Drag-and-drop file queue with per-file format targeting.
  - Animated glowing progress bar and status indicator.
  - Controls for output format selection, compression level (lossless / 1–7), overwrite mode, and output folder.
  - Hover-to-preview thumbnails and keyboard shortcuts (`Ctrl+O`, `Ctrl+Enter`, `Delete`, `Esc`, `F1`).
- **Image Viewer App (Tkinter)**: A standalone 90s-themed image viewer with:
  - Classic Windows 95-style 3D raised/sunken borders.
  - Zoom, pan (click-and-drag), fit-to-window, and reset controls.
  - Mouse wheel zoom support.
  - Opens `.oppsie`, PNG, JPEG, BMP, WebP, and GIF files.
- **Batch Converter**: Convert entire folders of PNG, JPEG, WebP, BMP, and GIF images to and from `.oppsie`.

---

##  Repository Structure

```
├── oppsie/               # Codec Library
│   ├── __init__.py       # Package entry exposing encode() and decode()
│   ├── encoder.py        # Raw pixels -> .oppsie byte stream
│   ├── decoder.py        # .oppsie byte stream -> PIL Image
│   ├── benchmark.py      # Format performance comparison tool
│   └── OPPSIE_SPEC.md    # Byte-level format specification
├── converter/            # Format Converter Engine
│   ├── __init__.py       # Converter entry
│   ├── to_oppsie.py      # CLI for converting images to .oppsie
│   ├── from_oppsie.py    # CLI for converting .oppsie to standard formats
│   └── batch_runner.py   # CLI for batch converting directories
├── app/                  # Desktop GUI Applications
│   ├── __init__.py       
│   ├── main.py           # PyQt5 Windows 95-themed Converter dashboard
│   ├── gui.py            # Tkinter 90s-themed standalone Image Viewer
│   ├── guibackup.py      # Backup of previous Tkinter viewer (modern dark theme)
│   └── mainbackup.py     # Backup of previous PyQt5 app (Catppuccin theme)
├── files/                # File uploads & exports
│   ├── uploads/          # Source images and .oppsie files
│   └── exports/          # Converted output files
├── tests/                # Test Suite
│   ├── test_codec.py     # Roundtrip and lossy correctness unit tests
│   ├── test_converter.py # Format conversion and batch unit tests
│   ├── test_gui_loader.py# Viewer image loading test
│   └── test_app_loader.py # Converter app helper tests
├── run_app.bat           # Launch the converter app without commands
├── run_viewer.bat        # Launch the image viewer without commands
├── README.md             # Project overview and guide
├── requirements.txt      # Dependency listing
└── LICENSE               # License file
```

---

##  Getting Started

### 1. Installation

Install dependencies (Pillow, PyQt5):

```bash
pip install -r requirements.txt
```

### 2. Running the Converter GUI App (PyQt5)

You can launch the Windows 95-themed conversion dashboard using any of the following:

- **Windows Batch File**: Double-click [run_app.bat](file:///C:/projects/Image%20format/run_app.bat) in the project root directory.
- **Python CLI**: Run the following in your terminal:
  ```bash
  python app/main.py
  ```

### 3. Running the Image Viewer (Tkinter)

Open the standalone 90s-themed image viewer:

- **Windows Batch File**: Double-click [run_viewer.bat](file:///C:/projects/Image%20format/run_viewer.bat) in the project root directory.
- **Python CLI**: Run the following in your terminal:
  ```bash
  python app/gui.py
  ```

### 4. Interactive Jupyter Demo

Open the interactive notebook [demo.ipynb](file:///C:/projects/Image%20format/demo.ipynb) in Jupyter to experiment with the code step-by-step:
```bash
jupyter notebook demo.ipynb
```

### 5. CLI Conversion Examples


**Convert an image to lossless `.oppsie`:**
```bash
python converter/to_oppsie.py my_photo.png output.oppsie
```

**Convert an image to lossy `.oppsie` (quantization level 3):**
```bash
python converter/to_oppsie.py my_photo.jpg output.oppsie --lossy 3
```

**Convert an `.oppsie` back to PNG:**
```bash
python converter/from_oppsie.py output.oppsie recovered.png
```

**Batch convert a whole folder of images to `.oppsie`:**
```bash
python converter/batch_runner.py ./my_images ./converted_opps oppsie
```

---

##  Benchmark Results

Running the benchmark script (`python oppsie/benchmark.py`) yields the following results on 512x512 sample images:

### Flat Graphic (512x512, RGB)
*Consists of solid blocks of color, text, and clean shapes.*

| Format | Size (KB) | Encode Time (ms) | Decode Time (ms) |
| :--- | :--- | :--- | :--- |
| **OPPSIE (Lossless)** | **7.08 KB** | **170.60 ms** | **40.64 ms** |
| OPPSIE (Lossy L3) | 7.08 KB | 182.65 ms | 42.67 ms |
| OPPSIE (Lossy L5) | 9.49 KB | 184.82 ms | 40.81 ms |
| PNG | 2.81 KB | 4.35 ms | 0.14 ms |
| JPEG (Q80) | 12.62 KB | 1.70 ms | 0.12 ms |
| WebP (Lossless) | 0.61 KB | 9.46 ms | 0.37 ms |

### Gradient Photo (512x512, RGB)
*Smooth color ramps simulating photographic content.*

| Format | Size (KB) | Encode Time (ms) | Decode Time (ms) |
| :--- | :--- | :--- | :--- |
| **OPPSIE (Lossless)** | **257.02 KB** | **441.09 ms** | **318.47 ms** |
| **OPPSIE (Lossy L3)** | **116.37 KB** | **273.19 ms** | **79.72 ms** |
| **OPPSIE (Lossy L5)** | **31.55 KB** | **200.87 ms** | **48.33 ms** |
| PNG | 7.17 KB | 8.22 ms | 0.12 ms |
| JPEG (Q80) | 10.40 KB | 1.74 ms | 0.11 ms |
| WebP (Lossless) | 3.60 KB | 143.60 ms | 0.30 ms |

### Pixel Art (512x512, RGBA)
*Small palette grid graphic with full transparency.*

| Format | Size (KB) | Encode Time (ms) | Decode Time (ms) |
| :--- | :--- | :--- | :--- |
| **OPPSIE (Lossless)** | **16.03 KB** | **131.97 ms** | **50.49 ms** |
| OPPSIE (Lossy L3) | 16.04 KB | 199.36 ms | 52.62 ms |
| OPPSIE (Lossy L5) | 26.10 KB | 199.11 ms | 53.09 ms |
| PNG | 2.59 KB | 3.92 ms | 0.11 ms |
| WebP (Lossless) | 0.18 KB | 16.18 ms | 0.28 ms |

---

##  Codec Analysis & Observations

1. **Python vs Native Timings**: PNG, JPEG, and WebP encode/decode times in our benchmark are exceptionally fast because they call compiled C libraries (libpng, libjpeg, libwebp) wrapped inside Pillow. Our reference `.oppsie` codec is written in pure Python, making its performance (100–400 ms) very impressive for a byte-level loop.
2. **Quantization Behavior**: 
   - **For Photographs/Gradients**: Quantization (`flags > 0`) works wonders, reducing size from 257.02 KB down to 31.55 KB (an 87.7% reduction).
   - **For Pixel Art/Flat Graphics**: Applying heavy quantization (e.g. L5) can actually *increase* file size. This occurs because quantization creates large steps in color value. When adjacent colors shift from one quantized bin to another, the differences exceed the threshold of `OPPS_DIFF` ([-2, 1]) and `OPPS_LUMA` ([-32, 31]), forcing the encoder to emit raw `OPPS_RGB` chunks (4 bytes) instead of compact 1 or 2-byte difference chunks.

---

##  Testing

Run unit tests covering roundtrip verification, transparency correctness, and CLI conversions:

```bash
python -m unittest discover tests/
```

**This is only a joke that I built to impress my best friend so you know :3**
