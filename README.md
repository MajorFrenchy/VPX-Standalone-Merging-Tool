# 🎮 VPX Standalone Merging Tool

![Version](https://img.shields.io/badge/version-1.0-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-MIT-orange)

**The Ultimate Virtual Pinball Table Management Utility**

Automate the tedious process of organizing and merging all components needed for a complete VPX table setup. Simply drag and drop your `.vpx` files, and let the tool handle the rest!

---

## ✨ Features

### 🔍 Automatic Detection & Merging
- **ROM Files** - Automatically finds and copies `.zip` ROM files
- **DirectB2S Backglasses** - Detects and includes backglass files
- **UltraDMD/FlexDMD** - Smart detection of DMD packages
- **AltSound Packages** - Includes alternative sound packs
- **AltColor Packages** - Detects colorization files
- **PuP-Packs** - Automatically finds Pinup Player video packs
- **Music Files** - Scans and copies MP3/OGG music tracks
- **GitHub Patches** - Downloads standalone scripts from jsm174's repository

### ⚡ Powerful Interface
- 🖱️ **Drag-and-Drop** - Simple file handling
- 📊 **Real-time Progress** - Live progress bar and status updates
- 🎨 **Visual Separators** - Clean, organized audit log
- 🎲 **Random Quotes** - Fun pinball-themed messages
- 📈 **File Summary** - Complete breakdown of processed files

### 🎯 Three Operation Modes

1. **Make The Magic Happen** - Full merge with all components
2. **Create Clean VBS** - Extract VBS scripts from VPX files
3. **Patch Only** - Download GitHub patches without copying files

---

## 📥 Installation

### Option 1: Standalone Executable (Coming Soon!)
A standalone `.exe` for Windows is currently in development. No Python installation will be required!

### Option 2: Run from Python (Current Method)

#### 🪟 **Windows**

1. **Install Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)
   - ⚠️ **Important**: Check "Add Python to PATH" during installation

2. **Install required packages**
   ```bash
   pip install tkinterdnd2 olefile
   ```

3. **Download and run**
   ```bash
   # Download VPXmerge.py from releases
   python VPXmerge.py
   ```

#### 🍎 **macOS**

1. **Install Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)
   - Or use Homebrew: `brew install python3`

2. **Install Tkinter** (if not already included)
   ```bash
   brew install python-tk@3.12
   ```
   *Note: Adjust version to match your Python installation*

3. **Install required packages**
   ```bash
   pip3 install tkinterdnd2 olefile
   ```

4. **Download and run**
   ```bash
   # Download VPXmerge.py from releases
   python3 VPXmerge.py
   ```

#### ⚠️ **Troubleshooting**

- **tkinter not found**: Reinstall Python with Tkinter support enabled
- **Permission denied (Mac)**: Run `chmod +x VPXmerge.py` first
- **Drag-and-drop not working**: Ensure `tkinterdnd2` is properly installed

### Option 3: Clone from Source
```bash
# Clone the repository
git clone https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool.git
cd VPX-Standalone-Merging-Tool

# Install dependencies
pip install tkinterdnd2 olefile

# Run the application
python VPXmerge.py
```

---

## 📦 Dependencies

### Required Python Packages
- **tkinter** - GUI framework (usually included with Python)
- **tkinterdnd2** - Drag-and-drop support for Tkinter
- **olefile** - Reading and parsing OLE files (VPX files)

### Standard Library
- `os`, `shutil`, `json`, `threading`, `subprocess`, `re`, `random`, `urllib`

Install all dependencies:
```bash
pip install tkinterdnd2 olefile
```

---

## 🚀 Quick Start Guide

### 1. Configure Source Folders
Set up your source directories where the tool will look for components:
- **TABLES** - Your VPX tables and related files folder
- **VPINMAME** - VPinMAME folder containing ROMs, AltSound, AltColor
- **PUPVIDEOS** - Pinup Player video packs folder
- **MUSIC** - Music folder with MP3/OGG files

### 2. Set Export Target
Choose where you want the merged standalone tables to be created.

### 3. Enable Patch Lookup (Optional)
Check the "Enable Patch Lookup (GitHub)" option to automatically download standalone scripts from [jsm174's repository](https://github.com/jsm174/vpx-standalone-scripts).

### 4. Process Your Tables
- Drag and drop one or more `.vpx` files into the black audit window
- Review the detected components
- Click your desired operation mode:
  - **MAKE THE MAGIC HAPPEN** - Full merge
  - **CREATE CLEAN .VBS** - VBS extraction only
  - **PATCH ONLY** - GitHub patch download only

---

## 📋 What Gets Detected?

The tool scans your VPX file and automatically detects:

| Item | Detection Method | Location |
|------|-----------------|----------|
| **ROM** | `cGameName` in script | `/vpinmame/roms/` |
| **Backglass** | `[TableName].directb2s` | `/tables/` |
| **UltraDMD/FlexDMD** | `UseUltraDMD/UseFlexDMD = 1` | `/tables/[name].DMD/` |
| **AltSound** | ROM name match | `/vpinmame/altsound/` |
| **AltColor** | ROM name match | `/vpinmame/altcolor/` |
| **PuP-Pack** | ROM or table name | `/pupvideos/` |
| **Music** | `PlayMusic` references | `/music/` |
| **Patch** | GitHub fuzzy search | jsm174 repository |

---

## 🎨 Screenshots

### Main Interface
![Main Interface](screenshots/Screenshot%2001.jpg)

![Main Interface](screenshots/Screenshot%2002.jpg)

![Main Interface](screenshots/Screenshot%2003.jpg)

*Clean, intuitive interface with drag-and-drop support*



### Operation Summary
![Summary](screenshots/summary.png)
*Detailed breakdown of all processed files*

---

## 🛠️ Building from Source

### Create Standalone Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
pyinstaller --onefile --windowed \
    --name "VPX_Merging_Tool_v1.0" \
    --add-data "tkdnd;tkdnd" \
    --hidden-import=tkinterdnd2 \
    --hidden-import=olefile \
    VPXmerge.py
```

The executable will be in the `dist/` folder.

---

## 📖 Version History

### v1.0 (Initial Release)
- ✅ Automatic detection of 9 component types
- ✅ ROM, Backglass, UltraDMD/FlexDMD support
- ✅ AltSound, AltColor, PuP-Pack detection
- ✅ Music file scanning and copying
- ✅ GitHub patch lookup and download
- ✅ Progress bar with real-time updates
- ✅ Visual separators and enhanced UI
- ✅ Button hover effects
- ✅ File count summary
- ✅ Random pinball quotes
- ✅ Three operation modes (Full, VBS Only, Patch Only)
- ✅ Drag-and-drop interface
- ✅ VBS extraction with proper formatting
- ✅ Smart fuzzy matching for patches

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs via [Issues](https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/issues)
- Submit feature requests
- Create pull requests

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

**Coded by Major Frenchy with the help of Claude.ai**

Special thanks to:
- [jsm174](https://github.com/jsm174) for the VPX standalone scripts repository and VPX Standalone 
- The Virtual Pinball community
- All contributors and testers

---

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/discussions)

---

## ⭐ Star this repo if you find it useful!

Made with ❤️ for the Virtual Pinball community

##  Support me

If you find this utility useful and would like to support its development: You can con tribute in 2 ways, Getting the VPC Chat Discord server a Boost :" https://discord.com/invite/virtual-pinball-chat-652274650524418078 

or by contributing to the VPC Chat Patreon: https://www.patreon.com/c/vpchat
