# VPX Standalone Merging Tool

**The all-in-one utility for organizing, fixing, and preparing Visual Pinball X tables for standalone play.**

VPXmerge streamlines your VPX table collection by automating exports, script fixes, media organization, and asset detection — all with an intuitive drag-and-drop interface.

## Latest Release

- **v1.81**: `CREATE CLEAN .VBS` now only creates `.vbs` files and skips all other copy/detection actions.
- Full release history: [GitHub Releases](https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/releases)

[![Watch the video](https://img.youtube.com/vi/pPD1GJQKCT8/maxresdefault.jpg)](https://www.youtube.com/watch?v=pPD1GJQKCT8)
YOUTUBE VIDEO
---

## ✨ Features at a Glance

- 🎯 **One-Click Full Export** — VPX + VBS + Backglass + PUP + Media
- 🎬 **Smart Media Manager** — Fuzzy matching for POPMedia files
- 🖼️ **Live Table Previews** — See table artwork while you work
- 📦 **Batch Processing** — Handle entire collections at once
- 🎮 **ROM Detection** — 3-tier fallback for maximum compatibility
- 📝 **VBS Extraction** — Pull scripts from VPX files safely
  
---
Screenshots
<p align="center">
  <img src="https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/raw/main/screenshots/Screenshot%2001.jpg" width="50%" alt="VPXmerge Interface">
</p>
<br>
<p align="center">
  <img src="https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/raw/main/screenshots/Screenshot%2002.jpg" width="50%" alt="VPXmerge Interface">
</p>
<br>
<p align="center">
  <img src="https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/raw/main/screenshots/Screenshot%2003.jpg" width="50%" alt="VPXmerge Interface">
</p>

## 🚀 Installation

Use prebuilt release packages. No extra runtime setup is required.

Download from [GitHub Releases](https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/releases):

- **Windows:** `VPXmerge_v1.81-Windows.zip`
- **macOS:** `VPXmerge_v1.81-macOS.zip`
- **Linux x64:** `VPXmerge_v1.81-linux-amd64.run`
- **Linux ARM64:** `VPXmerge_v1.81-linux-arm64.run`

Linux quick launch:
```bash
chmod +x VPXmerge_v1.81-linux-*.run
./VPXmerge_v1.81-linux-*.run
```
Optional database (for enhanced preview matching):
- Place `pinballxdatabase.csv` next to the VPXmerge executable/app  
  Source: [VPS Database](https://virtualpinballspreadsheet.github.io/vps-db/)

---

## ⚡ Quick Start

1. **Launch VPXmerge** → Open the app/executable for your platform
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
| 🎯 **MAKE MAGIC HAPPEN** | Full export: VPX + backglass + PUP + media + patches |
| 📝 **EXTRACT VBS ONLY** | Save embedded scripts without copying tables |
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
# 1. Launch VPXmerge app
# 2. Browse → Select target folder
# 2. Drag VPX files
# 3. Enable "Include Media Files"
# 4. Click MAKE MAGIC HAPPEN
```

### Extract Scripts Only

```bash
# For script analysis/backup
# Click "EXTRACT VBS ONLY" instead
```

## 🐛 Troubleshooting

### "App does not start"
- On Linux, make the `.run` file executable, then launch it:
```bash
chmod +x VPXmerge_v1.81-linux-*.run
./VPXmerge_v1.81-linux-*.run
```
- On macOS, open the extracted app bundle.
- On Windows, run `VPXmerge.exe` from the extracted zip folder.

### "No table previews"
- Wait for "✓ Ready" status (database loading)
- Check internet connection (initial download)
- Add custom mapping if needed
- The image is not in the media database. 

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
- * jsm174 for the VPX standalone scripts repository and VPX Standalone
* SuperHack for his coding tips/help and his Media Database leveraged by this project. https://github.com/superhac
* All contributors and testers
- Virtual Pinball Spreadsheet maintainers ( DuxRero )


---

**⚡ VPXmerge — Because your tables deserve better organization.**

*Star this repo if you find it useful!* ⭐

Support me

If you find this utility useful and would like to support its development: You can con tribute in 2 ways, Getting the VPC Chat Discord server a Boost :" https://discord.com/invite/virtual-pinball-chat-652274650524418078
or by contributing to the VPC Chat Patreon: https://www.patreon.com/c/vpchat

https://github.com/MajorFrenchy/VPX-Standalone-Merging-Tool/raw/main/screenshots/Screenshot%2002.jpg
