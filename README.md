# VPX Standalone Merging Tool

**The all-in-one utility for organizing, fixing, and preparing Visual Pinball X tables for standalone play.**

VPXmerge streamlines your VPX table collection by automating exports, script fixes, media organization, and asset detection — all with an intuitive drag-and-drop interface.

---

## ✨ Features at a Glance

- 🎯 **One-Click Full Export** — VPX + VBS + Backglass + PUP + Media
- 🔧 **Auto-Fix Scripts** — WScript.Shell, RegRead, deprecated B2S properties
- 🎬 **Smart Media Manager** — Fuzzy matching for POPMedia files
- 🖼️ **Live Table Previews** — See table artwork while you work
- 📦 **Batch Processing** — Handle entire collections at once
- 🎮 **ROM Detection** — 3-tier fallback for maximum compatibility
- 📝 **VBS Extraction** — Pull scripts from VPX files safely

---

## 🚀 Installation

### Prerequisites

- **Python 3.8 or higher** ([Download Python](https://www.python.org/downloads/))
- **Windows, macOS, or Linux**

### Step 1: Install Python Dependencies

Open Terminal (macOS/Linux) or Command Prompt (Windows) and run:

```bash
# Windows
pip install Pillow olefile tkinterdnd2 --break-system-packages

# macOS/Linux  
pip3 install Pillow olefile tkinterdnd2 --break-system-packages
```

**Required Packages:**
- `Pillow` — Image processing for table previews
- `olefile` — VPX file parsing (OLE format)
- `tkinterdnd2` — Drag & drop support

**Note:** `tkinter` is included with Python by default. If missing:
- **Ubuntu/Debian:** `sudo apt-get install python3-tk`
- **macOS:** Included with official Python installer
- **Windows:** Included with Python installer

### Step 2: Download VPXmerge

**Option A: Clone Repository**
```bash
git clone https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool.git
cd VPX-Standalone-Merging-Tool
```

**Option B: Download ZIP**
1. Click the green **Code** button above
2. Select **Download ZIP**
3. Extract to your preferred location

### Step 3: (Optional) Add Database

Place these files in the same directory as `VPXmerge.py`:

- **`pinballxdatabase.csv`** — Enhanced preview database ([VPS Database](https://virtualpinballspreadsheet.github.io/vps-db/))

### Step 4: Launch

```bash
# Windows
python VPXmerge.py

# macOS/Linux
python3 VPXmerge.py
```

---

## ⚡ Quick Start

1. **Launch VPXmerge** → Run `python VPXmerge.py`
2. **Set Export Target** → Click **Browse** to choose output folder
3. **Add Tables** → Drag VPX files or folders into the drop zone
4. **Preview** → See table images and detected assets
5. **Enable Options:**
   - ☑️ **Enable Patch Lookup** (GitHub script fixes)
   - ☑️ **Include Media Files** (POPMedia scanning)
6. **Click** 🎯 **MAKE MAGIC HAPPEN**

### Action Buttons

| Button | Function |
|--------|----------|
| 🎯 **MAKE MAGIC HAPPEN** | Full export: VPX + VBS + backglass + PUP + media + patches |
| 📝 **EXTRACT VBS ONLY** | Save embedded scripts without copying tables |
| 🔧 **FIX SCRIPT** | Auto-patch VPX scripts and save fixed version |
| 🗑️ **CLEAR** | Reset and start over |

---

## 🎯 Key Features

### 📦 Smart Table Export

**Automated Organization:**
```
Target/TableName/
├── TableName.vpx              # Original table
├── TableName.vbs              # Extracted script
├── TableName.directb2s        # Backglass (if found)
├── PUPVideos/                 # PinUP Player videos
└── medias/                    # Organized media files
    ├── table.mp4
    ├── fulldmd.mp4
    ├── wheel.png
    ├── bg.mp4
    ├── flyer.png
    └── media_log.ini
```

---

### 🔧 Auto-Fix Script Issues

**One-Click Fixes:**

✅ **WScript.Shell Removal** (any variable name: `wsh`, `WshShell`, etc.)
```vbscript
' Before
Set wsh = CreateObject("WScript.Shell")

' After  
' Set wsh = CreateObject("WScript.Shell") ' REMOVED
```

✅ **GetNVramPath() → Local Paths**
```vbscript
Function GetNVramPath()
    GetNVramPath = ".\pinmame\nvram\"
End Function
```

✅ **RegRead Stubbing**
```vbscript
' nvramPath = wsh.RegRead(...) ' REMOVED
nvramPath = ".\pinmame\nvram\" ' Auto-fixed
```

✅ **Deprecated B2S Properties**
```vbscript
' .ShowDMDOnly = 1 ' REMOVED - deprecated
' .ShowFrame = 0   ' REMOVED - deprecated  
```

✅ **Problematic COM Objects** (SAPI.SpVoice, WMPlayer.OCX)

---

### 🎬 Intelligent Media Manager

**POPMedia Scanning with Fuzzy Name Matching:**

| POPMedia Folder | Renamed To | Formats |
|----------------|------------|---------|
| Playfield | `table.mp4` | .mp4, .avi, .f4v |
| Menu | `fulldmd.mp4` | .mp4, .avi, .f4v |
| Loading | `loading.mp4` | .mp4, .avi, .f4v |
| Gameinfo | `flyer.png` | .png, .jpg |
| GameHelp | `rules.png` | .png, .jpg |
| Backglass | `bg.mp4` | .mp4, .avi, .f4v |
| AudioLaunch | `audiolaunch.mp3` | .mp3, .wav |
| Audio | `audio.mp3` | .mp3, .wav |
| Wheel | `wheel.png` | .png, .apng, .jpg |

**Fuzzy Matching Examples:**

| Your VPX File | POPMedia Filename | Match? |
|---------------|-------------------|--------|
| `Godzilla limited edition` | `Godzilla (Sega 1998) VPW v1.1.mp4` | ✅ 100% |
| `Bugs Bunny_s Birthday Ball` | `Bugs Bunny's Birthday Ball.png` | ✅ 100% |
| `Star Trek LE (Stern 2013)` | `Star Trek (Stern 2013).mp4` | ✅ 100% |

**How It Works:**
- Strips manufacturer, year, version (`VPW`, `MOD`, `v1.1`)
- Normalizes apostrophes, underscores (`_s` → `s`)
- Removes noise words (`limited`, `edition`, `le`, `pro`)
- ≥50% keyword overlap = match
- Skips tables with existing `medias/` folder

---

### 🎮 ROM & Asset Detection

**3-Tier ROM Detection:**
1. Primary: `cGameName`, `GameName`, `RomName`
2. Fallback: Explicit `cGameName =` search
3. Fallback: `OptRom =` pattern

**Also Detects:**
- ✅ Backglass (.directb2s files)
- ✅ DMD (UltraDMD, FlexDMD)
- ✅ PUP Packs (PinUP Player videos)

---

### 🖼️ Live Table Previews

- Adaptive grid (1–6 tables)
- VPinMAME database (5,300+ images)
- Fuzzy image matching
- CSV database support

**Custom Mappings:**
```ini
# custom_mappings.txt
Star Trek LE (Stern 2013) = stle_150
Gilligan's Island = gilligans_island
```

---

## 📖 Usage Examples

### Basic Export

```bash
python VPXmerge.py
# 1. Browse → Select target folder
# 2. Drag VPX files
# 3. Enable "Include Media Files"
# 4. Click MAKE MAGIC HAPPEN
```

### Extract Scripts Only

```bash
# For script analysis/backup
# Click "EXTRACT VBS ONLY" instead
```

### Fix Problematic Table

```bash
# Drag single VPX
# Click "FIX SCRIPT"
# Fixed .vbs saved alongside VPX
```

---

## 🐛 Troubleshooting

### "Module not found: tkinter"
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# macOS (reinstall Python from python.org)
# Windows (reinstall with "tcl/tk and IDLE" checked)
```

### "Module not found: PIL"
```bash
pip install Pillow --break-system-packages
```

### "No table previews"
- Wait for "✓ Ready" status (database loading)
- Check internet connection (initial download)
- Add custom mapping if needed

### "Media not copying"
- ☑️ "Include Media Files" enabled?
- ☑️ POPMedia folder structure: `POPMedia/Visual Pinball X/`?
- ☑️ POPMedia one directory up from PUP source?

---

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- Additional UI themes
- More auto-fix patterns
- Additional media sources
- Enhanced fuzzy matching

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push and open PR

---

## 📜 License

MIT License - Free to use, modify, and distribute.

---

## 🙏 Acknowledgments

**Created by:** Major Frenchy  
**Powered by:** Claude (Anthropic)

**Special Thanks:**
- VPinMAME community
- Virtual Pinball Spreadsheet maintainers
- PinballX database contributors

---

**⚡ VPXmerge — Because your tables deserve better organization.**

*Star this repo if you find it useful!* ⭐
