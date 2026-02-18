import tkinter as tk
from tkinter import filedialog, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
import olefile, os, shutil, json, threading, subprocess, re, random, urllib.request, urllib.error
from PIL import Image, ImageTk
import io

VERSION = "1.0"

# ── Media fuzzy matching helpers ──────────────────────────────────────────────
_MEDIA_NOISE = {
    'limited','edition','le','pro','premium','vr','vpw','mod','sg1','vpu',
    'the','a','an','and','of','in','remaster','vpx','remake','ultimate',
    'deluxe','special','anniversary','collector','classic','night','jp','fizx'
}

def _mnorm(s):
    """Normalize a name for fuzzy media matching."""
    s = s.lower()
    s = re.sub(r"_s\b", "s", s)               # Bugs_Bunny_s → Bugs Bunnys
    s = re.sub(r"['\u2019\u2018`]", "", s)     # strip apostrophes
    s = re.sub(r"[^a-z0-9\s]", " ", s)        # non-alphanum → space
    return re.sub(r"\s+", " ", s).strip()

def _mstrip(s):
    """Strip manufacturer, year, version, author noise."""
    s = re.sub(r'\s*\([^)]*\d{4}[^)]*\)', '', s)          # (Stern 2013)
    s = re.sub(r'\s*\([^)]*\)', '', s)                      # any remaining ()
    s = re.sub(r'\s+v\d+[\d.]*\b.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+\d+\.\d+[\d.]*\b.*$', '', s)
    s = re.sub(r'\s+(VPW|MOD|VR|LE|SE|CE|PRO|PREM|JP|FizX)\b.*$', '', s, flags=re.IGNORECASE)
    return s.strip()

def _mkeywords(s):
    return set(_mnorm(_mstrip(s)).split()) - _MEDIA_NOISE

def _mfuzzy(a, b):
    """Return keyword overlap score 0.0–1.0 between two table names."""
    ka, kb = _mkeywords(a), _mkeywords(b)
    if not ka or not kb: return 0.0
    return len(ka & kb) / max(len(ka), len(kb))

class VPXStandaloneMergingUtility:
    def __init__(self, root):
        self.root = root
        self.root.title(f"VPX UTILITY v{VERSION} - FULL RESTORATION")
        self.root.geometry("1400x1000")
        self.root.minsize(1200, 900)
        self.root.resizable(True, True) 
        self.root.configure(bg="#1e1e1e") 
        
        self.config_file = os.path.join(os.path.expanduser("~"), ".vpx_utility_config.json")
        self.sources = {"tables": tk.StringVar(), "vpinmame": tk.StringVar(), "pupvideos": tk.StringVar(), "music": tk.StringVar()}
        self.target = tk.StringVar()
        self.enable_patch_lookup = tk.BooleanVar(value=True)
        self.include_media = tk.BooleanVar(value=False)  # Default: checked
        
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

    def _make_section(self, parent, label, accent):
        """Creates a modern section with a slim colored top-border and label."""
        outer = tk.Frame(parent, bg=accent, pady=1)
        outer.pack(fill="x", padx=28, pady=(8, 0))
        inner = tk.Frame(outer, bg="#1a1e2e", pady=6, padx=12)
        inner.pack(fill="x")
        tk.Label(inner, text=label, bg="#1a1e2e", fg=accent,
                 font=("Courier", 14, "bold", "underline")).pack(anchor="w")
        return inner

    def _make_btn(self, parent, text, color, cmd, dim_color, height=2):
        """Rounded-feel button with hover."""
        btn = tk.Button(parent, text=text, bg=color, fg="#0a0d1a",
                        font=("Courier", 16, "bold"), relief="flat",
                        bd=0, height=height, cursor="hand2", command=cmd,
                        activebackground=dim_color, activeforeground="#0a0d1a",
                        disabledforeground="#555566")
        btn.bind("<Enter>", lambda e, b=btn, c=dim_color: b.config(bg=c) if b["state"] == "normal" else None)
        btn.bind("<Leave>", lambda e, b=btn, c=color:     b.config(bg=c) if b["state"] == "normal" else None)
        return btn

    def setup_ui(self):
        BG      = "#0a0d1a"   # deep navy black
        PANEL   = "#111526"   # slightly lighter panel
        BORDER  = "#1e2440"   # subtle border
        ACCENT1 = "#00e5ff"   # cyan   — sources
        ACCENT2 = "#ffd600"   # amber  — target
        GREEN   = "#00e676"   # green  — found / main action
        CYAN    = "#40c4ff"   # blue   — vbs
        ORANGE  = "#ff9100"   # orange — patch
        RED     = "#ff1744"   # red    — clear
        MUTED   = "#4a5080"   # muted text

        self.root.configure(bg=BG)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(18, 4))

        # Canvas title with white outline + cyan fill
        title_canvas = tk.Canvas(hdr, bg=BG, highlightthickness=0, height=62)
        title_canvas.pack(side="left", fill="x", expand=True)

        def draw_title(event=None):
            title_canvas.delete("all")
            cw = title_canvas.winfo_width() or 900
            cx = cw // 2
            txt = "VPX  STANDALONE  MERGING  TOOL"
            fnt = ("Courier", 42, "bold")
            # White outline — draw 8 times offset in every direction
            for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2),(-2,0),(2,0),(0,-2),(0,2)]:
                title_canvas.create_text(cx+dx, 31+dy, text=txt, font=fnt,
                                         fill="#ffffff", anchor="center")
            # Cyan fill on top
            title_canvas.create_text(cx, 31, text=txt, font=fnt,
                                     fill=ACCENT1, anchor="center")

        title_canvas.bind("<Configure>", draw_title)
        title_canvas.after(50, draw_title)

        tk.Label(hdr, text=f"v{VERSION}", font=("Courier", 10),
                 fg=MUTED, bg=BG).pack(side="right", anchor="n", pady=(4, 0))

        # thin separator line under header
        tk.Frame(self.root, bg=ACCENT1, height=1).pack(fill="x", padx=28, pady=(0, 6))

        # ── Sources ───────────────────────────────────────────────────────────
        src_sec = self._make_section(self.root, "◈  SOURCE FOLDERS", ACCENT1)
        LABELS = {"tables": "TABLES", "vpinmame": "VPINMAME", "pupvideos": "PUP VIDEOS", "music": "MUSIC"}
        for key in ["tables", "vpinmame", "pupvideos", "music"]:
            row = tk.Frame(src_sec, bg="#1a1e2e")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=LABELS[key], bg="#1a1e2e", fg="#ffffff",
                     font=("Courier", 11, "bold"), width=11, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=self.sources[key],
                     bg=BORDER, fg="#ffffff", font=("Courier", 10, "bold"),
                     relief="flat", bd=0,
                     insertbackground=ACCENT1).pack(side="left", fill="x", expand=True, padx=(4, 6), ipady=5)
            tk.Button(row, text="›", bg="#1e2856", fg=ACCENT1,
                      font=("Courier", 14, "bold"), relief="flat", bd=0,
                      width=3, cursor="hand2",
                      command=lambda k=key: self.browse_path(k, "source"),
                      activebackground="#2a3870", activeforeground=ACCENT1).pack(side="right")

        # ── Target ────────────────────────────────────────────────────────────
        tgt_sec = self._make_section(self.root, "◈  EXPORT TARGET", ACCENT2)
        tgt_row = tk.Frame(tgt_sec, bg="#1a1e2e")
        tgt_row.pack(fill="x", pady=2)
        tk.Entry(tgt_row, textvariable=self.target,
                 bg=BORDER, fg="#ffffff", font=("Courier", 10, "bold"),
                 relief="flat", bd=0,
                 insertbackground=ACCENT2).pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=5)
        tk.Button(tgt_row, text="›", bg="#2a2000", fg=ACCENT2,
                  font=("Courier", 13, "bold"), relief="flat", bd=0,
                  width=3, cursor="hand2",
                  command=lambda: self.browse_path(None, "target"),
                  activebackground="#3a3000", activeforeground=ACCENT2).pack(side="right")

        # ── Options row ───────────────────────────────────────────────────────
        opt_row = tk.Frame(self.root, bg=BG)
        opt_row.pack(fill="x", padx=28, pady=(10, 2))
        tk.Checkbutton(opt_row, text=" Enable Patch Lookup  (GitHub)",
                       variable=self.enable_patch_lookup,
                       bg=BG, fg=GREEN, selectcolor=BORDER,
                       font=("Courier", 11, "bold"), activebackground=BG,
                       activeforeground=GREEN, cursor="hand2").pack(side="left")
        
        tk.Checkbutton(opt_row, text=" Include Media Files",
                       variable=self.include_media,
                       bg=BG, fg=CYAN, selectcolor=BORDER,
                       font=("Courier", 11, "bold"), activebackground=BG,
                       activeforeground=CYAN, cursor="hand2").pack(side="left", padx=(20, 0))

        # ── Progress Bar ──────────────────────────────────────────────────────
        self.progress_frame = tk.Frame(self.root, bg=BG, height=1)
        self.progress_frame.pack(fill="x", padx=28, pady=0)
        self.progress_frame.pack_propagate(False)  # keep fixed height — prevents layout shift
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Neo.Horizontal.TProgressbar",
                        troughcolor=BORDER, background=ACCENT1,
                        borderwidth=0, thickness=6)
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate",
                                            style="Neo.Horizontal.TProgressbar")
        self.progress_label = tk.Label(self.progress_frame, text="", bg=BG, fg="#ffffff",
                                       font=("Courier", 10, "bold"))
        # bar and label hidden initially — frame stays packed to hold layout space

        # ── Main area (audit log + preview) ──────────────────────────────────
        main_container = tk.Frame(self.root, bg=BG, height=500)
        main_container.pack(fill="both", expand=True, padx=28, pady=(8, 4))
        main_container.pack_propagate(False)

        # Audit log
        audit_outer = tk.Frame(main_container, bg=BORDER, pady=1, padx=1)
        audit_outer.pack(side="left", fill="both", expand=True)
        audit_inner = tk.Frame(audit_outer, bg=PANEL)
        audit_inner.pack(fill="both", expand=True)

        # header bar for audit
        audit_hdr = tk.Frame(audit_inner, bg="#161a2e", pady=6)
        audit_hdr.pack(fill="x")
        # spacer left
        tk.Label(audit_hdr, text="", bg="#161a2e", width=8).pack(side="left")
        tk.Label(audit_hdr, text="AUDIT LOG",
                 bg="#161a2e", fg="#ffffff", font=("Courier", 14, "bold")).pack(side="left", expand=True)
        tk.Button(audit_hdr, text="✕  CLEAR", command=self.clear_list,
                  bg="#2a0010", fg=RED, font=("Courier", 11, "bold"),
                  relief="flat", bd=0, padx=12, pady=2, cursor="hand2",
                  activebackground="#3a0018", activeforeground=RED).pack(side="right", padx=6)

        self.audit_list = tk.Text(audit_inner, bg=PANEL, fg="#c0cce8",
                                  font=("Menlo", 13), state="disabled",
                                  padx=14, pady=8, relief="flat", bd=0,
                                  width=68, insertbackground=ACCENT1)
        scrollbar = tk.Scrollbar(audit_inner, command=self.audit_list.yview,
                                 bg=BORDER, troughcolor=PANEL,
                                 activebackground=MUTED, relief="flat", bd=0, width=8)
        self.audit_list.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.audit_list.pack(fill="both", expand=True)

        self.audit_list.tag_configure("table_name", foreground=ACCENT1, font=("Menlo", 15, "bold"))
        self.audit_list.tag_configure("found",   foreground=GREEN,   font=("Menlo", 13))
        self.audit_list.tag_configure("missing", foreground="#ffffff", font=("Menlo", 13))
        self.audit_list.tag_configure("yellow",  foreground=ACCENT2, font=("Menlo", 13, "bold"))
        self.audit_list.tag_configure("white",   foreground="#7080a0", font=("Menlo", 13))
        self.audit_list.drop_target_register(DND_FILES)
        self.audit_list.dnd_bind("<<Drop>>", self.handle_drop)

        # Centered drop hint overlay — shown when log is empty
        self.drop_hint = tk.Label(audit_inner,
                                  text="DROP  .VPX  TABLE  HERE",
                                  bg=PANEL, fg="#ffd600",
                                  font=("Courier", 22, "bold"),
                                  cursor="hand2",
                                  highlightthickness=2,
                                  highlightbackground="#ffffff",
                                  padx=16, pady=10)
        self.drop_hint.place(relx=0.5, rely=0.5, anchor="center")
        self.drop_hint.drop_target_register(DND_FILES)
        self.drop_hint.dnd_bind("<<Drop>>", self.handle_drop)

        # Preview panel
        prev_outer = tk.Frame(main_container, bg=BORDER, pady=1, padx=1, width=462)
        prev_outer.pack(side="right", fill="y", padx=(10, 0))
        prev_outer.pack_propagate(False)
        self.preview_frame = tk.Frame(prev_outer, bg=PANEL, width=460)
        self.preview_frame.pack(fill="both", expand=True)
        self.preview_frame.pack_propagate(False)

        # ── Header row: title + back button ──────────────────────────────────
        prev_hdr = tk.Frame(self.preview_frame, bg=PANEL)
        prev_hdr.pack(fill="x", pady=(10, 4))

        self.preview_title = tk.Label(prev_hdr, text="TABLE PREVIEW",
                 bg=PANEL, fg="#ffffff", font=("Courier", 16, "bold"),
                 wraplength=420, justify="center")
        self.preview_title.pack(side="left", expand=True, fill="x", padx=(10, 0))

        self.btn_back_preview = tk.Button(prev_hdr, text="◀ ALL",
                 bg=PANEL, fg="#00e5ff", font=("Courier", 9, "bold"),
                 relief="flat", bd=0, cursor="hand2",
                 command=self._preview_back,
                 activebackground="#1a1e2e", activeforeground="#ffffff")
        self.btn_back_preview.pack(side="right", padx=(0, 8))
        self.btn_back_preview.pack_forget()  # hidden until multi-file grid is active

        tk.Frame(self.preview_frame, bg=BORDER, height=1).pack(fill="x", padx=10)

        # ── Single big view (DEFAULT) ─────────────────────────────────────────
        self.preview_single_frame = tk.Frame(self.preview_frame, bg=PANEL)
        self.preview_single_frame.pack(fill="both", expand=True)

        self.preview_canvas = tk.Canvas(self.preview_single_frame, bg="#0d101e",
                                        width=440, height=490, highlightthickness=0)
        self.preview_canvas.pack(pady=(8, 4), padx=10, fill="both", expand=True)

        self.preview_table_name = tk.Label(self.preview_single_frame, text="",
                                           bg=PANEL, fg="#ffffff",
                                           font=("Courier", 11, "bold"),
                                           wraplength=430, justify="center")
        self.preview_table_name.pack(pady=(2, 1))

        self.preview_rom_name = tk.Label(self.preview_single_frame, text="",
                                         bg=PANEL, fg=GREEN,
                                         font=("Courier", 8), wraplength=430)
        self.preview_rom_name.pack(pady=1)

        # ── Grid view (up to 6 thumbnails 2×3) — shown for multiple files ────
        self.preview_grid_frame = tk.Frame(self.preview_frame, bg=PANEL)
        # not packed yet — appears when 2+ files are dropped
        self.thumb_cells  = []
        self.thumb_images = []

        # ── Status bar ────────────────────────────────────────────────────────
        self.preview_status = tk.Label(self.preview_frame,
                                       text="Drop a .vpx file to preview",
                                       bg=PANEL, fg="#a0b4d0",
                                       font=("Courier", 9, "italic"), wraplength=440)
        self.preview_status.pack(side="bottom", pady=(4, 6))

        # State
        self.current_preview_image = None
        self.thumb_images  = []
        self._preview_data = []   # [{table_name, rom_name, image, thumb, loaded}]
        self._zoom_index   = None # slot being shown in single view from grid

        # ── Action buttons ────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill="x", padx=28, pady=(4, 6))

        self.btn_full = self._make_btn(btn_frame, "⚡  MAKE THE MAGIC HAPPEN",
                                       GREEN, lambda: self.start_thread("full"), "#33ff99")
        self.btn_full.config(state="disabled")
        self.btn_full.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_vbs = self._make_btn(btn_frame, "◎  CREATE CLEAN .VBS",
                                      CYAN, lambda: self.start_thread("vbs"), "#80d8ff")
        self.btn_vbs.config(state="disabled")
        self.btn_vbs.pack(side="left", fill="x", expand=True, padx=4)

        self.btn_fix = self._make_btn(btn_frame, "🔧  FIX SCRIPT",
                                      "#ff3366", lambda: self.start_thread("fix"), "#ff6699")
        self.btn_fix.config(state="disabled")
        self.btn_fix.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # ── Bottom bar ────────────────────────────────────────────────────────
        bot = tk.Frame(self.root, bg=BG)
        bot.pack(fill="x", padx=28, pady=(0, 10))

        # Load and resize logo to fit beside small text (~28px tall)
        try:
            _logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mf_logo.png")
            _logo_img = Image.open(_logo_path).convert("RGBA")
            _logo_img = _logo_img.resize((28, 28), Image.Resampling.LANCZOS)
            self._logo_photo = ImageTk.PhotoImage(_logo_img)
            tk.Label(bot, image=self._logo_photo, bg=BG).pack(side="right", padx=(4, 0))
        except Exception:
            self._logo_photo = None

        tk.Label(bot, text="Brought to you by Major Frenchy .",
                 font=("Courier", 11, "bold"), fg="#ffffff", bg=BG).pack(side="right")

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

            # ── 4. Load user custom mappings (optional) ──────────────────
            custom_map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_mappings.txt")
            if os.path.exists(custom_map_path):
                try:
                    with open(custom_map_path, 'r', encoding='utf-8') as cf:
                        for line in cf:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            if '=' in line:
                                table_name, vpinmdb_id = line.split('=', 1)
                                table_name = table_name.strip()
                                vpinmdb_id = vpinmdb_id.strip()
                                if table_name and vpinmdb_id:
                                    # Add both raw and normalized versions
                                    self.vpsdb_lookup[table_name.lower()] = vpinmdb_id
                                    norm = re.sub(r"[^\w\s]", " ", table_name.lower())
                                    norm = re.sub(r"\s+", " ", norm).strip()
                                    self.vpsdb_lookup[norm] = vpinmdb_id
                except Exception:
                    pass  # Silently ignore custom mapping errors
            
            # ── 5. Load local CSV database (optional) ────────────────────
            csv_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinballxdatabase.csv")
            if os.path.exists(csv_db_path):
                try:
                    import csv
                    with open(csv_db_path, 'r', encoding='utf-8-sig') as csvf:
                        reader = csv.DictReader(csvf)
                        for row in reader:
                            table_full = row.get('Table Name (Manufacturer Year)', '').strip()
                            if not table_full:
                                continue
                            
                            # Extract base name (before author/version info)
                            # Format: "Table Name (Manufacturer Year) Author Version"
                            # We want just the "Table Name (Manufacturer Year)" part
                            parts = table_full.split()
                            # Find where manufacturer/year ends
                            base_end = -1
                            for i, part in enumerate(parts):
                                if part.endswith(')'):
                                    base_end = i
                                    break
                            
                            if base_end > 0:
                                base_name = ' '.join(parts[:base_end+1])
                            else:
                                base_name = table_full
                            
                            # Also try without manufacturer/year
                            clean_name = re.sub(r'\s*\([^)]+\)\s*', '', base_name).strip()
                            
                            # Use the IPDB number as the ID if available
                            ipdb = row.get('IPDB Number', '').strip()
                            if ipdb and ipdb != '-':
                                vid = f"ipdb_{ipdb}"
                            else:
                                # Use normalized name as fallback ID
                                vid = normalize(clean_name).replace(' ', '_')
                            
                            # Add various name formats to lookup
                            for name_var in [base_name, clean_name, table_full]:
                                if name_var:
                                    norm = normalize(name_var)
                                    if norm and norm not in self.vpsdb_lookup:
                                        self.vpsdb_lookup[norm] = vid
                                        self.vpsdb_lookup[name_var.lower()] = vid
                except Exception:
                    pass  # Silently ignore CSV errors
            
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
        """Register a table for preview. 1 file = big single view. 2-6 = grid."""
        # Find or assign slot
        for i, d in enumerate(self._preview_data):
            if d["table_name"] == table_name:
                slot = i; break
        else:
            if len(self._preview_data) >= 6:
                return
            slot = len(self._preview_data)
            self._preview_data.append({"table_name": table_name, "rom_name": rom_name,
                                       "image": None, "thumb": None, "loaded": False})

        n = len(self._preview_data)

        if n == 1:
            # ── Single big view ───────────────────────────────────────────────
            self.preview_grid_frame.pack_forget()
            self.preview_single_frame.pack(fill="both", expand=True)
            self.btn_back_preview.pack_forget()
            self._zoom_index = None
            self.preview_title.config(text=table_name[:38])
            self.preview_table_name.config(text=table_name)
            self.preview_rom_name.config(text=f"ROM: {rom_name}" if rom_name else "")
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width()//2 or 220,
                self.preview_canvas.winfo_height()//2 or 245,
                text="⏳", font=("Arial", 32), fill="#ffcc00", anchor="center")
        else:
            # ── Rebuild grid layout to match new count ────────────────────────
            self._rebuild_grid(n)
            if self._zoom_index is None:
                self.preview_single_frame.pack_forget()
                self.preview_grid_frame.pack(fill="both", expand=True, padx=6, pady=6)
            self.preview_title.config(text=f"{n} TABLES")
            # Re-setup all existing slots after grid rebuild
            for i, d in enumerate(self._preview_data):
                self._setup_thumb_cell(i, d["table_name"])
                if d.get("loaded"):
                    self._render_thumb(i)

        # Start image fetch for this slot
        self._start_fetch(slot, table_name, rom_name)

    # Layout map: n_files -> (rows, cols)
    GRID_LAYOUT = {2: (1,2), 3: (1,3), 4: (2,2), 5: (2,3), 6: (2,3)}

    def _rebuild_grid(self, n):
        """Destroy and recreate grid cells to match layout for n files."""
        rows, cols = self.GRID_LAYOUT.get(n, (2, 3))

        # Destroy old cells
        for widget in self.preview_grid_frame.winfo_children():
            widget.destroy()
        self.thumb_cells  = []
        self.thumb_images = []

        # Remove old row/col configs
        for i in range(6):
            self.preview_grid_frame.columnconfigure(i, weight=0, minsize=0)
            self.preview_grid_frame.rowconfigure(   i, weight=0, minsize=0)

        # Thumb size based on layout
        #  1×2 → wide, short   1×3 → wide, short   2×2 → medium   2×3 → small
        sizes = {(1,2): (210, 260), (1,3): (138, 220),
                 (2,2): (210, 190), (2,3): (138, 150)}
        tw, th = sizes.get((rows, cols), (138, 150))

        for row in range(rows):
            self.preview_grid_frame.rowconfigure(row, weight=1)
            for col in range(cols):
                self.preview_grid_frame.columnconfigure(col, weight=1)
                cell = tk.Frame(self.preview_grid_frame, bg="#0d101e",
                                highlightthickness=1, highlightbackground="#2a3060")
                cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
                c = tk.Canvas(cell, bg="#0d101e", highlightthickness=0,
                              width=tw, height=th)
                c.pack(fill="both", expand=True)
                lbl = tk.Label(cell, text="", bg="#0d101e", fg="#a0b4d0",
                               font=("Courier", 7), wraplength=tw-10, justify="center")
                lbl.pack(fill="x", pady=(0, 2))
                self.thumb_cells.append((c, lbl))

    def _start_fetch(self, slot, table_name, rom_name):
        """Look up media DB and kick off background image download."""
        if not self.media_db_ready or not self.vpsdb_lookup or not self.vpinmdb:
            self._on_no_image(slot, table_name); return

        def normalize(s):
            s = s.lower()
            s = re.sub(r"[\'\u2019\u2018`]", "", s)
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            return re.sub(r"\s+", " ", s).strip()

        def word_sorted(s):
            return " ".join(sorted(w for w in s.split() if w not in ("the","a","an","of","and","in")))

        raw = table_name.strip()
        nr  = normalize(raw)
        clean = re.sub(r"\s*\(.*?\)", "", raw).strip()
        nc    = normalize(clean)
        
        candidates = [raw.lower(), nr, word_sorted(nr), clean.lower(), nc, word_sorted(nc)]
        
        # Try hyphenated variations (Spider-Man ↔ Spiderman)
        if '-' in raw:
            no_hyphen = raw.replace('-', '').replace('  ', ' ')
            candidates.append(normalize(no_hyphen))
        
        # Known hyphenated names - try both with and without hyphen
        known_hyphenated = {
            'spiderman': 'spider-man',
            'xmen': 'x-men',
            'tmachine': 't-machine',
        }
        clean_lower = clean.lower()
        for unhyphen, hyphen in known_hyphenated.items():
            if unhyphen in clean_lower:
                # Replace in the clean version
                hyph_version = clean_lower.replace(unhyphen, hyphen)
                candidates.append(normalize(hyph_version))
        
        # Expand abbreviations
        if ' le' in nc or nc.endswith(' le'):
            # LE = Limited Edition
            expanded = nc.replace(' le', ' limited edition')
            candidates.append(expanded)
        
        # Try with/without "The" at start
        if clean.lower().startswith('the '):
            without_the = clean[4:].strip()
            candidates.append(normalize(without_the))
        else:
            candidates.append(normalize(f"the {clean}"))
        
        # Handle parenthetical manufacturer/year
        sm = re.search(r"\(([^)]+)\)\s*$", raw)
        if sm:
            a = sm.group(1).strip(); rest = raw[:sm.start()].strip(); nr2 = normalize(rest)
            candidates += [f"{a.lower()}s {rest.lower()}", f"{a.lower()} {rest.lower()}",
                           normalize(f"{a} {rest}"), word_sorted(nr2)]
            # Try just the manufacturer name without year
            mfg_match = re.match(r"^([A-Za-z]+)", a)
            if mfg_match:
                mfg = mfg_match.group(1)
                candidates.append(normalize(f"{mfg} {rest}"))
        
        # Strip common suffixes (most specific first)
        suffixes = [
            ' pinball adventure', ' pinball adventures', 
            ' the pinball adventure', ' the pinball adventures',
            ' vault edition', ' premium', ' le', ' pro', 
            ' vr', ' vpw', ' sg1', ' vpu'
        ]
        for sfx in suffixes:
            if nc.endswith(sfx): 
                stripped = nc[:-len(sfx)].strip()
                if stripped:
                    candidates.append(stripped)
                    # Also try plural/singular variations
                    if stripped.endswith('s'):
                        candidates.append(stripped[:-1])
                    else:
                        candidates.append(stripped + 's')
        
        seen, unique = set(), []
        for c in candidates:
            if c and c not in seen: seen.add(c); unique.append(c)

        media_id = next((self.vpsdb_lookup[k] for k in unique if k in self.vpsdb_lookup), None)
        if not media_id:
            # Fuzzy matching fallback: word-based similarity
            best_id, best_score = None, 0.0
            table_words = set(nc.split())  # Words from normalized table name
            
            for lk, lid in self.vpsdb_lookup.items():
                if len(lk) < 3: continue
                db_words = set(lk.split())
                
                # Method 1: Word overlap (if table has "hellboy" and DB has "hellboy", match!)
                common = table_words & db_words
                if common:
                    score = len(common) / max(len(table_words), len(db_words))
                    if score > best_score:
                        best_score = score
                        best_id = lid
                
                # Method 2: Substring matching for single-word tables
                if len(table_words) == 1 and len(db_words) == 1:
                    tw = list(table_words)[0]
                    dw = list(db_words)[0]
                    if tw in dw or dw in tw:
                        score = min(len(tw), len(dw)) / max(len(tw), len(dw))
                        if score > best_score:
                            best_score = score
                            best_id = lid
            
            # Accept if confidence is high enough
            if best_id and best_score >= 0.5: media_id = best_id

        if not media_id or media_id not in self.vpinmdb:
            self._on_no_image(slot, table_name); return

        entry = self.vpinmdb[media_id]
        url = (entry.get("1k", {}).get("table") or entry.get("1k", {}).get("fss") or entry.get("wheel"))
        if not url:
            self._on_no_image(slot, table_name); return

        threading.Thread(target=self._fetch_image_for_slot,
                         args=(url, slot, table_name), daemon=True).start()

    def _fetch_image_for_slot(self, url, slot, table_name):
        """Background: download + prepare full + thumb images, then update UI."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.rotate(-90, expand=True)

            # Try wheel
            wheel = None
            try:
                wurl = re.sub(r"1k/.*\.png$", "wheel.png", url)
                if wurl != url:
                    req2 = urllib.request.Request(wurl, headers={"User-Agent": "VPXMergeTool/1.0"})
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        wheel = Image.open(io.BytesIO(r2.read())).convert("RGBA")
            except Exception:
                wheel = None

            full  = img.copy()
            thumb = img.copy()
            thumb.thumbnail((196, 146), Image.Resampling.LANCZOS)

            self._preview_data[slot]["image"]  = full
            self._preview_data[slot]["wheel"]  = wheel
            self._preview_data[slot]["thumb"]  = thumb
            self._preview_data[slot]["loaded"] = True

            self.root.after(0, lambda s=slot: self._render_slot(s))
        except Exception:
            self.root.after(0, lambda s=slot, n=table_name: self._on_no_image(s, n))

    def _render_slot(self, slot):
        """Render slot: big view if single/zoomed, thumbnail if grid."""
        if slot >= len(self._preview_data): return
        data = self._preview_data[slot]
        n    = len(self._preview_data)

        if n == 1 or self._zoom_index == slot:
            # ── Full single view ──────────────────────────────────────────────
            self._render_single(slot)
        else:
            # ── Grid thumbnail ────────────────────────────────────────────────
            self._render_thumb(slot)

    def _render_single(self, slot):
        """Draw full-size image with wheel overlay onto the big canvas."""
        data  = self._preview_data[slot]
        img   = data.get("image")
        wheel = data.get("wheel")
        if not img: return

        self.preview_canvas.update_idletasks()
        cw = self.preview_canvas.winfo_width()  or 440
        ch = self.preview_canvas.winfo_height() or 490

        full = img.copy()
        full.thumbnail((cw - 24, ch - 24), Image.Resampling.LANCZOS)
        pf_w, pf_h = full.size

        composite = Image.new("RGBA", (cw, ch), (26, 26, 26, 255))
        px, py = (cw - pf_w)//2, (ch - pf_h)//2
        composite.paste(full, (px, py), full)

        if wheel:
            from PIL import ImageDraw
            ws = int(cw * 0.34)
            wimg = wheel.copy(); wimg = wimg.resize((ws, ws), Image.Resampling.LANCZOS)
            ww, wh = wimg.size
            wx, wy = (cw - ww)//2, ch - wh - 24
            shadow = Image.new("RGBA", (ww+8, wh+8), (0,0,0,0))
            ImageDraw.Draw(shadow).ellipse([0,0,ww+7,wh+7], fill=(0,0,0,120))
            composite.paste(shadow, (wx-4, wy-4), shadow)
            composite.paste(wimg, (wx, wy), wimg)

        photo = ImageTk.PhotoImage(composite)
        self.current_preview_image = photo
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(cw//2, ch//2, anchor="center", image=photo)
        ix, iy = (cw - pf_w)//2, (ch - pf_h)//2
        self.preview_canvas.create_rectangle(ix-2, iy-2, ix+pf_w+2, iy+pf_h+2,
                                              outline="#ffffff", width=2, fill="")
        self.preview_status.config(text="✓ Preview loaded", fg="#00ff00")

    def _render_thumb(self, slot):
        """Draw thumbnail image into a grid cell."""
        if slot >= len(self.thumb_cells): return
        data  = self._preview_data[slot]
        thumb = data.get("thumb")
        if not thumb: return
        canvas, lbl = self.thumb_cells[slot]
        photo = ImageTk.PhotoImage(thumb)
        while len(self.thumb_images) <= slot: self.thumb_images.append(None)
        self.thumb_images[slot] = photo
        cw = canvas.winfo_width()  or 200
        ch = canvas.winfo_height() or 150
        canvas.delete("all")
        canvas.create_image(cw//2, ch//2, anchor="center", image=photo)
        tw, th = thumb.size
        ix, iy = (cw-tw)//2, (ch-th)//2
        canvas.create_rectangle(ix-1, iy-1, ix+tw+1, iy+th+1,
                                 outline="#ffffff", width=1, fill="")

    def _on_no_image(self, slot, table_name):
        """No image available — show placeholder in the right context."""
        n = len(self._preview_data)
        if n == 1 or self._zoom_index == slot:
            self.show_placeholder_preview(table_name)
        else:
            if slot >= len(self.thumb_cells): return
            canvas, _ = self.thumb_cells[slot]
            canvas.delete("all")
            cw = canvas.winfo_width() or 200
            ch = canvas.winfo_height() or 150
            canvas.create_rectangle(4, 4, cw-4, ch-4, fill="#1a1a1a", outline="#2a3060")
            canvas.create_text(cw//2, ch//2, text="No Preview",
                               fill="#444466", font=("Arial", 8, "bold"), anchor="center")

    def _setup_thumb_cell(self, slot, table_name):
        """Set up grid cell label and click binding."""
        if slot >= len(self.thumb_cells): return
        canvas, lbl = self.thumb_cells[slot]
        short = (table_name[:26] + "…") if len(table_name) > 26 else table_name
        lbl.config(text=short)
        canvas.delete("all")
        cw = canvas.winfo_width() or 200; ch = canvas.winfo_height() or 150
        canvas.create_text(cw//2, ch//2, text="⏳",
                           font=("Arial", 18), fill="#ffcc00", anchor="center")
        canvas.bind("<Button-1>", lambda e, s=slot: self._preview_zoom(s))
        lbl.bind(   "<Button-1>", lambda e, s=slot: self._preview_zoom(s))

    def _preview_zoom(self, slot):
        """Click on grid thumbnail → show in big single view."""
        if slot >= len(self._preview_data): return
        self._zoom_index = slot
        data = self._preview_data[slot]
        # Switch to single view
        self.preview_grid_frame.pack_forget()
        self.preview_single_frame.pack(fill="both", expand=True)
        self.btn_back_preview.pack(side="right", padx=(0, 8))
        self.preview_title.config(text=data["table_name"][:38])
        self.preview_table_name.config(text=data["table_name"])
        self.preview_rom_name.config(text=f"ROM: {data['rom_name']}" if data.get("rom_name") else "")
        if data.get("loaded"):
            self._render_single(slot)
        else:
            self.preview_canvas.delete("all")
            cw = self.preview_canvas.winfo_width() or 440
            ch = self.preview_canvas.winfo_height() or 490
            self.preview_canvas.create_text(cw//2, ch//2, text="⏳ Loading...",
                                             fill="#ffcc00", font=("Arial", 14), anchor="center")

    def _preview_back(self):
        """Back from zoomed single view → return to grid."""
        self._zoom_index = None
        self.preview_single_frame.pack_forget()
        self.preview_grid_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.btn_back_preview.pack_forget()
        self.preview_title.config(text=f"{len(self._preview_data)} TABLES")
        self.preview_table_name.config(text="")
        self.preview_rom_name.config(text="")

    def show_placeholder_preview(self, table_name):
        """Draw placeholder on the big single canvas."""
        self.preview_canvas.delete("all")
        cw = self.preview_canvas.winfo_width()  or 440
        ch = self.preview_canvas.winfo_height() or 490
        self.preview_canvas.create_rectangle(10, 10, cw-10, ch-10,
                                             fill="#1a1a1a", outline="#00ccff", width=2)
        self.preview_canvas.create_text(cw//2, ch//2-20, text="No Preview\nAvailable",
                                        fill="#666666", font=("Arial", 11, "bold"), justify="center")
        short = (table_name[:32] + "…") if len(table_name) > 32 else table_name
        self.preview_canvas.create_text(cw//2, ch//2+30, text=short,
                                        fill="#00ccff", font=("Arial", 8),
                                        justify="center", width=cw-40)
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
                with open(path, 'rb') as f:
                    raw = f.read()
                # Auto-detect encoding by BOM — Windows VBS files are often UTF-16 LE
                if raw[:2] == b'\xff\xfe':
                    return raw.decode('utf-16-le', errors='ignore').encode('latin-1', errors='ignore')
                elif raw[:2] == b'\xfe\xff':
                    return raw.decode('utf-16-be', errors='ignore').encode('latin-1', errors='ignore')
                elif raw[:3] == b'\xef\xbb\xbf':
                    return raw[3:]  # strip UTF-8 BOM, rest is plain ASCII/latin-1
                return raw  # plain ASCII or latin-1, return as-is
            if olefile.isOleFile(path):
                with olefile.OleFileIO(path) as ole:
                    for s in ole.listdir():
                        if any(x in str(s).lower() for x in ["gamestru", "mac", "version"]): continue
                        with ole.openstream(s) as stream:
                            d = stream.read()
                            # Must contain "Option Explicit" or "Option Base" - the definitive script marker
                            # This prevents matching binary streams that happen to contain ' bytes
                            idx = d.lower().find(b'option ')
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

    def auto_fix_script(self, script):
        """Auto-patch common VPX standalone incompatibilities."""
        if not script:
            return script, []

        fixes_applied = []
        fixed = script

        # 1. Fix WScript.Shell registry reads for NVRAM path
        if 'WScript.Shell' in fixed or 'WshShell' in fixed:
            # Replace GetNVramPath function
            import re
            pattern = r'Function GetNVramPath\(\).*?End [Ff]unction'
            if re.search(pattern, fixed, re.DOTALL | re.IGNORECASE):
                replacement = r'Function GetNVramPath()' + '\n    GetNVramPath = ".\\\\pinmame\\\\nvram\\\\"' + '\nEnd Function'
                fixed = re.sub(pattern, replacement, fixed, flags=re.DOTALL | re.IGNORECASE)
                fixes_applied.append("Fixed GetNVramPath() to use local pinmame folder")

            # Remove standalone WScript.Shell CreateObject lines (any variable name)
            lines = fixed.split('\n')
            new_lines = []
            for line in lines:
                # Match: Set <variable> = CreateObject("WScript.Shell")
                if re.search(r'Set\s+\w+\s*=\s*CreateObject\s*\(\s*["\']WScript\.Shell', line, re.IGNORECASE):
                    new_lines.append("    ' " + line.strip() + " ' REMOVED - not supported in VPX standalone")
                    if "Fixed WScript.Shell CreateObject" not in fixes_applied:
                        fixes_applied.append("Removed WScript.Shell CreateObject (not supported)")
                else:
                    new_lines.append(line)
            fixed = '\n'.join(new_lines)

        # 2. Comment out problematic registry reads
        if 'RegRead' in fixed:
            lines = fixed.split('\n')
            new_lines = []
            for line in lines:
                if 'RegRead' in line and '=' in line:
                    # Extract variable being assigned
                    var_match = re.search(r'(\w+)\s*=.*RegRead', line)
                    if var_match:
                        var_name = var_match.group(1)
                        new_lines.append("    ' " + line.strip() + " ' REMOVED")
                        new_lines.append(f'    {var_name} = ".\\\\\\\\pinmame\\\\\\\\nvram\\\\\\\\" \' Auto-fixed by VPX Utility')
                        if "Fixed RegRead" not in fixes_applied:
                            fixes_applied.append("Fixed RegRead to use local path")
                    else:
                        new_lines.append("    ' " + line.strip())
                else:
                    new_lines.append(line)
            fixed = '\n'.join(new_lines)

        # 3. Stub out other problematic COM objects
        problematic_objects = [
            ('SAPI.SpVoice', 'text-to-speech'),
            ('WMPlayer.OCX', 'Windows Media Player'),
        ]
        for obj, desc in problematic_objects:
            if obj in fixed:
                lines = fixed.split('\n')
                new_lines = []
                for line in lines:
                    if f'CreateObject("{obj}")' in line or f"CreateObject('{obj}')" in line:
                        new_lines.append("    ' " + line.strip() + f" ' REMOVED - {desc} not supported")
                        fixes_applied.append(f"Removed {desc} CreateObject")
                    else:
                        new_lines.append(line)
                fixed = '\n'.join(new_lines)

        # 4. Remove deprecated B2S.Server properties
        deprecated_props = ['ShowDMDOnly', 'ShowFrame', 'ShowTitle']
        b2s_fixed = False
        for prop in deprecated_props:
            if prop in fixed:
                lines = fixed.split('\n')
                new_lines = []
                for line in lines:
                    if f'.{prop}' in line and '=' in line:
                        new_lines.append("    ' " + line.strip() + " ' REMOVED - deprecated B2S property")
                        b2s_fixed = True
                    else:
                        new_lines.append(line)
                fixed = '\n'.join(new_lines)
        if b2s_fixed:
            fixes_applied.append("Removed deprecated B2S properties (ShowDMDOnly, ShowFrame, ShowTitle)")

        return fixed, fixes_applied


    def scan_and_copy_media(self, source_pup_path, table_name, target_table_folder):
        """
        Scan POPMedia/Visual Pinball X subfolders and fuzzy-match media to table_name.
        Outputs to target_table_folder/medias/
        Skips silently if medias/ folder already exists.

        Renaming:
          Playfield  → table.mp4        Menu      → fulldmd.mp4
          Loading    → loading.mp4      Gameinfo  → flyer.png
          GameHelp   → rules.png        Backglass → bg.mp4
          AudioLaunch→ audiolaunch.mp3  Audio     → audio.mp3
          Wheel      → wheel.png  (wheel.apng preserved if source is .apng)
        """
        if not self.include_media.get():
            return []
        if not source_pup_path:
            return []

        # ── Output folder ────────────────────────────────────────────────────
        media_dest = os.path.join(target_table_folder, "medias")
        if os.path.isdir(media_dest):
            return []          # already done — skip

        # ── Locate POPMedia (one level up from PUPVideos source) ─────────────
        parent       = os.path.dirname(source_pup_path.rstrip('/\\'))
        popmedia     = os.path.join(parent, "POPMedia", "Visual Pinball X")
        if not os.path.exists(popmedia):
            return []

        media_mappings = [
            ("Playfield",    [".mp4", ".avi", ".f4v"],   "table"),
            ("Menu",         [".mp4", ".avi", ".f4v"],   "fulldmd"),
            ("Loading",      [".mp4", ".avi", ".f4v"],   "loading"),
            ("Gameinfo",     [".png", ".jpg", ".jpeg"],  "flyer"),
            ("GameHelp",     [".png", ".jpg", ".jpeg"],  "rules"),
            ("Backglass",    [".mp4", ".avi", ".f4v"],   "bg"),
            ("AudioLaunch",  [".mp3", ".wav"],           "audiolaunch"),
            ("Audio",        [".mp3", ".wav"],           "audio"),
            ("Wheel",        [".png", ".apng", ".jpg"],  "wheel"),
        ]

        copied = []

        for folder_name, extensions, target_base in media_mappings:
            src_folder = os.path.join(popmedia, folder_name)
            if not os.path.exists(src_folder):
                continue

            # List only files with valid extensions
            try:
                candidates = [f for f in os.listdir(src_folder)
                              if os.path.splitext(f)[1].lower() in extensions]
            except Exception:
                continue

            # ── Exact match first, then fuzzy ────────────────────────────────
            best_file, best_score = None, 0.0
            for fname in candidates:
                fbase = os.path.splitext(fname)[0]
                if fbase.lower() == table_name.lower():
                    best_file, best_score = fname, 1.0
                    break
                score = _mfuzzy(table_name, fbase)
                if score > best_score:
                    best_score, best_file = score, fname

            if not best_file or best_score < 0.5:
                continue

            ext         = os.path.splitext(best_file)[1].lower()
            target_name = f"{target_base}{ext}"
            src_file    = os.path.join(src_folder, best_file)
            dst_file    = os.path.join(media_dest, target_name)

            try:
                os.makedirs(media_dest, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied.append({
                    'original': f"{folder_name}/{best_file}",
                    'renamed':  target_name,
                    'score':    best_score,
                })
            except Exception:
                pass

        # ── Write media_log.ini ───────────────────────────────────────────────
        if copied:
            try:
                with open(os.path.join(media_dest, "media_log.ini"), 'w', encoding='utf-8') as lf:
                    lf.write(f"# Media Rename Log — {table_name}\n")
                    lf.write(f"# Generated by VPXmerge\n")
                    lf.write(f"# Original = Renamed\n\n")
                    lf.write(f"[{table_name}]\n")
                    for item in copied:
                        lf.write(f"{item['original']} = {item['renamed']}\n")
            except Exception:
                pass

        return copied

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
            self.progress_frame.config(height=36, pady=4)
            self.progress_bar.pack(fill="x")
            self.progress_label.pack(anchor="w")
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
        elif mode == "fix":
            self.log_audit("🔧 AUTO-FIXING SCRIPT FOR VPX STANDALONE...", "white")
            self.log_audit("")
        
        total_files = len(self.vpx_files)
        
        for idx, f in enumerate(self.vpx_files):
            fname = os.path.basename(f); v_base = os.path.splitext(fname)[0]
            script_raw = self.extract_script(f)  # raw bytes - used for writing carbon copy
            # Decode to string for all regex/text operations
            script = script_raw.decode('latin-1', errors='ignore') if isinstance(script_raw, bytes) else (script_raw or '')
            if not script and mode == "scan":
                self.log_audit(f"⚠ Could not read script from: {fname}", "missing")
            table_dest = os.path.join(target_root, v_base)
            
            # Update progress
            if mode != "scan":
                progress = ((idx + 1) / total_files) * 100
                self.progress_bar['value'] = progress
                self.progress_label.config(text=f"Processing {idx + 1}/{total_files}: {v_base}")
                self.root.update_idletasks()
            
            # Setup Folder Structure — patch saves next to source, full/fix need table subfolder
            if mode in ["full", "fix"]: os.makedirs(table_dest, exist_ok=True)
            
            # Extract ROM name for preview
            rom_for_preview = None
            if script:
                rom_m = re.search(r'(?:Const\s+)?c?(?:Game|Rom)Name\s*=\s*(["\'])([^"\']+)\1', script, re.IGNORECASE)
                rom_for_preview = rom_m.group(2) if rom_m else None
                if not rom_for_preview:
                    cgame_m = re.search(r'cGameName\s*=\s*(["\'])([^"\']+)\1', script, re.IGNORECASE)
                    if cgame_m:
                        rom_for_preview = cgame_m.group(2).strip()
                if not rom_for_preview:
                    optrom_m = re.search(r'OptRom\s*=\s*(["\'])([^"\']+)\1', script, re.IGNORECASE)
                    if optrom_m:
                        rom_for_preview = optrom_m.group(2).strip()
            
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
                
                # Copy media files if enabled
                if self.include_media.get():
                    media_dest_check = os.path.join(table_dest, "medias")
                    if os.path.isdir(media_dest_check):
                        self.log_audit(f"10-MEDIA: SKIPPED (medias/ already exists)", "yellow")
                    else:
                        media_copied = self.scan_and_copy_media(p_dir, v_base, table_dest)
                        if media_copied:
                            self.log_audit(f"10-MEDIA: {len(media_copied)} files copied → medias/", "found")
                            for item in media_copied:
                                self.log_audit(f"   → {item['original']} → {item['renamed']}  ({item['score']:.0%})", "found")
                            self.file_stats['media'] = self.file_stats.get('media', 0) + len(media_copied)
                        else:
                            self.log_audit(f"10-MEDIA: No matching media found", "missing")
            elif mode == "patch": 
                self.log_separator("double")
                self.log_audit(f"  Table: {fname}", "table_name")
                self.log_separator("single")

            # 1. ROM Logic — detect before backglass so audit order matches numbering
            rom = None
            if script and mode not in ["patch", "fix"]:
                rom_m = re.search(r'(?:Const\s+)?c?(?:Game|Rom)Name\s*=\s*(["\'])([^"\']+)\1', script, re.IGNORECASE)
                rom = rom_m.group(2) if rom_m else None
                # Fallback 1: explicitly look for cGameName = "value" if primary match missed
                if not rom:
                    cgame_m = re.search(r'cGameName\s*=\s*(["\'])([^"\']+)\1', script, re.IGNORECASE)
                    if cgame_m:
                        rom = cgame_m.group(2).strip()
                # Fallback 2: OptRom = "playboys" style
                if not rom:
                    optrom_m = re.search(r'OptRom\s*=\s*(["\'])([^"\']+)\1', script, re.IGNORECASE)
                    if optrom_m:
                        rom = optrom_m.group(2).strip()
                if rom:
                    if not v_dir:
                        if mode == "scan": self.log_audit(f"1-ROM: {rom} (VPINMAME path not set)", "missing")
                    else:
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
                else:
                    if mode == "scan": self.log_audit("1-ROM: NOT DETECTED IN SCRIPT", "missing")

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
                
                # PUP pack: try rom name first, then v_base as fallback
                pup_found = False
                for pup_name in ([rom, v_base] if rom and rom != v_base else [v_base]):
                    if not pup_name: continue
                    pup_src = os.path.join(p_dir, pup_name)
                    if os.path.exists(pup_src):
                        if mode == "scan": self.log_audit(f"6-PUP-PACK: {pup_name} (DETECTED)", "found")
                        elif mode == "full":
                            shutil.copytree(pup_src, os.path.join(table_dest, "pupvideos", pup_name), dirs_exist_ok=True)
                            self.file_stats['pup_packs'] += 1
                        pup_found = True
                        break
                if not pup_found:
                    if mode == "scan": self.log_audit("6-PUP-PACK: NOT FOUND", "missing")

                # 7. Music Logic (Flat Export to 'music' folder)
                # 8. Music — collect all subfolder references from PlayMusic calls
                # Handles both:
                #   PlayMusic "OBWAT/OBWAT1.mp3"  -> subfolder OBWAT in m_dir
                #   PlayMusic "track.mp3"          -> flat file in m_dir root or named subfolder
                m_found = False
                f_folders = set()  # subfolder names to search for in m_dir

                # Extract subfolder from PlayMusic "folder/file.mp3" or PlayMusic "folder\file.mp3"
                pm_matches = re.findall(r'PlayMusic\s*["\']?([^"\',;\r\n]+)', script, re.IGNORECASE)
                for path in pm_matches:
                    path = path.strip().strip('"\'\\/ ')
                    # Check for subfolder separator (/ or \)
                    for sep in ['/', '\\\\', '\\']:
                        if sep in path:
                            folder = path.split(sep)[0].strip()
                            if folder:
                                f_folders.add(folder)
                            break

                # Also check MusicSubDirectory and fallback names
                subdir_m = re.search(r'MusicSubDirectory\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                if subdir_m:
                    f_folders.add(subdir_m.group(1).replace("\\", "").strip())
                # Fallback: rom name and v_base as folder names
                f_folders.add(v_base)
                if rom:
                    f_folders.add(rom)

                if os.path.exists(m_dir):
                    all_sub = [d for d in os.listdir(m_dir) if os.path.isdir(os.path.join(m_dir, d))]
                    for target in sorted(f_folders):
                        for real in all_sub:
                            if real.lower() == target.lower():
                                m_found = True
                                full_m = os.path.join(m_dir, real)
                                music_files = sorted([trk for trk in os.listdir(full_m) if trk.lower().endswith(('.mp3', '.ogg', '.wav', '.flac'))])
                                if mode == "scan":
                                    files_str = ', '.join(music_files)
                                    self.log_audit(f"8-MUSIC: (DETECTED) {real}/ [{files_str}]", "found")
                                elif mode == "full":
                                    # Preserve subfolder structure: music/OBWAT/*.mp3
                                    dest_music = os.path.join(table_dest, "music", real)
                                    os.makedirs(dest_music, exist_ok=True)
                                    for trk in music_files:
                                        shutil.copy2(os.path.join(full_m, trk), dest_music)
                                    self.file_stats['music_tracks'] += len(music_files)
                if mode == "scan" and not m_found: self.log_audit("8-MUSIC: NOT FOUND", "missing")

                # 9. Patch Lookup (GitHub) - runs in all modes
                if self.enable_patch_lookup.get():
                    patch_result = self.find_github_patch(fname)
                    if patch_result['found']:
                        patch_name = patch_result['name']
                        if mode == "scan":
                            self.log_audit(f"9-PATCH: {patch_name} (DETECTED)", "found")
                        elif mode in ["full", "patch"]:
                            # For patch mode: save next to the source file
                            # For full mode: save inside the export table folder
                            if mode == "patch":
                                save_dir = os.path.dirname(f)
                            else:
                                save_dir = table_dest
                                os.makedirs(save_dir, exist_ok=True)
                            patch_save_path = os.path.join(save_dir, f"{v_base}.vbs")
                            if self.download_patch(patch_result['download_url'], patch_save_path):
                                self.log_audit(f"9-PATCH: {patch_name} (DOWNLOADED)", "found")
                                self.log_audit(f"   → Saved: {patch_save_path}", "found")
                                self.file_stats['patches'] += 1
                            else:
                                self.log_audit(f"9-PATCH: Download FAILED for {patch_name}", "missing")
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
                    if script_raw and len(script_raw) > 0:
                        raw_out = script_raw if isinstance(script_raw, bytes) else script.encode('latin-1', errors='replace')
                        raw_out = raw_out.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
                        with open(vbs_path, "wb") as vf:
                            vf.write(raw_out)
                        self.log_audit(f"VBS CREATED: {v_base}.vbs ({len(raw_out):,} bytes)", "found")
                        self.file_stats['vbs_files'] += 1
                    else:
                        self.log_audit(f"VBS FAILED: could not extract script from {fname}", "missing")

                # Script Auto-Fixer
                if mode == "fix":
                    if script:
                        fixed_script, fixes = self.auto_fix_script(script)
                        if fixes:
                            # Copy VPX to target subfolder and save fixed VBS next to it
                            vpx_dest = os.path.join(table_dest, fname)
                            fix_path = os.path.join(table_dest, f"{v_base}.vbs")
                            # Only copy VPX if source and destination are different
                            if os.path.abspath(f) != os.path.abspath(vpx_dest):
                                shutil.copy2(f, vpx_dest)
                            with open(fix_path, "w", encoding='latin-1', errors='replace') as vf:
                                vf.write(fixed_script)
                            self.log_audit(f"✓ FIXED: {v_base}.vbs", "found")
                            for fix in fixes:
                                self.log_audit(f"   • {fix}", "found")
                            self.log_audit(f"   → VPX copied to: {table_dest}/", "found")
                            self.log_audit(f"   → Fixed VBS saved next to VPX", "found")
                            self.file_stats['vbs_files'] += 1
                        else:
                            self.log_audit(f"✓ NO ISSUES DETECTED in {fname}", "yellow")
                    else:
                        self.log_audit(f"✗ Could not read script from {fname}", "missing")

            if mode == "scan": 
                self.log_separator("bottom")
                self.log_audit("")
        self.root.after(0, self.reset_ui)
        
        # Hide progress bar — collapse frame back to 1px, no layout shift
        if mode != "scan":
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()
            self.progress_frame.config(height=1, pady=0)
        
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
        self.clear_list()
        self.drop_hint.place_forget()  # hide drop hint once file is dropped
        # splitlist handles brace-wrapped paths; strip any residual {} for safety
        try:
            raw_files = self.root.tk.splitlist(event.data)
        except Exception:
            raw_files = event.data.split()
        files = []
        for f in raw_files:
            f = f.strip('{}').strip()
            # Handle paths that still have braces around them (spaces/parens in name)
            if f.startswith('{') and f.endswith('}'):
                f = f[1:-1]
            files.append(f)
        self.vpx_files = [f for f in files if f.lower().endswith(('.vpx', '.vbs'))]
        self.audit_logic("scan")

    def start_thread(self, mode):
        self.btn_full.config(state="disabled")
        self.btn_vbs.config(state="disabled")
        self.btn_fix.config(state="disabled")
        threading.Thread(target=lambda: self.audit_logic(mode), daemon=True).start()

    def reset_ui(self):
        if self.vpx_files:
            self.btn_full.config(state="normal")
            self.btn_fix.config(state="normal")
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
        self.btn_fix.config(state="disabled")
        # Show drop hint again
        try:
            self.drop_hint.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass
        
        # Reset preview — back to single view, clear all state
        self._preview_data = []
        self._zoom_index   = None
        self.thumb_images  = []
        self.current_preview_image = None
        for c, lbl in self.thumb_cells:
            c.delete("all"); lbl.config(text="")
        self.preview_grid_frame.pack_forget()
        self.preview_single_frame.pack(fill="both", expand=True)
        self.btn_back_preview.pack_forget()
        self.preview_canvas.delete("all")
        self.preview_title.config(text="TABLE PREVIEW")
        self.preview_table_name.config(text="")
        self.preview_rom_name.config(text="")
        self.preview_status.config(text="Drop a .vpx file to preview", fg="#888888")

    def save_settings(self):
        data = {"sources": {k: v.get() for k, v in self.sources.items()}, "target": self.target.get()}
        with open(self.config_file, "w") as f: json.dump(data, f)

if __name__ == "__main__":
    root = TkinterDnD.Tk(); app = VPXStandaloneMergingUtility(root); root.mainloop()
