import tkinter as tk
from tkinter import filedialog, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
import olefile, os, shutil, json, threading, subprocess, re, random, urllib.request, urllib.error
from PIL import Image, ImageTk
import io

VERSION = "1.0"

class VPXStandaloneMergingUtility:
    def __init__(self, root):
        self.root = root
        self.root.title(f"VPX UTILITY v{VERSION} - FULL RESTORATION")
        self.root.geometry("1200x920") 
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
        
        # Media DB - loaded in background at startup
        self.vpinmdb      = {}   # { id: {1k:{table:url,...}, wheel:url, ...} }
        self.vpsdb_lookup = {}   # { "rom_or_name_lower": id }
        self.media_db_ready = False
        
        self.load_settings()
        self.vpx_files = []
        self.setup_ui()
        
        # Load media DB in background so UI is not blocked
        threading.Thread(target=self.load_media_db, daemon=True).start()

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
        
        # Main container for audit and preview
        main_container = tk.Frame(self.root, bg="#1e1e1e")
        main_container.pack(fill="both", expand=True, padx=30, pady=10)
        
        # Audit frame on the left
        self.audit_frame = tk.Frame(main_container, bg="#000000", bd=2, relief="sunken")
        self.audit_frame.pack(side="left", fill="both", expand=True)
        self.audit_list = tk.Text(self.audit_frame, bg="#000000", fg="#ffffff", font=("Menlo", 11), state="disabled", padx=15, pady=10, width=70)
        self.audit_list.pack(fill="both", expand=True)
        self.audit_list.tag_configure("table_name", foreground="#00ccff", font=("Menlo", 12, "bold"))
        self.audit_list.tag_configure("found", foreground="#00ff00")
        self.audit_list.tag_configure("missing", foreground="#ffffff")
        self.audit_list.tag_configure("yellow", foreground="#ffff00", font=("Menlo", 11, "bold"))
        self.audit_list.tag_configure("white", foreground="#ffffff", font=("Menlo", 11, "bold"))
        self.audit_list.drop_target_register(DND_FILES); self.audit_list.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Preview panel on the right
        self.preview_frame = tk.Frame(main_container, bg="#000000", bd=2, relief="sunken", width=300)
        self.preview_frame.pack(side="right", fill="both", padx=(10, 0))
        self.preview_frame.pack_propagate(False)
        
        # Preview title
        tk.Label(self.preview_frame, text="TABLE PREVIEW", bg="#000000", fg="#00ccff", 
                font=("Arial", 12, "bold")).pack(pady=(10, 5))
        
        # Image display
        self.preview_canvas = tk.Canvas(self.preview_frame, bg="#1a1a1a", width=280, height=350, highlightthickness=0)
        self.preview_canvas.pack(pady=10, padx=10)
        
        # Table info labels
        self.preview_table_name = tk.Label(self.preview_frame, text="", bg="#000000", fg="#ffffff", 
                                           font=("Arial", 10, "bold"), wraplength=280, justify="center")
        self.preview_table_name.pack(pady=(5, 2))
        
        self.preview_rom_name = tk.Label(self.preview_frame, text="", bg="#000000", fg="#00ff00", 
                                         font=("Arial", 9), wraplength=280)
        self.preview_rom_name.pack(pady=2)
        
        self.preview_status = tk.Label(self.preview_frame, text="Drop a .vpx file to preview", 
                                      bg="#000000", fg="#888888", font=("Arial", 9, "italic"), wraplength=280)
        self.preview_status.pack(pady=(10, 5))


        # Store current image reference
        self.current_preview_image = None
        
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
    
    def load_media_db(self):
        """Download live VPS database + vpinmdb, build lookup fresh every run."""
        try:
            self.root.after(0, lambda: self.preview_status.config(
                text="\u23f3 Loading media database...", fg="#ffcc00"))

            # ── 1. Download vpsdatabaseV2.json (updated daily) ─────────────
            req = urllib.request.Request(
                "https://raw.githubusercontent.com/xantari/VPS.Database/main/vpsdatabaseV2.json",
                headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                vpsdata = json.loads(r.read().decode())
            entries = vpsdata.get("Entries", [])

            # ── 2. Build title -> vpinmdb_id lookup ────────────────────────
            AUTHOR_PREFIXES = [
                "jp's", "jps", "jp'", "vpw", "sg1", "flupper",
                "hauntfreaks", "davadruix", "jp\u2019s"
            ]

            def normalize(s):
                import re as _re
                s = s.lower()
                s = _re.sub(r"[\u2019\u2018`\']", "", s)
                s = _re.sub(r"[^a-z0-9\s]", " ", s)
                s = _re.sub(r"\s+", " ", s).strip()
                return s

            def word_sorted(s):
                """Canonical word-sorted key so word-order variants match."""
                words = sorted(w for w in s.split() if w not in ('the','a','an','of','and','in'))
                return " ".join(words)

            def make_keys(title):
                import re as _re
                keys = set()
                t = title.strip()
                keys.add(t.lower())
                norm_t = normalize(t)
                keys.add(norm_t)
                keys.add(word_sorted(norm_t))          # word-order invariant
                clean = _re.sub(r"\s*\(.*?\)", "", t).strip()
                norm_c = normalize(clean)
                keys.add(clean.lower())
                keys.add(norm_c)
                keys.add(word_sorted(norm_c))          # word-order invariant
                for prefix in AUTHOR_PREFIXES:
                    for pat in [prefix + "'s ", prefix + "s ", prefix + " ", prefix + "' "]:
                        if t.lower().startswith(pat.lower()):
                            rest = t[len(pat):].strip()
                            pl = prefix.rstrip("'s ").rstrip("'")
                            norm_r = normalize(rest)
                            keys.add(rest.lower())
                            keys.add(norm_r)
                            keys.add(word_sorted(norm_r))
                            keys.add(f"{rest.lower()} ({pl})")
                            keys.add(normalize(f"{rest} {pl}"))
                            break
                for suffix in [" le", " pro", " premium", " vr", " vault edition"]:
                    if norm_c.endswith(suffix):
                        keys.add(norm_c[:-len(suffix)].strip())
                return {k for k in keys if k and len(k) > 1}

            lookup = {}
            for e in entries:
                if e.get("MajorCategory") != "Table":
                    continue
                eid_raw = e.get("ExternalId", "")
                if "|" not in eid_raw:
                    continue
                vpinmdb_id = eid_raw.split("|")[0]
                title = e.get("Title", "").strip()
                if not title or not vpinmdb_id:
                    continue
                for key in make_keys(title):
                    if key not in lookup:
                        lookup[key] = vpinmdb_id

            self.vpsdb_lookup = lookup

            # ── 3. Supplement with live VPS spreadsheet (2,400+ entries) ──
            # This is the authoritative source - same one vpinfe uses
            vps_urls = [
                "https://virtualpinballspreadsheet.github.io/vps-db/db/vpsdb.json",
                "https://raw.githubusercontent.com/VirtualPinballSpreadsheet/vps-db/master/db/vpsdb.json",
            ]
            for vps_url in vps_urls:
                try:
                    req_vps = urllib.request.Request(
                        vps_url, headers={"User-Agent": "VPXMergeTool/1.0"})
                    with urllib.request.urlopen(req_vps, timeout=20) as r:
                        vpsdb_live = json.loads(r.read().decode())
                    added = 0
                    for entry in vpsdb_live:
                        eid = entry.get("id", "")
                        if not eid:
                            continue
                        name = entry.get("name", "").strip()
                        if name:
                            for key in make_keys(name):
                                if key not in lookup:
                                    lookup[key] = eid
                                    added += 1
                        for rom in entry.get("roms", []):
                            if isinstance(rom, dict):
                                for k in ("id", "name"):
                                    v = rom.get(k, "")
                                    if v and v.lower() not in lookup:
                                        lookup[v.lower()] = eid
                    self.vpsdb_lookup = lookup
                    break
                except Exception as ve:
                    continue


            # ── 3. Download vpinmdb.json (image index) ─────────────────────
            req2 = urllib.request.Request(
                "https://raw.githubusercontent.com/superhac/vpinmediadb/refs/heads/main/vpinmdb.json",
                headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req2, timeout=20) as r:
                self.vpinmdb = json.loads(r.read().decode())

            self.media_db_ready = True
            n = len(self.vpsdb_lookup)
            m = len(self.vpinmdb)
            self.root.after(0, lambda: self.preview_status.config(
                text=f"\u2713 Ready  {n:,} titles | {m:,} media", fg="#00ff00"))

        except Exception as e:
            err = str(e)[:45]
            # Fall back to bundled lookup if present
            lookup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vps_title_lookup.json")
            if os.path.exists(lookup_path):
                with open(lookup_path, "r", encoding="utf-8") as f:
                    combined = json.load(f)
                    self.vpsdb_lookup = combined.get("vpinmdb", combined) if isinstance(combined, dict) else {}
                self.media_db_ready = True
                self.root.after(0, lambda: self.preview_status.config(
                    text="\u26a0 Using cached DB (offline)", fg="#ffcc00"))
            else:
                self.root.after(0, lambda: self.preview_status.config(
                    text=f"\u26a0 DB failed: {err}", fg="#ff6600"))

    def update_preview(self, table_name, rom_name=None):
        """Match table by title -> vpinmdb id -> fetch playfield image."""
        self.preview_table_name.config(text=table_name[:42])
        self.preview_rom_name.config(text=f"ROM: {rom_name}" if rom_name else "")

        if not self.media_db_ready or not self.vpsdb_lookup or not self.vpinmdb:
            self.preview_status.config(text="\u23f3 Media DB loading...", fg="#ffcc00")
            self.show_placeholder_preview(table_name)
            return

        def normalize(s):
            s = s.lower()
            s = re.sub(r"['\u2019\u2018`]", "", s)
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def word_sorted(s):
            """Canonical key regardless of word order."""
            words = sorted(w for w in s.split() if w not in ("the","a","an","of","and","in"))
            return " ".join(words)


        # Build candidate keys from the filename
        candidates = []
        raw = table_name.strip()

        # 1 - raw and normalized
        norm_raw = normalize(raw)
        candidates.append(raw.lower())
        candidates.append(norm_raw)
        candidates.append(word_sorted(norm_raw))

        # 2 - strip parentheticals: "Ghostbusters Slimer (JP)" -> "Ghostbusters Slimer"
        clean = re.sub(r"\s*\(.*?\)", "", raw).strip()
        norm_clean = normalize(clean)
        candidates.append(clean.lower())
        candidates.append(norm_clean)
        candidates.append(word_sorted(norm_clean))

        # 3 - swap suffix author back to prefix: "Ghostbusters Slimer (JP)" -> "jp ghostbusters slimer"
        suffix_match = re.search(r"\(([^)]+)\)\s*$", raw)
        if suffix_match:
            author = suffix_match.group(1).strip()
            rest = raw[:suffix_match.start()].strip()
            norm_rest = normalize(rest)
            candidates.append(f"{author.lower()}s {rest.lower()}")
            candidates.append(f"{author.lower()} {rest.lower()}")
            candidates.append(normalize(f"{author} {rest}"))
            candidates.append(word_sorted(norm_rest))

        # 4 - strip version tags: VPW, LE, Pro, Premium etc.
        for suffix in [' le', ' pro', ' premium', ' vr', ' vpw', ' sg1', ' vpu']:
            n = normalize(clean)
            if n.endswith(suffix):
                candidates.append(n[:-len(suffix)].strip())

        # Deduplicate keeping order
        seen = set()
        unique = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                unique.append(c)

        media_id = None

        # Exact match
        for key in unique:
            if key in self.vpsdb_lookup:
                media_id = self.vpsdb_lookup[key]
                break

        # Substring fallback — only match if candidate covers at least 60% of lookup key
        # This prevents "fire" matching "harry potter and the goblet of fire"
        if not media_id:
            best_id = None
            best_ratio = 0.0
            for key in unique:
                if len(key) < 5:
                    continue
                for lk, lid in self.vpsdb_lookup.items():
                    if key in lk:
                        ratio = len(key) / len(lk)
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_id = lid
                    elif lk in key:
                        ratio = len(lk) / len(key)
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_id = lid
            # Only accept if the match covers at least 60% of the string
            if best_id and best_ratio >= 0.60:
                media_id = best_id
            elif best_id:
                pass  # match found but below threshold

        if not media_id:
            self.preview_status.config(text="Not found in database", fg="#888888")
            self.show_placeholder_preview(table_name)
            return

        if media_id not in self.vpinmdb:
            self.preview_status.config(text="No media for this table", fg="#888888")
            self.show_placeholder_preview(table_name)
            return

        entry = self.vpinmdb[media_id]
        img_url = (entry.get("1k", {}).get("table")
                   or entry.get("1k", {}).get("fss")
                   or entry.get("wheel"))

        if not img_url:
            self.show_placeholder_preview(table_name)
            return

        self.preview_status.config(text="\u23f3 Loading image...", fg="#ffcc00")
        threading.Thread(target=self._fetch_and_show_image,
                         args=(img_url, table_name), daemon=True).start()

    def _fetch_and_show_image(self, url, table_name):
        """Background thread: download playfield + wheel, composite, push to UI."""
        try:
            # ── Fetch playfield image ───────────────────────────────────────
            req = urllib.request.Request(url, headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()

            playfield = Image.open(io.BytesIO(data)).convert("RGBA")
            playfield = playfield.rotate(-90, expand=True)

            # Scale to fit canvas (280 wide x 370 tall)
            playfield.thumbnail((280, 370), Image.Resampling.LANCZOS)
            canvas_w, canvas_h = 280, 370
            pf_w, pf_h = playfield.size

            # ── Try to fetch wheel image ────────────────────────────────────
            wheel_img = None
            try:
                # Wheel URL is sibling of table URL: replace "1k/table.png" -> "wheel.png"
                wheel_url = re.sub(r"1k/.*\.png$", "wheel.png", url)
                if wheel_url != url:
                    req2 = urllib.request.Request(wheel_url, headers={"User-Agent": "VPXMergeTool/1.0"})
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        wdata = r2.read()
                    wheel_img = Image.open(io.BytesIO(wdata)).convert("RGBA")
                    # Size wheel to ~28% of canvas width
                    wheel_size = int(canvas_w * 0.342)
                    wheel_img = wheel_img.resize((wheel_size, wheel_size), Image.Resampling.LANCZOS)
            except Exception as we:
                wheel_img = None

            # ── Composite onto blank canvas ─────────────────────────────────
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (26, 26, 26, 255))

            # Centre playfield
            pf_x = (canvas_w - pf_w) // 2
            pf_y = (canvas_h - pf_h) // 2
            canvas.paste(playfield, (pf_x, pf_y), playfield)

            # Overlay wheel bottom-centre with slight shadow effect
            if wheel_img:
                ww, wh = wheel_img.size
                wx = (canvas_w - ww) // 2
                wy = canvas_h - wh - 24  # moved up to avoid cutoff

                # Draw a subtle dark circle behind the wheel
                shadow = Image.new("RGBA", (ww + 8, wh + 8), (0, 0, 0, 0))
                from PIL import ImageDraw
                ImageDraw.Draw(shadow).ellipse([0, 0, ww + 7, wh + 7], fill=(0, 0, 0, 120))
                canvas.paste(shadow, (wx - 4, wy - 4), shadow)

                canvas.paste(wheel_img, (wx, wy), wheel_img)

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(canvas)

            def show(p=photo):
                self.current_preview_image = p
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(canvas_w // 2, canvas_h // 2,
                                                 anchor="center", image=p)
                lbl = "✓ Preview + Wheel" if wheel_img else "✓ Preview loaded"
                self.preview_status.config(text=lbl, fg="#00ff00")

            self.root.after(0, show)

        except Exception as e:
            err = str(e)[:40]
            self.root.after(0, lambda: self.show_placeholder_preview(table_name))
            self.root.after(0, lambda msg=err: self.preview_status.config(
                text=f"Image error: {msg}", fg="#ff6600"))

    def show_placeholder_preview(self, table_name):
        """Styled placeholder when no image is available."""
        self.preview_canvas.delete("all")
        w, h = 280, 370
        self.preview_canvas.create_rectangle(5, 5, w-5, h-5,
                                             fill="#1a1a1a", outline="#00ccff", width=2)
        # Pinball icon
        self.preview_canvas.create_oval(90, 110, 190, 210,
                                        fill="#2a2a2a", outline="#00ccff", width=2)
        self.preview_canvas.create_oval(115, 135, 165, 185,
                                        fill="#00ccff", outline="#ffffff", width=1)
        self.preview_canvas.create_text(w//2, 240,
                                        text="No Preview\nAvailable",
                                        fill="#666666", font=("Arial", 11, "bold"),
                                        justify="center")
        short = (table_name[:32] + "…") if len(table_name) > 32 else table_name
        self.preview_canvas.create_text(w//2, 300, text=short,
                                        fill="#00ccff", font=("Arial", 8),
                                        justify="center", width=260)
        self.current_preview_image = None

    def browse_path(self, key, mode):
        path = filedialog.askdirectory()
        if path:
            if mode == "source": self.sources[key].set(path)
            else: self.target.set(path)
            self.save_settings()

    def extract_script(self, path):
        try:
            if path.lower().endswith('.vbs'):
                with open(path, 'rb') as f: return f.read()
            if olefile.isOleFile(path):
                with olefile.OleFileIO(path) as ole:
                    for s in ole.listdir():
                        if any(x in str(s).lower() for x in ["gamestru", "mac", "version"]): continue
                        with ole.openstream(s) as stream:
                            d = stream.read()
                            # Must contain "Option Explicit" or "Option Base" - the definitive script marker
                            # This prevents matching binary streams that happen to contain ' bytes
                            idx = d.find(b'Option ')
                            if idx == -1:
                                continue
                            # Verify this is actually text: 95%+ printable chars in first 200 bytes after marker
                            sample = d[idx:idx+200]
                            printable = sum(1 for b in sample if b >= 0x20 or b in (0x09, 0x0a, 0x0d))
                            if len(sample) > 0 and printable / len(sample) < 0.95:
                                continue  # binary stream, skip it
                            # Scan backwards from idx to include comment header before Option
                            start = idx
                            for back in range(idx - 1, max(idx - 100000, -1), -1):
                                b = d[back]
                                # Stop at any non-text byte (not tab, LF, CR, space, or printable ASCII/latin-1)
                                if b < 0x09 or (0x0e <= b <= 0x1f):
                                    start = back + 1
                                    # Walk forward to start of next line
                                    while start < idx and d[start] in (0x0a, 0x0d):
                                        start += 1
                                    break
                            else:
                                start = 0
                            raw = d[start:]
                            # Strip OLE stream padding and ENDB footer from the end
                            endb = raw.rfind(b'ENDB')
                            if endb != -1:
                                raw = raw[:endb].rstrip(b'\x00\x04')
                            else:
                                raw = raw.rstrip(b'\x00')
                            return raw
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
            fname = os.path.basename(f); v_base = os.path.splitext(fname)[0]
            script_raw = self.extract_script(f)  # raw bytes - used for writing carbon copy
            # Decode to string for all regex/text operations
            script = script_raw.decode('latin-1', errors='ignore') if isinstance(script_raw, bytes) else (script_raw or '')
            table_dest = os.path.join(target_root, v_base)
            
            # Update progress
            if mode != "scan":
                progress = ((idx + 1) / total_files) * 100
                self.progress_bar['value'] = progress
                self.progress_label.config(text=f"Processing {idx + 1}/{total_files}: {v_base}")
                self.root.update_idletasks()
            
            # Setup Folder Structure
            if mode != "scan": os.makedirs(table_dest, exist_ok=True)
            
            # Extract ROM name for preview
            rom_for_preview = None
            if script:
                rom_m = re.search(r'(?:Const\s+)?c?(?:Game|Rom)Name\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                rom_for_preview = rom_m.group(1) if rom_m else None
            
            # Update preview with table info
            self.root.after(0, lambda tn=v_base, rn=rom_for_preview: self.update_preview(tn, rn))
            
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

            # 2. Backglass — purely file-based, no script needed
            if mode != "patch":
                # .directb2s always has exact same name as .vpx
                b2s_src = None
                b2s_fname = None
                file_dir = os.path.dirname(f)
                b2s_base = v_base

                # For .vbs drops: find the .vpx in same folder to get real base name
                if f.lower().endswith('.vbs'):
                    try:
                        for entry in os.scandir(file_dir):
                            if entry.name.lower().endswith('.vpx'):
                                b2s_base = os.path.splitext(entry.name)[0]
                                break
                    except Exception:
                        pass

                # Look in same folder as the file, then t_dir as fallback
                for search_dir in [file_dir, t_dir]:
                    if not search_dir:
                        continue
                    candidate = os.path.join(search_dir, f"{b2s_base}.directb2s")
                    if os.path.exists(candidate):
                        b2s_src, b2s_fname = candidate, f"{b2s_base}.directb2s"
                        break
                if b2s_src:
                    if mode == "scan": self.log_audit(f"2-BACKGLASS: {b2s_fname} (DETECTED)", "found")
                    elif mode == "full":
                        shutil.copy2(b2s_src, os.path.join(table_dest, b2s_fname))
                        self.file_stats['backglass'] += 1
                else:
                    if mode == "scan": self.log_audit("2-BACKGLASS: NOT FOUND", "missing")

            if script and mode != "patch":
                # 1. ROM Logic
                rom_m = re.search(r'(?:Const\s+)?c?(?:Game|Rom)Name\s*=\s*["\']([^"\' ]+)["\']', script, re.IGNORECASE)
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
                        if mode == "scan": self.log_audit(f"1-ROM: {rom} NOT FOUND", "missing")

                # 3. UltraDMD / FlexDMD Detection
                uses_ultradmd = (re.search(r'UltraDMDTimer\.Enabled\s*=\s*1', script, re.IGNORECASE) or
                                 re.search(r'UseUltraDMD\s*=\s*1',              script, re.IGNORECASE))
                uses_flexdmd  = (re.search(r'UseFlexDMD\s*=\s*1',   script, re.IGNORECASE) or
                                 re.search(r'Dim\s+FlexDMD\b',       script, re.IGNORECASE) or
                                 re.search(r'Sub\s+FlexDMD_init\b',  script, re.IGNORECASE) or
                                 re.search(r'\.ProjectFolder\s*=',   script, re.IGNORECASE))

                if uses_ultradmd or uses_flexdmd:
                    dmd_found = False
                    dmd_type  = "UltraDMD" if uses_ultradmd else "FlexDMD"

                    # Extract Const TableName = "Name of the Table" from VBS
                    tname_match = re.search(r'(?:Const\s+)?TableName\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                    vbs_table_name = tname_match.group(1).strip() if tname_match else None

                    # For FlexDMD: extract folder name from ProjectFolder line
                    # Handles: .ProjectFolder = "./FolderName/"
                    #      or: .ProjectFolder = "./" & "FolderName" & "/"
                    flex_folder = None
                    if uses_flexdmd:
                        # Pattern 1: .ProjectFolder = "./FolderName/"
                        pf_match = re.search(r'ProjectFolder\s*=\s*"\./([^"/]+)/"', script, re.IGNORECASE)
                        if pf_match:
                            flex_folder = pf_match.group(1).strip()
                        else:
                            # Pattern 2: .ProjectFolder = "./" & "FolderName" & "/"
                            pf_match = re.search(r'ProjectFolder\s*=.*?"\./?"\s*&\s*"([^"]+)"', script, re.IGNORECASE)
                            if pf_match:
                                flex_folder = pf_match.group(1).strip()

                    # Build search names in priority order
                    search_names = []
                    if flex_folder:
                        search_names.append(flex_folder)   # exact folder from ProjectFolder
                    if vbs_table_name:
                        search_names.append(vbs_table_name)
                    search_names.append(v_base)
                    if rom:
                        search_names.append(rom)

                    # DMD folder lives next to the .vpx - search file_dir first, then t_dir as fallback
                    dmd_search_roots = list(dict.fromkeys([os.path.dirname(f), t_dir]))
                    # Try all known extensions INCLUDING bare name (e.g. MFDOOMDMD has no extension)
                    dmd_extensions = ['.FlexDMD', '.UltraDMD', '.DMD', 'DMD', '']

                    for search_name in search_names:
                        if dmd_found:
                            break
                        for ext in dmd_extensions:
                            if dmd_found:
                                break
                            dmd_folder = f"{search_name}{ext}"
                            for dmd_search_root in dmd_search_roots:
                                dmd_src = os.path.join(dmd_search_root, dmd_folder)
                                if os.path.exists(dmd_src) and os.path.isdir(dmd_src):
                                    dmd_found = True
                                    if mode == "scan":
                                        self.log_audit(f"3-ULTRADMD/FLEXDMD: {dmd_folder} (DETECTED)", "found")
                                    elif mode == "full":
                                        shutil.copytree(dmd_src, os.path.join(table_dest, dmd_folder), dirs_exist_ok=True)
                                        self.file_stats['ultradmd'] = self.file_stats.get('ultradmd', 0) + 1
                                    break

                    if not dmd_found:
                        tried = [f"{n}{e}" for n in search_names for e in dmd_extensions]
                        self.log_audit("3-ULTRADMD/FLEXDMD: NOT FOUND", "missing")
                        if flex_folder:
                            pass
                        if vbs_table_name:
                            pass

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

                # VBS Creator
                if mode == "vbs":
                    vbs_path = os.path.join(table_dest, f"{v_base}.vbs")
                    raw_out = script_raw if isinstance(script_raw, bytes) else script.encode('latin-1', errors='replace')
                    raw_out = raw_out.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
                    with open(vbs_path, "wb") as vf:
                        vf.write(raw_out)
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
            self.btn_patch.config(state="normal")
            # VBS export only makes sense for .vpx files (extracts embedded script)
            # For .vbs source files the file IS already the script
            all_vbs = all(f.lower().endswith('.vbs') for f in self.vpx_files)
            self.btn_vbs.config(state="disabled" if all_vbs else "normal")

    def clear_list(self):
        self.vpx_files = []
        self.audit_list.config(state="normal")
        self.audit_list.delete('1.0', tk.END)
        self.audit_list.config(state="disabled")
        self.btn_full.config(state="disabled")
        self.btn_vbs.config(state="disabled")
        self.btn_patch.config(state="disabled")
        
        # Reset preview
        self.preview_canvas.delete("all")
        self.preview_table_name.config(text="")
        self.preview_rom_name.config(text="")
        self.preview_status.config(text="Drop a .vpx file to preview", fg="#888888")
        self.current_preview_image = None

    def save_settings(self):
        data = {"sources": {k: v.get() for k, v in self.sources.items()}, "target": self.target.get()}
        with open(self.config_file, "w") as f: json.dump(data, f)

if __name__ == "__main__":
    root = TkinterDnD.Tk(); app = VPXStandaloneMergingUtility(root); root.mainloop()
