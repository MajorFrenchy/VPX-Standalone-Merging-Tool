import tkinter as tk
from tkinter import filedialog, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
import olefile, os, shutil, json, threading, subprocess, re, random, urllib.request, urllib.error

VERSION = "1.0"

class VPXStandaloneMergingUtility:
    def __init__(self, root):
        self.root = root
        self.root.title(f"VPX UTILITY v{VERSION} - FULL RESTORATION")
        self.root.geometry("900x920") 
        self.root.resizable(False, False) 
        self.root.configure(bg="#1e1e1e") 
        
        self.config_file = os.path.join(os.path.expanduser("~"), ".vpx_utility_config.json")
        self.sources = {"tables": tk.StringVar(), "vpinmame": tk.StringVar(), "pupvideos": tk.StringVar(), "music": tk.StringVar()}
        self.target = tk.StringVar()
        self.enable_patch_lookup = tk.BooleanVar(value=True)  # Default: checked
        
        # File tracking for summary
        self.file_stats = {
            'tables': 0, 'roms': 0, 'backglass': 0, 'altsound': 0, 'altcolor': 0, 
            'pup_packs': 0, 'music_tracks': 0, 'patches': 0, 'vbs_files': 0
        }
        
        self.load_settings()
        self.vpx_files = []
        self.setup_ui()

    def load_settings(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    for key, val in data.get("sources", {}).items():
                        if key in self.sources: self.sources[key].set(val)
                    if "target" in data: self.target.set(data["target"])
            except: pass

    def setup_ui(self):
        btn_opt, l_btn_opt = {"font": ("Arial", 10, "bold"), "fg": "#000000"}, {"font": ("Arial", 12, "bold"), "fg": "#000000", "height": 2}
        tk.Label(self.root, text="VPX STANDALONE MERGING TOOL", font=("Arial", 22, "bold"), fg="#ffffff", bg="#1e1e1e").pack(pady=(15, 5))
        src_container = tk.LabelFrame(self.root, text=" FOLDER SOURCE ", bg="#1e1e1e", fg="#00ffcc", font=("Arial", 10, "bold"))
        src_container.pack(fill="x", padx=30, pady=5)
        for key in ["tables", "vpinmame", "pupvideos", "music"]:
            row = tk.Frame(src_container, bg="#1e1e1e"); row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=key.upper() + ":", bg="#1e1e1e", fg="#ffffff", font=("Menlo", 9), width=12, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=self.sources[key], bg="#2a2a2a", fg="#aaaaaa", font=("Menlo", 9)).pack(side="left", fill="x", expand=True, padx=5)
            tk.Button(row, text="SET", command=lambda k=key: self.browse_path(k, "source"), **btn_opt).pack(side="right")
        tgt_container = tk.LabelFrame(self.root, text=" EXPORT TARGET ", bg="#1e1e1e", fg="#ffcc00", font=("Arial", 10, "bold"))
        tgt_container.pack(fill="x", padx=30, pady=5)
        tk.Entry(tgt_container, textvariable=self.target, bg="#2a2a2a", fg="#ffcc00", font=("Menlo", 10)).pack(side="left", fill="x", expand=True, padx=15, pady=8)
        tk.Button(tgt_container, text="BROWSE", command=lambda: self.browse_path(None, "target"), **btn_opt).pack(side="right", padx=10)
        
        # Patch Lookup Checkbox
        patch_frame = tk.Frame(self.root, bg="#1e1e1e")
        patch_frame.pack(fill="x", padx=30, pady=5)
        tk.Checkbutton(patch_frame, text="Enable Patch Lookup (GitHub)", variable=self.enable_patch_lookup, 
                      bg="#1e1e1e", fg="#00ff00", selectcolor="#2a2a2a", 
                      font=("Arial", 10, "bold"), activebackground="#1e1e1e", 
                      activeforeground="#00ff00").pack(anchor="w")
        
        # Progress Bar
        self.progress_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.progress_frame.pack(fill="x", padx=30, pady=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate', length=840)
        self.progress_bar.pack(fill="x")
        self.progress_label = tk.Label(self.progress_frame, text="", bg="#1e1e1e", fg="#00ff00", font=("Arial", 9))
        self.progress_label.pack()
        self.progress_frame.pack_forget()  # Hide initially
        
        self.audit_frame = tk.Frame(self.root, bg="#000000", bd=2, relief="sunken", height=400); self.audit_frame.pack_propagate(False); self.audit_frame.pack(fill="x", padx=30, pady=10)
        self.audit_list = tk.Text(self.audit_frame, bg="#000000", fg="#ffffff", font=("Menlo", 11), state="disabled", padx=15, pady=10)
        self.audit_list.pack(fill="both", expand=True)
        self.audit_list.tag_configure("table_name", foreground="#00ccff", font=("Menlo", 12, "bold"))
        self.audit_list.tag_configure("found", foreground="#00ff00")
        self.audit_list.tag_configure("missing", foreground="#ffffff")
        self.audit_list.tag_configure("yellow", foreground="#ffff00", font=("Menlo", 11, "bold"))
        self.audit_list.tag_configure("white", foreground="#ffffff", font=("Menlo", 11, "bold"))
        self.audit_list.drop_target_register(DND_FILES); self.audit_list.dnd_bind('<<Drop>>', self.handle_drop)
        btn_frame = tk.Frame(self.root, bg="#1e1e1e"); btn_frame.pack(fill="x", padx=30, pady=10)
        self.btn_full = tk.Button(btn_frame, text="MAKE THE MAGIC HAPPEN", state="disabled", bg="#00ff00", command=lambda: self.start_thread("full"), **l_btn_opt)
        self.btn_full.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_full.bind("<Enter>", lambda e: self.btn_full.config(bg="#33ff33") if self.btn_full['state'] == 'normal' else None)
        self.btn_full.bind("<Leave>", lambda e: self.btn_full.config(bg="#00ff00") if self.btn_full['state'] == 'normal' else None)
        
        self.btn_vbs = tk.Button(btn_frame, text="CREATE CLEAN .VBS", state="disabled", bg="#00ccff", command=lambda: self.start_thread("vbs"), **l_btn_opt)
        self.btn_vbs.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_vbs.bind("<Enter>", lambda e: self.btn_vbs.config(bg="#33ddff") if self.btn_vbs['state'] == 'normal' else None)
        self.btn_vbs.bind("<Leave>", lambda e: self.btn_vbs.config(bg="#00ccff") if self.btn_vbs['state'] == 'normal' else None)
        
        self.btn_patch = tk.Button(btn_frame, text="PATCH ONLY", state="disabled", bg="#ff9900", command=lambda: self.start_thread("patch"), **l_btn_opt)
        self.btn_patch.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.btn_patch.bind("<Enter>", lambda e: self.btn_patch.config(bg="#ffaa33") if self.btn_patch['state'] == 'normal' else None)
        self.btn_patch.bind("<Leave>", lambda e: self.btn_patch.config(bg="#ff9900") if self.btn_patch['state'] == 'normal' else None)
        
        tk.Button(self.root, text="CLEAR LIST", command=self.clear_list, bg="#ff4444", **btn_opt).pack(pady=(5, 10))
        
        # Credits
        tk.Label(self.root, text="Coded by Major Frenchy with the help of Claude.ai", 
                font=("Arial", 8), fg="#888888", bg="#1e1e1e").pack(pady=(0, 10))

    def log_audit(self, msg, tag=None):
        self.audit_list.config(state="normal"); self.audit_list.insert(tk.END, msg + "\n", tag); self.audit_list.config(state="disabled"); self.audit_list.see(tk.END)
    
    def log_separator(self, style="single"):
        """Add visual separator lines"""
        if style == "double":
            self.log_audit("╔═══════════════════════════════════════════════════════╗", "white")
        elif style == "single":
            self.log_audit("─" * 55, "white")
        elif style == "bottom":
            self.log_audit("╚═══════════════════════════════════════════════════════╝", "white")

    def browse_path(self, key, mode):
        path = filedialog.askdirectory()
        if path:
            if mode == "source": self.sources[key].set(path)
            else: self.target.set(path)
            self.save_settings()

    def extract_script(self, path):
        try:
            if path.lower().endswith('.vbs'):
                with open(path, 'r', encoding='latin-1') as f: return f.read()
            if olefile.isOleFile(path):
                with olefile.OleFileIO(path) as ole:
                    for s in ole.listdir():
                        if any(x in str(s).lower() for x in ["gamestru", "mac", "version"]): continue
                        with ole.openstream(s) as stream:
                            d = stream.read(); idx = d.find(b'Option')
                            if idx == -1: idx = d.find(b'Const')
                            if idx != -1: 
                                # Extract the script and decode
                                raw_script = d[idx:].decode('latin-1', errors='ignore')
                                # Clean up line endings - remove extra carriage returns
                                # Replace any \r\r with single \r, and normalize to \r\n
                                cleaned = raw_script.replace('\r\r', '\r')
                                # Ensure proper Windows line endings
                                cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
                                return cleaned.strip()
        except: pass
        return None

    def find_github_patch(self, table_name):
        """Search GitHub repo for matching patch file using fuzzy matching"""
        try:
            # GitHub API endpoint for repo contents
            api_url = "https://api.github.com/repos/jsm174/vpx-standalone-scripts/contents"
            
            # Get list of folders in the repo
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', 'VPX-Utility')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                folders = json.loads(response.read().decode())
            
            # Normalize table name for fuzzy matching
            def normalize(name):
                # Remove file extension, special chars, convert to lowercase
                name = os.path.splitext(name)[0]
                name = re.sub(r'[^\w\s]', '', name).lower()
                name = re.sub(r'\s+', '', name)
                return name
            
            normalized_table = normalize(table_name)
            
            # Try to find matching folder
            best_match = None
            best_score = 0
            
            for item in folders:
                if item['type'] == 'dir':
                    folder_name = item['name']
                    normalized_folder = normalize(folder_name)
                    
                    # Calculate similarity score (simple character overlap)
                    if normalized_folder == normalized_table:
                        best_match = item
                        break  # Exact match found
                    elif normalized_table in normalized_folder or normalized_folder in normalized_table:
                        # Partial match - calculate score
                        score = len(set(normalized_table) & set(normalized_folder))
                        if score > best_score:
                            best_score = score
                            best_match = item
            
            if best_match:
                # Get contents of the matched folder
                folder_url = best_match['url']
                req = urllib.request.Request(folder_url)
                req.add_header('User-Agent', 'VPX-Utility')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    files = json.loads(response.read().decode())
                
                # Find the .vbs file (not .original, not starting with "patch:")
                for file in files:
                    if file['type'] == 'file' and file['name'].endswith('.vbs'):
                        if not file['name'].endswith('.original') and not file['name'].startswith('patch:'):
                            return {
                                'found': True,
                                'name': file['name'],
                                'download_url': file['download_url'],
                                'folder': best_match['name']
                            }
            
            return {'found': False}
        
        except Exception as e:
            return {'found': False, 'error': str(e)}

    def download_patch(self, download_url, save_path):
        """Download patch file from GitHub"""
        try:
            req = urllib.request.Request(download_url)
            req.add_header('User-Agent', 'VPX-Utility')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
            
            with open(save_path, 'wb') as f:
                f.write(content)
            
            return True
        except:
            return False

    def audit_logic(self, mode):
        # Random pinball quotes for "Make Magic Happen"
        pinball_quotes = [
            "TILT! Just kidding... let's roll!",
            "Bumpers engaged, flippers ready!",
            "Time to rack up some high scores!",
            "Multi-ball mode: ACTIVATED!",
            "Nudge it real good!",
            "Extra ball earned! Let's go!",
            "Jackpot incoming!",
            "Skill shot lined up perfectly!",
            "The silver ball never lies!",
            "Flipper fingers ready!",
            "Lock and load those balls!",
            "Plunger pulled, magic initiated!",
            "Warning: Addictive gameplay ahead!",
            "Remember: It's all in the wrists!",
            "The ball is wild, the table is yours!",
            "Gravity? Never heard of her!",
            "Launching into pinball paradise!",
            "Table manners: Optional. Skill: Required!",
            "Keep your eye on the ball... literally!",
            "Free game? No, better... FREE FILES!"
        ]
        
        # Reset file stats
        self.file_stats = {
            'tables': 0, 'roms': 0, 'backglass': 0, 'altsound': 0, 'altcolor': 0, 
            'pup_packs': 0, 'music_tracks': 0, 'patches': 0, 'vbs_files': 0
        }
        
        t_dir, v_dir, p_dir, m_dir = [self.sources[k].get() for k in ["tables", "vpinmame", "pupvideos", "music"]]
        target_root = self.target.get()
        
        # Show progress bar for non-scan modes
        if mode != "scan":
            self.progress_frame.pack(fill="x", padx=30, pady=5)
            self.progress_bar['value'] = 0
            self.progress_label.config(text="Initializing...")
        
        # Show random quote and progress message for full mode
        if mode == "full":
            quote = random.choice(pinball_quotes)
            self.log_audit(quote, "found")
            self.log_audit("--- COPYING IN PROGRESS ---", "white")
            self.log_audit("")
        elif mode == "patch":
            self.log_audit("🔍 SEARCHING FOR PATCHES...", "white")
            self.log_audit("")
        
        total_files = len(self.vpx_files)
        
        for idx, f in enumerate(self.vpx_files):
            fname = os.path.basename(f); v_base = os.path.splitext(fname)[0]; script = self.extract_script(f); table_dest = os.path.join(target_root, v_base)
            
            # Update progress
            if mode != "scan":
                progress = ((idx + 1) / total_files) * 100
                self.progress_bar['value'] = progress
                self.progress_label.config(text=f"Processing {idx + 1}/{total_files}: {v_base}")
                self.root.update_idletasks()
            
            # Setup Folder Structure
            if mode != "scan": os.makedirs(table_dest, exist_ok=True)
            
            # Visual separator for table
            if mode == "scan": 
                self.log_separator("double")
                self.log_audit(f"  Table: {fname}", "table_name")
                self.log_separator("single")
            elif mode == "full": 
                shutil.copy2(f, os.path.join(table_dest, fname))
                self.file_stats['tables'] += 1
            elif mode == "patch": 
                self.log_separator("double")
                self.log_audit(f"  Table: {fname}", "table_name")
                self.log_separator("single")

            if script:
                # Skip ROM/Backglass/Music/etc. in patch-only mode
                if mode != "patch":
                    # 1. ROM Logic
                    rom_m = re.search(r'cGameName\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                    rom = rom_m.group(1) if rom_m else None
                    if rom:
                        r_src = os.path.join(v_dir, "roms", f"{rom}.zip")
                        if os.path.exists(r_src):
                            if mode == "scan": self.log_audit(f"1-ROM: {rom} (DETECTED)", "found")
                            elif mode == "full": 
                                rd = os.path.join(table_dest, "pinmame", "roms")
                                os.makedirs(rd, exist_ok=True)
                                shutil.copy2(r_src, rd)
                                self.file_stats['roms'] += 1
                        else:
                            if mode == "scan": self.log_audit(f"1-ROM: {rom} (NOT FOUND)", "missing")

                    # 2. Backglass 
                    b2s_src = os.path.join(t_dir, f"{v_base}.directb2s")
                    if os.path.exists(b2s_src):
                        if mode == "scan": self.log_audit(f"2-BACKGLASS: {v_base}.directb2s (DETECTED)", "found")
                        elif mode == "full": 
                            shutil.copy2(b2s_src, os.path.join(table_dest, f"{v_base}.directb2s"))
                            self.file_stats['backglass'] += 1
                    else:
                        if mode == "scan": self.log_audit("2-BACKGLASS: NOT FOUND", "missing")

                    # 3. UltraDMD / FlexDMD Detection
                    uses_ultradmd = re.search(r'UseUltraDMD\s*=\s*1', script, re.IGNORECASE)
                    uses_flexdmd = re.search(r'UseFlexDMD\s*=\s*1', script, re.IGNORECASE)
                    
                    if uses_ultradmd or uses_flexdmd:
                        dmd_found = False
                        dmd_type = "UltraDMD" if uses_ultradmd else "FlexDMD"
                        
                        # Check for DMD folders using rom name or table name
                        search_names = [rom, v_base] if rom else [v_base]
                        dmd_extensions = ['.DMD', '.UltraDMD', 'DMD']
                        
                        for search_name in search_names:
                            if dmd_found:
                                break
                            for ext in dmd_extensions:
                                dmd_folder = f"{search_name}{ext}"
                                dmd_src = os.path.join(t_dir, dmd_folder)
                                
                                if os.path.exists(dmd_src) and os.path.isdir(dmd_src):
                                    dmd_found = True
                                    if mode == "scan":
                                        self.log_audit(f"3-ULTRADMD/FLEXDMD: {dmd_folder} (DETECTED)", "found")
                                    elif mode == "full":
                                        shutil.copytree(dmd_src, os.path.join(table_dest, dmd_folder), dirs_exist_ok=True)
                                        self.file_stats['ultradmd'] = self.file_stats.get('ultradmd', 0) + 1
                                    break
                        
                        if mode == "scan" and not dmd_found:
                            self.log_audit(f"3-ULTRADMD/FLEXDMD: NOT FOUND (Script uses {dmd_type})", "missing")

                    # 4. AltSound / 5. AltColor / 6. PuP-Pack
                    if rom:
                        for folder, label, num in [("altsound", "4-ALTSOUND", "full"), ("altcolor", "5-ALTCOLOR", "full")]:
                            src = os.path.join(v_dir, folder, rom)
                            if os.path.exists(src):
                                if mode == "scan": self.log_audit(f"{label}: {rom} (DETECTED)", "found")
                                elif mode == "full": 
                                    shutil.copytree(src, os.path.join(table_dest, "pinmame", folder, rom), dirs_exist_ok=True)
                                    if folder == "altsound": self.file_stats['altsound'] += 1
                                    else: self.file_stats['altcolor'] += 1
                            else:
                                if mode == "scan": self.log_audit(f"{label}: NOT FOUND", "missing")
                    
                    pup_name = rom if rom else v_base
                    pup_src = os.path.join(p_dir, pup_name)
                    if os.path.exists(pup_src):
                        if mode == "scan": self.log_audit(f"6-PUP-PACK: {pup_name} (DETECTED)", "found")
                        elif mode == "full": 
                            shutil.copytree(pup_src, os.path.join(table_dest, "pupvideos", pup_name), dirs_exist_ok=True)
                            self.file_stats['pup_packs'] += 1
                    else:
                        if mode == "scan": self.log_audit("6-PUP-PACK: NOT FOUND", "missing")

                    # 7. Music Logic (Flat Export to 'music' folder)
                    m_found, f_folders = False, set([v_base])
                    if rom: f_folders.add(rom)
                    pm_matches = re.findall(r'PlayMusic\s*"?([^"\r\n]+)', script, re.IGNORECASE)
                    for path in pm_matches:
                        if "\\" in path: f_folders.add(path.split("\\")[0].strip())
                    subdir_m = re.search(r'MusicSubDirectory\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                    if subdir_m: f_folders.add(subdir_m.group(1).replace("\\", "").strip())
                    
                    if os.path.exists(m_dir):
                        all_sub = [d for d in os.listdir(m_dir) if os.path.isdir(os.path.join(m_dir, d))]
                        for target in sorted(f_folders):
                            for real in all_sub:
                                if real.lower() == target.lower():
                                    m_found = True; full_m = os.path.join(m_dir, real)
                                    if mode == "scan":
                                        # Collect all music files
                                        music_files = sorted([trk for trk in os.listdir(full_m) if trk.lower().endswith(('.mp3', '.ogg'))])
                                        files_str = ', '.join(music_files)
                                        self.log_audit(f"8-MUSIC: (DETECTED) {real} [{files_str}]", "found")
                                    elif mode == "full":
                                        music_files = [trk for trk in os.listdir(full_m) if trk.lower().endswith(('.mp3', '.ogg'))]
                                        self.file_stats['music_tracks'] += len(music_files)
                                        shutil.copytree(full_m, os.path.join(table_dest, "music"), dirs_exist_ok=True)
                    if mode == "scan" and not m_found: self.log_audit("8-MUSIC: NOT FOUND", "missing")

                # 9. Patch Lookup (GitHub) - runs in all modes
                if self.enable_patch_lookup.get():
                    patch_result = self.find_github_patch(fname)
                    if patch_result['found']:
                        patch_name = patch_result['name']
                        if mode == "scan":
                            self.log_audit(f"9-PATCH: {patch_name} (DETECTED)", "found")
                        elif mode in ["full", "patch"]:
                            # Download and save patch with same name as table
                            patch_save_path = os.path.join(table_dest, f"{v_base}.vbs")
                            if self.download_patch(patch_result['download_url'], patch_save_path):
                                self.log_audit(f"9-PATCH: {patch_name} downloaded", "found")
                                self.file_stats['patches'] += 1
                            else:
                                self.log_audit(f"9-PATCH: Download failed", "missing")
                    else:
                        if mode == "scan":
                            self.log_audit("9-PATCH: NOT FOUND", "missing")
                        elif mode == "patch":
                            self.log_audit("9-PATCH: NOT FOUND", "missing")
                else:
                    if mode == "scan":
                        self.log_audit("9-PATCH: LOOKUP DISABLED", "missing")
                    elif mode == "patch":
                        self.log_audit("9-PATCH: LOOKUP IS DISABLED (Enable checkbox)", "missing")

                # Restore VBS Creator logic - FIXED
                if mode == "vbs":
                    vbs_path = os.path.join(table_dest, f"{v_base}.vbs")
                    # Write with proper Windows line endings (\r\n)
                    with open(vbs_path, "w", encoding='latin-1', newline='') as vf:
                        # Normalize to Unix line endings first, then let Python handle the conversion
                        lines = script.split('\n')
                        for i, line in enumerate(lines):
                            vf.write(line)
                            if i < len(lines) - 1:  # Don't add newline after last line if it's empty
                                vf.write('\r\n')
                    self.log_audit(f"VBS CREATED: {v_base}.vbs", "found")
                    self.file_stats['vbs_files'] += 1

            if mode == "scan": 
                self.log_separator("bottom")
                self.log_audit("")
        self.root.after(0, self.reset_ui)
        
        # Hide progress bar
        if mode != "scan":
            self.progress_frame.pack_forget()
        
        if mode != "scan" and target_root:
            self.log_audit("")
            # Display summary box
            self.log_separator("double")
            self.log_audit("                    📊 OPERATION SUMMARY", "yellow")
            self.log_separator("single")
            if self.file_stats['tables'] > 0:
                self.log_audit(f"  Tables Copied: {self.file_stats['tables']}", "found")
            if self.file_stats['roms'] > 0:
                self.log_audit(f"  ROMs Copied: {self.file_stats['roms']}", "found")
            if self.file_stats['backglass'] > 0:
                self.log_audit(f"  Backglasses: {self.file_stats['backglass']}", "found")
            if self.file_stats.get('ultradmd', 0) > 0:
                self.log_audit(f"  UltraDMD/FlexDMD Packs: {self.file_stats['ultradmd']}", "found")
            if self.file_stats['altsound'] > 0:
                self.log_audit(f"  AltSound Packs: {self.file_stats['altsound']}", "found")
            if self.file_stats['altcolor'] > 0:
                self.log_audit(f"  AltColor Packs: {self.file_stats['altcolor']}", "found")
            if self.file_stats['pup_packs'] > 0:
                self.log_audit(f"  PuP-Packs: {self.file_stats['pup_packs']}", "found")
            if self.file_stats['music_tracks'] > 0:
                self.log_audit(f"  Music Tracks: {self.file_stats['music_tracks']}", "found")
            if self.file_stats['patches'] > 0:
                self.log_audit(f"  Patches Downloaded: {self.file_stats['patches']}", "found")
            if self.file_stats['vbs_files'] > 0:
                self.log_audit(f"  VBS Files Created: {self.file_stats['vbs_files']}", "found")
            
            total_items = sum(self.file_stats.values())
            self.log_separator("single")
            self.log_audit(f"  TOTAL ITEMS PROCESSED: {total_items}", "yellow")
            self.log_separator("bottom")
            self.log_audit("")
            self.log_audit("--- TASK COMPLETED --- ENJOY!", "yellow")
            subprocess.run(["open", target_root])

    def handle_drop(self, event):
        self.clear_list(); files = [f.strip('{}') for f in self.root.tk.splitlist(event.data)]
        self.vpx_files = [f for f in files if f.lower().endswith(('.vpx', '.vbs'))]; self.audit_logic("scan")

    def start_thread(self, mode):
        self.btn_full.config(state="disabled")
        self.btn_vbs.config(state="disabled")
        self.btn_patch.config(state="disabled")
        threading.Thread(target=lambda: self.audit_logic(mode), daemon=True).start()

    def reset_ui(self):
        if self.vpx_files: 
            self.btn_full.config(state="normal")
            self.btn_vbs.config(state="normal")
            self.btn_patch.config(state="normal")

    def clear_list(self):
        self.vpx_files = []
        self.audit_list.config(state="normal")
        self.audit_list.delete('1.0', tk.END)
        self.audit_list.config(state="disabled")
        self.btn_full.config(state="disabled")
        self.btn_vbs.config(state="disabled")
        self.btn_patch.config(state="disabled")

    def save_settings(self):
        data = {"sources": {k: v.get() for k, v in self.sources.items()}, "target": self.target.get()}
        with open(self.config_file, "w") as f: json.dump(data, f)

if __name__ == "__main__":
    root = TkinterDnD.Tk(); app = VPXStandaloneMergingUtility(root); root.mainloop()
