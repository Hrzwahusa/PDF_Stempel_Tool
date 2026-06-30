import tkinter as tk
from tkinter import filedialog
from tkinter import PhotoImage
import json
import os
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import shutil
import time


class PDFStamperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Stempel Tool")
        
        # Pfad zum Verzeichnis der ausführbaren Datei (für Stempel, Config)
        if getattr(sys, 'frozen', False):
            self.app_path = os.path.dirname(sys.executable)
        else:
            self.app_path = os.path.dirname(os.path.abspath(__file__))
        
        # Konfigurationsdatei
        self.config_file = "pdf_stamper_config.json"
        self.config = self.load_config()
        
        # Variablen
        self.version = "1.3.0"
        self.current_pdf = None
        self.pdf_document = None
        self.current_page = 0
        self.zoom = 1.0
        self.selected_stamp = None
        self.stamps = []
        self.watch_files = []
        self.file_paths = []  # Index-Liste: Position in Listbox → vollständiger Pfad
        self.page_positions = []   # (page_index, y_start, y_end) für alle sichtbaren Seiten
        self.page_photo_refs = []  # Referenzen auf PhotoImage-Objekte (verhindert GC)
        self.stamped_pages = set() # Seitenindizes auf denen ein Stempel platziert wurde
        self._fa_icons = {}        # PhotoImage-Referenzen (verhindert GC)
        self.auto_save_var = tk.BooleanVar(value=self.config.get("auto_save", False))
        self.auto_delete_var=tk.BooleanVar(value=self.config.get("auto_delete", False))
        self.simple_stamp_var = tk.BooleanVar(value=self.config.get("simple_stamp_mode", False))
        
        # Skalierungsfaktor relativ zu 1920px Referenzbreite
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.scale = max(0.75, min(2.0, sw / 1920))
        self.s = lambda n: max(1, round(n * self.scale))
        win_w = min(self.s(1200), sw - 50)
        win_h = min(self.s(800),  sh - 80)
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(self.s(700), self.s(450))

        icon_path = self._resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # Theme + GUI erstellen
        self._setup_theme()
        self.create_gui()

        if self.config.get("simple_stamp_mode", False):
            self.root.title("PDF Stempel Tool  [Einfacher Modus]")

        # Überwachung starten
        self.watch_folder()
        
    def load_config(self):
        """Konfiguration laden oder Standard erstellen"""
        default_config = {
            "open_path": str(Path.home() / "Documents"),
            "save_path": str(Path.home() / "Documents"),
            "dfq_path": str(Path.home() / "Documents"),
            "dfq_out": str(Path.home() / "Documents"),
            "stabi_path": str(Path.home() / "Documents"),
            "oqis_ein_path": str(Path.home() / "Documents"),
            "dfq_same_as_open": True,
            "auto_save": False,
            "auto_delete": False,
            "auto_delete_time": 12,
            "auto_move_sonstige": False,
            "simple_stamp_mode": False
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    return config
            except:
                return default_config
        return default_config

    def cleanup_old_files(self):
        if self.config.get("auto_delete", False):
            current_time = time.time()
            time_limit = self.config.get("auto_delete_time") * 60 * 60 #alle Datein älter x stunden
            
            unstamped_files_path = self.config.get("open_path")
            stamped_files_path = self.config.get("save_path")
            # Alte ungestempelte löschen
            if(os.path.exists(unstamped_files_path)):
                for root, dirs, files in os.walk(unstamped_files_path):
                    for file in files:
                        if(file.lower().endswith('.pdf')):
                            full_path = os.path.normpath(os.path.join(root, file))
                            file_time = os.path.getmtime(full_path)
                            if(current_time - file_time > time_limit):
                                try:
                                    os.remove(full_path)
                                    print(f"Datei '{file}' erfolgreich geloescht!")
                                except FileNotFoundError: print(f"Datei '{file}' nicht gefunden.")
        
    def on_mousewheel(self, event):
        """Mausrad im PDF Canvas: Ctrl+Rad → Zoom, sonst Scrollen"""
        ctrl = (event.state & 0x4) != 0
        if ctrl:
            if event.num == 5 or event.delta < 0:
                self.zoom_out()
            elif event.num == 4 or event.delta > 0:
                self.zoom_in()
        else:
            if event.num == 5 or event.delta < 0:
                self.pdf_canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.pdf_canvas.yview_scroll(-1, "units")
        return "break"
    
    def _resource_path(self, *parts):
        """Pfad zu gebündelten Ressourcen: sys._MEIPASS bei .exe, sonst app_path"""
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = self.app_path
        return os.path.join(base, *parts)

    def get_stamp_folder(self):
        """Gibt den Stempel-Ordner-Pfad zurück (immer relativ zur .exe)"""
        return os.path.join(self.app_path, "Stempel")
    
    def save_config(self):
        """Konfiguration speichern"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
    
    def _setup_theme(self):
        """Farben und Schriften des Unternehmens-Designsystems"""
        self.C_BG        = "#F0F2F4"   # Gray 100 – App-Hintergrund (sichtbar gegen Weiß)
        self.C_WHITE     = "#FFFFFF"   # Content-Flächen (Galerie, Liste)
        self.C_PRIMARY   = "#0057B7"   # Blue
        self.C_PRI_HOV   = "#0C67CA"   # Button Hover
        self.C_PRI_PRE   = "#014A9D"   # Button Pressed
        self.C_SELECTED  = "#DBEBFC"   # Blue 200
        self.C_BORDER    = "#C9D2D9"   # Gray 400
        self.C_TEXT      = "#1F272E"   # Gray 1300
        self.C_HINT      = "#63788D"   # Gray 800
        self.C_SURFACE   = "#F0F2F4"   # Gray 100 (identisch mit C_BG, für Buttons)
        self.C_DANGER_BG = "#FEF2F2"
        self.C_DANGER_FG = "#B91C1C"
        self.C_DANGER_HV = "#FEE2E2"
        self.C_CANVAS_BG = "#3A3F47"   # Dunkler Hintergrund für PDF-Canvas

        _fs = lambda n: max(8, round(n * max(0.75, min(1.5, self.scale))))
        self.F_HEADING  = ("Segoe UI", _fs(13), "bold")
        self.F_BODY     = ("Segoe UI", _fs(13))
        self.F_SMALL    = ("Segoe UI", _fs(11))
        self.F_BTN_PRI  = ("Segoe UI", _fs(13))
        self.F_BTN_SEC  = ("Segoe UI", _fs(11))
        self.F_MONO     = ("Courier New", _fs(10))

        # Font Awesome Solid Codepoints
        self.IC_FOLDER = ""
        self.IC_SAVE   = ""
        self.IC_TRASH  = ""
        self.IC_FILE   = ""
        self.IC_CHECK  = ""

    def _btn(self, parent, text, command, style="secondary", **kwargs):
        """Erstellt einen gestylten Button mit Hover-Effekt"""
        if style == "primary":
            bg, fg, hov, pre = self.C_PRIMARY, self.C_WHITE, self.C_PRI_HOV, self.C_PRI_PRE
            font, px, py = self.F_BTN_PRI, self.s(16), self.s(8)
        elif style == "primary_small":
            bg, fg, hov, pre = self.C_PRIMARY, self.C_WHITE, self.C_PRI_HOV, self.C_PRI_PRE
            font, px, py = self.F_BTN_SEC, self.s(10), self.s(6)
        elif style == "danger":
            bg, fg, hov, pre = self.C_DANGER_BG, self.C_DANGER_FG, self.C_DANGER_HV, self.C_DANGER_HV
            font, px, py = self.F_BTN_SEC, self.s(10), self.s(6)
        else:
            bg, fg, hov, pre = self.C_SURFACE, self.C_TEXT, self.C_BORDER, self.C_BORDER
            font, px, py = self.F_BTN_SEC, self.s(10), self.s(6)

        if kwargs.get("image") is None:
            kwargs.pop("image", None)
            kwargs.pop("compound", None)
        btn = tk.Button(parent, text=text, command=command,
                        bg=bg, fg=fg, font=kwargs.pop("font", font),
                        relief=tk.FLAT, bd=0, padx=px, pady=py,
                        activebackground=pre, activeforeground=fg,
                        cursor="hand2", **kwargs)
        btn.bind("<Enter>",           lambda e, b=btn, c=hov: b.config(bg=c))
        btn.bind("<Leave>",           lambda e, b=btn, c=bg:  b.config(bg=c))
        btn.bind("<ButtonPress-1>",   lambda e, b=btn, c=pre: b.config(bg=c))
        btn.bind("<ButtonRelease-1>", lambda e, b=btn, c=hov: b.config(bg=c))
        return btn

    def _section_label(self, parent, text):
        return tk.Label(parent, text=text, font=self.F_HEADING,
                        bg=self.C_BG, fg=self.C_TEXT, anchor="w")

    def _fa_icon(self, codepoint, size=14, color="#FFFFFF"):
        """Rendert ein Font Awesome Solid Icon als PhotoImage (fallback: None)"""
        font_path = self._resource_path("fonts", "fa-solid-900.ttf")
        if not os.path.exists(font_path):
            return None
        try:
            fa = ImageFont.truetype(font_path, size)
            dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            bbox = dummy.textbbox((0, 0), codepoint, font=fa)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            ImageDraw.Draw(img).text((-bbox[0], -bbox[1]), codepoint,
                                     font=fa, fill=(r, g, b, 255))
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _dialog(self, title, width=420):
        """Erstellt ein gestyltes Toplevel-Dialogfenster"""
        width = self.s(width)
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg=self.C_BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.minsize(width, 0)
        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width() // 2 - width // 2
        ry = self.root.winfo_rooty() + self.root.winfo_height() // 2 - 100
        dlg.geometry(f"+{rx}+{ry}")
        return dlg

    def _entry_field(self, parent, **kwargs):
        """Gestyltes Entry-Widget mit Rahmen"""
        frame = tk.Frame(parent, bg=self.C_WHITE,
                         highlightthickness=1, highlightbackground=self.C_BORDER)
        entry = tk.Entry(frame, bg=self.C_WHITE, fg=self.C_TEXT,
                         font=self.F_BODY, relief=tk.FLAT,
                         insertbackground=self.C_TEXT, **kwargs)
        entry.pack(fill=tk.X, padx=6, pady=5)
        return frame, entry

    def _msgbox(self, title, message, kind="info"):
        """Gestylter Hinweisdialog (ersetzt messagebox.show*)"""
        dlg = self._dialog(title, width=420)
        content = tk.Frame(dlg, bg=self.C_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=(20, 8))
        icons = {"info": ("ℹ", self.C_PRIMARY), "warning": ("⚠", "#E6A817"), "error": ("✕", self.C_DANGER_FG)}
        icon_char, icon_color = icons.get(kind, icons["info"])
        tk.Label(content, text=icon_char, font=("Segoe UI Symbol", 20), bg=self.C_BG,
                 fg=icon_color).pack(side=tk.LEFT, anchor="n", padx=(0, 14))
        tk.Label(content, text=message, font=self.F_BODY, bg=self.C_BG, fg=self.C_TEXT,
                 justify=tk.LEFT, wraplength=340).pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="n")
        tk.Frame(dlg, bg=self.C_BORDER, height=1).pack(fill=tk.X, pady=(8, 0))
        btn_row = tk.Frame(dlg, bg=self.C_BG)
        btn_row.pack(pady=10, padx=20, anchor="e")
        self._btn(btn_row, "OK", command=dlg.destroy, style="primary").pack(side=tk.RIGHT)
        dlg.wait_window()

    def _ask_yesno(self, title, message):
        """Gestylter Bestätigungsdialog (ersetzt messagebox.askyesno)"""
        result = [False]
        dlg = self._dialog(title, width=440)
        content = tk.Frame(dlg, bg=self.C_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=(20, 8))
        tk.Label(content, text="?", font=("Segoe UI", 20), bg=self.C_BG,
                 fg=self.C_PRIMARY).pack(side=tk.LEFT, anchor="n", padx=(0, 14))
        tk.Label(content, text=message, font=self.F_BODY, bg=self.C_BG, fg=self.C_TEXT,
                 justify=tk.LEFT, wraplength=355).pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="n")
        tk.Frame(dlg, bg=self.C_BORDER, height=1).pack(fill=tk.X, pady=(8, 0))
        btn_row = tk.Frame(dlg, bg=self.C_BG)
        btn_row.pack(pady=10, padx=20, anchor="e")
        def yes():
            result[0] = True
            dlg.destroy()
        self._btn(btn_row, "Nein", command=dlg.destroy, style="secondary").pack(side=tk.RIGHT, padx=(6, 0))
        self._btn(btn_row, "Ja", command=yes, style="primary").pack(side=tk.RIGHT)
        dlg.wait_window()
        return result[0]

    def create_gui(self):
        """GUI-Elemente erstellen"""
        self.root.configure(bg=self.C_BG)

        # Font Awesome Icons vorrendern (None wenn Font nicht vorhanden)
        self._fa_icons["folder"] = self._fa_icon(self.IC_FOLDER, size=self.s(13), color=self.C_WHITE)
        self._fa_icons["save"]   = self._fa_icon(self.IC_SAVE,   size=self.s(13), color=self.C_WHITE)
        self._fa_icons["trash"]  = self._fa_icon(self.IC_TRASH,  size=self.s(12), color=self.C_DANGER_FG)
        self._fa_icons["file"]   = self._fa_icon(self.IC_FILE,   size=self.s(13), color=self.C_PRIMARY)
        self._fa_icons["check"]  = self._fa_icon(self.IC_CHECK,  size=self.s(13), color=self.C_PRIMARY)

        # ── Menüleiste ──────────────────────────────────────────────────────
        def _menu(parent=None):
            opts = dict(tearoff=0, bg=self.C_WHITE, fg=self.C_TEXT,
                        activebackground=self.C_SELECTED, activeforeground=self.C_TEXT,
                        borderwidth=1, relief=tk.SOLID,
                        font=self.F_SMALL)
            return tk.Menu(parent, **opts) if parent else tk.Menu(self.root,
                           bg=self.C_BG, fg=self.C_TEXT,
                           activebackground=self.C_SELECTED,
                           activeforeground=self.C_TEXT,
                           borderwidth=0, relief=tk.FLAT,
                           font=self.F_SMALL)

        menubar = _menu()
        self.root.config(menu=menubar)

        file_menu = _menu(menubar)
        menubar.add_cascade(label="Datei", menu=file_menu)
        file_menu.add_command(label="PDF öffnen",    command=self.open_pdf)
        file_menu.add_command(label="PDF speichern", command=self.save_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden",       command=self.root.quit)

        menubar.add_command(label="Einstellungen", command=self.show_settings)

        info_menu = _menu(menubar)
        menubar.add_cascade(label="?", menu=info_menu)
        info_menu.add_command(label="Hilfe",  command=self.show_help)
        info_menu.add_separator()
        info_menu.add_command(label="Info",   command=self.show_info)

        # ── Hauptcontainer ──────────────────────────────────────────────────
        main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                                        bg=self.C_BG, sashwidth=self.s(5),
                                        sashrelief=tk.FLAT, sashpad=2,
                                        borderwidth=0)
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # ── Linke Seite ─────────────────────────────────────────────────────
        left_frame = tk.Frame(main_container, width=self.s(360), bg=self.C_BG,
                             highlightthickness=0)
        main_container.add(left_frame, minsize=self.s(260), padx=0, pady=0)

        self._section_label(left_frame, "Stempel").pack(anchor="center", padx=8, pady=(8, 2))

        self.preview_frame = tk.Frame(left_frame, bg=self.C_CANVAS_BG, height=self.s(80),
                                      highlightthickness=1,
                                      highlightbackground=self.C_BORDER)
        self.preview_frame.pack(fill=tk.X, padx=8, pady=4)
        self.preview_frame.pack_propagate(False)
        self.preview_label = tk.Label(self.preview_frame,
                                      text="Kein Stempel ausgewählt",
                                      bg=self.C_BG, fg=self.C_HINT,
                                      font=self.F_SMALL)
        self.preview_label.pack(expand=True)

        stamp_btn_row = tk.Frame(left_frame, bg=self.C_BG)
        stamp_btn_row.pack(fill=tk.X, padx=8, pady=4)
        inner_btn_row = tk.Frame(stamp_btn_row, bg=self.C_BG)
        inner_btn_row.pack(anchor="center")
        self._btn(inner_btn_row, "Stempel abwählen",
                  command=self.deselect_stamp, style="primary_small").pack(side=tk.LEFT, padx=(0, 4))
        self._btn(inner_btn_row, "Alle entfernen",
                  command=self.clear_all_stamps, style="danger",
                  image=self._fa_icons["trash"], compound=tk.LEFT).pack(side=tk.LEFT)

        stamp_panel = tk.Frame(left_frame, bg=self.C_CANVAS_BG,
                               highlightthickness=1, highlightbackground=self.C_BORDER)
        stamp_panel.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.stamp_canvas = tk.Canvas(stamp_panel, bg=self.C_CANVAS_BG, highlightthickness=0)
        stamp_sb = tk.Scrollbar(stamp_panel, command=self.stamp_canvas.yview,
                                bg=self.C_BG, troughcolor=self.C_BG)
        self.stamp_canvas.configure(yscrollcommand=stamp_sb.set)
        stamp_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.stamp_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.stamp_inner_frame = tk.Frame(self.stamp_canvas, bg=self.C_CANVAS_BG)
        _stamp_win = self.stamp_canvas.create_window((0, 0), window=self.stamp_inner_frame, anchor="n")
        self.stamp_canvas.bind("<Configure>",
            lambda e: self.stamp_canvas.coords(_stamp_win, e.width // 2, 0))

        self._section_label(left_frame, "Neue Dateien").pack(anchor="center", padx=8, pady=(4, 2))

        file_panel = tk.Frame(left_frame, bg=self.C_BG,
                              highlightthickness=1, highlightbackground=self.C_BORDER)
        file_panel.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        self.file_listbox = tk.Listbox(
            file_panel, font=self.F_MONO,
            bg=self.C_BG, fg=self.C_TEXT,
            selectbackground=self.C_SELECTED, selectforeground=self.C_TEXT,
            activestyle="none", borderwidth=0, highlightthickness=0, relief=tk.FLAT)
        file_sb = tk.Scrollbar(file_panel, command=self.file_listbox.yview,
                               bg=self.C_BG, troughcolor=self.C_BG)
        self.file_listbox.configure(yscrollcommand=file_sb.set)
        file_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind('<Double-Button-1>', self.open_from_list)

        self._btn(left_frame, "Ausgewählte Datei öffnen",
                  command=self.open_from_list, style="primary_small").pack(fill=tk.X, padx=8, pady=(0, 8))

        # ── Rechte Seite ────────────────────────────────────────────────────
        right_frame = tk.Frame(main_container, bg=self.C_BG,
                              highlightthickness=0)
        main_container.add(right_frame, padx=0, pady=0)

        toolbar = tk.Frame(right_frame, bg=self.C_BG)
        toolbar.pack(fill=tk.X, padx=8, pady=8)

        self._btn(toolbar, "PDF öffnen", command=self.open_pdf, style="primary",
                  image=self._fa_icons["folder"], compound=tk.LEFT).pack(side=tk.LEFT, padx=(0, 4))
        self._btn(toolbar, "◀", command=self.prev_page,
                  font=("Segoe UI Symbol", 11)).pack(side=tk.LEFT, padx=2)
        self._btn(toolbar, "▶", command=self.next_page,
                  font=("Segoe UI Symbol", 11)).pack(side=tk.LEFT, padx=(2, 8))

        self.page_label = tk.Label(toolbar, text="–",
                                   bg=self.C_BG, fg=self.C_HINT, font=self.F_SMALL)
        self.page_label.pack(side=tk.LEFT, padx=4)

        self._btn(toolbar, "Zoom +", command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        self._btn(toolbar, "Zoom −", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        self._btn(toolbar, "Reset", command=self.zoom_reset).pack(side=tk.LEFT, padx=2)
        self.zoom_label = tk.Label(toolbar, text="100%", bg=self.C_BG, fg=self.C_HINT, font=self.F_SMALL)
        self.zoom_label.pack(side=tk.LEFT, padx=2)

        # Spacer: nimmt freien Platz zwischen Zoom-Label und Speichern-Button
        tk.Frame(toolbar, bg=self.C_BG).pack(side=tk.LEFT, expand=True, fill=tk.X)

        self._btn(toolbar, "Speichern", command=self.save_pdf, style="primary",
                  image=self._fa_icons["save"], compound=tk.LEFT).pack(side=tk.LEFT, padx=(4, 0))

        filename_bar = tk.Frame(right_frame, bg=self.C_WHITE, height=30,
                                highlightthickness=1, highlightbackground=self.C_BORDER)
        filename_bar.pack(fill=tk.X, padx=8, pady=(0, 4))
        filename_bar.pack_propagate(False)
        self.filename_label = tk.Label(filename_bar, text="Keine Datei geöffnet",
                                       bg=self.C_WHITE, fg=self.C_HINT,
                                       font=self.F_SMALL, anchor="w", padx=10)
        self.filename_label.pack(fill=tk.BOTH, expand=True)

        canvas_panel = tk.Frame(right_frame, bg=self.C_BORDER, highlightthickness=0)
        canvas_panel.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.pdf_canvas = tk.Canvas(canvas_panel, bg=self.C_CANVAS_BG, highlightthickness=0)
        h_sb = tk.Scrollbar(canvas_panel, orient=tk.HORIZONTAL,
                            command=self.pdf_canvas.xview,
                            bg=self.C_SURFACE, troughcolor=self.C_BG)
        v_sb = tk.Scrollbar(canvas_panel, orient=tk.VERTICAL,
                            command=self.pdf_canvas.yview,
                            bg=self.C_SURFACE, troughcolor=self.C_BG)
        self.pdf_canvas.configure(xscrollcommand=h_sb.set, yscrollcommand=v_sb.set)
        h_sb.pack(side=tk.BOTTOM, fill=tk.X)
        v_sb.pack(side=tk.RIGHT,  fill=tk.Y)
        self.pdf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pdf_canvas.bind('<Button-1>',   self.place_stamp)
        self.pdf_canvas.bind('<MouseWheel>', self.on_mousewheel)
        self.pdf_canvas.bind('<Button-4>',   self.on_mousewheel)
        self.pdf_canvas.bind('<Button-5>',   self.on_mousewheel)

        self.load_stamps()
    
    def load_stamps(self):
        """Stempel aus dem konfigurierten Ordner laden"""
        stamp_folder = self.get_stamp_folder()
        
        if not os.path.exists(stamp_folder):
            return
        
        self.stamps = []
        for file in os.listdir(stamp_folder):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                self.stamps.append(os.path.join(stamp_folder, file))
        
        # Stempel anzeigen
        for widget in self.stamp_inner_frame.winfo_children():
            widget.destroy()
        
        for i, stamp_path in enumerate(self.stamps):
            try:
                img = Image.open(stamp_path)
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)
                
                btn = tk.Button(self.stamp_inner_frame, image=photo,
                               command=lambda s=stamp_path: self.select_stamp(s),
                               relief=tk.FLAT, bd=0, bg=self.C_BG,
                               activebackground=self.C_SELECTED, cursor="hand2")
                btn.image = photo
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.C_SELECTED))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.C_BG))
                btn.grid(row=i//2, column=i%2, padx=6, pady=6)
            except:
                pass
        
        self.stamp_inner_frame.update_idletasks()
        self.stamp_canvas.configure(scrollregion=self.stamp_canvas.bbox("all"))
    
    def select_stamp(self, stamp_path):
        """Stempel auswählen und Vorschau anzeigen"""
        self.selected_stamp = stamp_path
        
        # Vorschau aktualisieren
        try:
            img = Image.open(stamp_path)
            img.thumbnail((200, 60))
            photo = ImageTk.PhotoImage(img)
            
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo  # Referenz behalten
        except:
            self.preview_label.configure(image="", text=f"Ausgewählt: {os.path.basename(stamp_path)}")
            self.preview_label.image = None
    
    def deselect_stamp(self):
        """Stempel-Auswahl aufheben"""
        self.selected_stamp = None
        self.preview_label.configure(image="", text="Kein Stempel ausgewählt", fg=self.C_HINT)
        self.preview_label.image = None
        
    def show_help(self):
        """Hilfe-Dialog – Inhalt wird aus help.md geladen und gerendert"""
        dlg = tk.Toplevel(self.root)
        dlg.title("Hilfe – PDF Stempel Tool")
        dlg.configure(bg=self.C_BG)
        dlg.resizable(True, True)
        dlg.grab_set()

        # Initiale Größe: 50 % der Bildschirmbreite, 75 % der Bildschirmhöhe
        self.root.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        w  = min(max(int(sw * 0.5), 480), 1200)
        h  = min(max(int(sh * 0.75), 400), 1000)
        rx = self.root.winfo_rootx() + self.root.winfo_width()  // 2 - w // 2
        ry = max(0, self.root.winfo_rooty() + self.root.winfo_height() // 2 - h // 2)
        dlg.geometry(f"{w}x{h}+{rx}+{ry}")
        dlg.minsize(400, 300)

        # Scrollbarer Bereich
        canvas = tk.Canvas(dlg, bg=self.C_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=self.C_BG)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mousewheel nur für diesen Dialog, Binding beim Schließen aufräumen
        def _on_wheel(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        wheel_id = canvas.bind_all("<MouseWheel>", _on_wheel)
        dlg.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        P = 20

        # Labels mit wraplength werden hier gesammelt und bei Resize aktualisiert
        wrap_labels = []  # (label, side_padding)

        def _on_canvas_resize(e):
            canvas.itemconfig(inner_id, width=e.width)
            for lbl, extra in wrap_labels:
                lbl.configure(wraplength=max(e.width - P * 2 - extra, 100))
        canvas.bind("<Configure>", _on_canvas_resize)

        def render_h1(text):
            tk.Label(inner, text=text, font=("Segoe UI", 13, "bold"),
                     bg=self.C_BG, fg=self.C_PRIMARY, anchor="w").pack(fill=tk.X, padx=P, pady=(18, 2))
            tk.Frame(inner, bg=self.C_PRIMARY, height=1).pack(fill=tk.X, padx=P, pady=(0, 6))

        def render_h2(text):
            tk.Label(inner, text=text, font=("Segoe UI", 10, "bold"),
                     bg=self.C_BG, fg=self.C_TEXT, anchor="w").pack(fill=tk.X, padx=P, pady=(10, 1))

        def render_p(text):
            lbl = tk.Label(inner, text=text, font=self.F_BODY,
                           bg=self.C_BG, fg=self.C_TEXT, anchor="w",
                           justify=tk.LEFT, wraplength=w - P * 2 - 20)
            lbl.pack(fill=tk.X, padx=P + 4)
            wrap_labels.append((lbl, 24))

        def render_code(text):
            tk.Label(inner, text=text, font=("Courier New", 9),
                     bg=self.C_WHITE, fg=self.C_TEXT, anchor="w",
                     relief=tk.FLAT, justify=tk.LEFT,
                     highlightthickness=1, highlightbackground=self.C_BORDER,
                     padx=8, pady=4).pack(fill=tk.X, padx=P + 4, pady=(2, 4))

        def render_listitem(num, text):
            row = tk.Frame(inner, bg=self.C_BG)
            row.pack(fill=tk.X, padx=P + 4, pady=2)
            tk.Label(row, text=str(num), font=("Segoe UI", 9, "bold"),
                     bg=self.C_PRIMARY, fg=self.C_WHITE,
                     width=2, anchor="center").pack(side=tk.LEFT, padx=(0, 8))
            lbl = tk.Label(row, text=text, font=self.F_BODY, bg=self.C_BG, fg=self.C_TEXT,
                           anchor="w", justify=tk.LEFT,
                           wraplength=w - P * 2 - 50)
            lbl.pack(side=tk.LEFT, fill=tk.X)
            wrap_labels.append((lbl, 54))

        # ── help.md laden und rendern ────────────────────────────────────────
        tk.Label(inner, text="PDF Stempel Tool – Hilfe", font=("Segoe UI", 15, "bold"),
                 bg=self.C_BG, fg=self.C_TEXT).pack(padx=P, pady=(18, 0), anchor="w")
        tk.Label(inner, text=f"Version {self.version}", font=self.F_BODY,
                 bg=self.C_BG, fg=self.C_HINT).pack(padx=P, anchor="w")

        help_path = self._resource_path("help.md")
        try:
            with open(help_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            render_p(f"Hilfedatei nicht gefunden:\n{help_path}")
            lines = []

        para_buf = []
        in_code  = False
        code_buf = []

        def flush_para():
            if para_buf:
                render_p(" ".join(para_buf))
                para_buf.clear()

        for line in lines:
            if line.startswith("```"):
                if in_code:
                    render_code("\n".join(code_buf))
                    code_buf.clear()
                    in_code = False
                else:
                    flush_para()
                    in_code = True
                continue

            if in_code:
                code_buf.append(line)
                continue

            if line.startswith("# "):
                flush_para()
                render_h1(line[2:])
            elif line.startswith("## "):
                flush_para()
                render_h2(line[3:])
            elif line.strip() == "":
                flush_para()
            else:
                # Nummerierte Liste: "1. text"
                import re
                m = re.match(r'^(\d+)\.\s+(.*)', line)
                if m:
                    flush_para()
                    render_listitem(m.group(1), m.group(2))
                else:
                    para_buf.append(line.strip())

        flush_para()
        tk.Frame(inner, bg=self.C_BG, height=16).pack()

        # ── Schließen-Button ────────────────────────────────────────────────
        tk.Frame(dlg, bg=self.C_BORDER, height=1).pack(fill=tk.X)
        btn_row = tk.Frame(dlg, bg=self.C_BG)
        btn_row.pack(pady=10, padx=20, anchor="e")
        self._btn(btn_row, "Schließen", command=dlg.destroy, style="primary").pack(side=tk.RIGHT)

    def show_info(self):
        self._msgbox("Info", f'Erstellt von: Jan Schmidt\nBei Fragen und Anregungen Email an: jan.schmidt2@zf.com\n\nPDF_Stempel_Tool v{self.version}', kind="info")
    
    def clear_all_stamps(self):
        """Alle Stempel von der aktuellen PDF entfernen"""
        if not self.pdf_document or not self.current_pdf:
            self._msgbox("Warnung", "Keine PDF geöffnet.", kind="warning")
            return

        # Bestätigungsdialog
        result = self._ask_yesno(
            "Alle Stempel entfernen",
            "Möchten Sie wirklich alle Stempel von dieser PDF entfernen?\n\nDie Original-PDF wird neu geladen."
        )

        if result:
            try:
                # PDF neu laden (ohne Stempel)
                temp_path = self.current_pdf
                current_page_num = self.current_page
                self.pdf_document.close()
                self.pdf_document = fitz.open(temp_path)
                self.current_page = current_page_num
                self.stamped_pages = set()
                self.display_all_pages()
                self._msgbox("Erfolg", "Alle Stempel wurden entfernt.", kind="info")
            except Exception as e:
                self._msgbox("Fehler", f"Fehler beim Entfernen der Stempel:\n{str(e)}", kind="error")
    
    def watch_folder(self):
        """Überwachten Ordner auf neue PDF-Dateien prüfen (inkl. Unterordner)"""
        self.scan_folder_now()
        self.root.after(2000, self.watch_folder)  # Alle 2 Sekunden prüfen
    
    def matches_programm_list(self, filename, config_key="programm_list", empty_result=True):
        """Prüft ob Dateiname alle 3 Teile mindestens eines Programmlisten-Eintrags enthält"""
        active_entries = [e.strip() for e in self.config.get(config_key, []) if e.strip()]
        if not active_entries:
            return empty_result

        filename_lower = filename.lower()
        for entry in active_entries:
            parts = entry.split(';')
            if len(parts) >= 3:
                p1, p2, p3 = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if p1 and p2 and p3 and (
                    p1.lower() in filename_lower and
                    p2.lower() in filename_lower and
                    p3.lower() in filename_lower
                ):
                    return True
        return False
    
    def scan_folder_now(self):
        """Führt den Ordner-Scan sofort aus"""
        open_path     = self.config.get("open_path", "")
        oqis_ein_path = self.config.get("oqis_ein_path", "")
        stabi_path    = self.config.get("stabi_path", "")
        sonstige_path = os.path.join(open_path, "Eingang_Sonstige")
        move_sonstige = self.config.get("auto_move_sonstige", False)

        if os.path.exists(open_path):
            try:
                # Alle PDF-Dateien inkl. Unterordner finden (Archiv-Ordner ausschließen)
                archive_name   = os.path.normpath(os.path.join(open_path, "Archiv"))
                sonstige_name  = os.path.normpath(sonstige_path)
                all_pdf_files = []
                for root, dirs, files in os.walk(open_path):
                    norm_root = os.path.normpath(root)
                    if norm_root in (archive_name, sonstige_name):
                        dirs.clear()
                        continue
                    for file in files:
                        if file.lower().endswith('.pdf'):
                            full_path = os.path.normpath(os.path.join(root, file))
                            rel_path = os.path.relpath(full_path, open_path)
                            mtime = os.path.getmtime(full_path)

                            # Im einfachen Modus alle PDFs anzeigen, sonst Programmliste prüfen
                            if self.matches_programm_list(file, config_key="oqisprogramm_list", empty_result=False):
                                dfq_file, dfq_error = self.find_dfq_file(file, config_key="oqisprogramm_list")
                                if dfq_file:
                                    shutil.move(full_path, os.path.join(stabi_path, file))
                                    shutil.move(dfq_file, os.path.join(oqis_ein_path, os.path.basename(dfq_file)))
                            elif self.config.get("simple_stamp_mode", False) or self.matches_programm_list(file):
                                all_pdf_files.append((rel_path, mtime, full_path))
                            elif move_sonstige:
                                os.makedirs(sonstige_path, exist_ok=True)
                                dfq = self.find_dfq_by_timestamp(file)
                                shutil.move(full_path, os.path.join(sonstige_path, file))
                                if dfq:
                                    shutil.move(dfq, os.path.join(sonstige_path, os.path.basename(dfq)))

                # Nach Änderungszeit sortieren (neueste zuerst)
                all_pdf_files.sort(key=lambda x: x[1], reverse=True)

                self.watch_files = [f[0] for f in all_pdf_files]
                self.update_file_list_display(all_pdf_files)

            except Exception as e:
                pass  # Fehler ignorieren
    
    def update_file_list(self):
        """Liste manuell aktualisieren (z.B. bei Checkbox-Änderung)"""
        self.watch_files = []  # Erzwingt Update beim nächsten Scan
        # Sofort neu scannen statt auf Timer zu warten
        self.root.after(100, self.scan_folder_now)
    
    def update_file_list_display(self, all_pdf_files):
        """Aktualisiert die Anzeige der Dateiliste"""
        from datetime import datetime
        
        self.file_listbox.delete(0, tk.END)
        self.file_paths = []  # Index-basierte Liste zurücksetzen

        for rel_path, mtime, full_path in all_pdf_files:
            filename = os.path.basename(rel_path)
            time_str = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")

            max_filename_len = 30
            if len(filename) > max_filename_len:
                display_filename = filename[:max_filename_len-3] + "..."
            else:
                display_filename = filename

            spaces = max(1, 35 - len(display_filename))
            display_text = f"  {display_filename}{' ' * spaces}[{time_str}]"
            self.file_listbox.insert(tk.END, display_text)
            self.file_paths.append(full_path)
    
    def open_from_list(self, event=None):
        """PDF aus der Dateiliste öffnen"""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        filepath = self.file_paths[idx] if idx < len(self.file_paths) else None

        if filepath and os.path.exists(filepath):
            self.open_pdf(filepath)
        else:
            self._msgbox("Fehler", "Datei nicht gefunden", kind="error")
    
    def open_pdf(self, filepath=None):
        """PDF-Datei öffnen"""
        if not filepath:
            filepath = filedialog.askopenfilename(
                initialdir=self.config.get("open_path", ""),
                title="PDF öffnen",
                filetypes=[("PDF-Dateien", "*.pdf")]
            )
        
        if not filepath:
            return
        
        try:
            self.current_pdf = filepath
            self.pdf_document = fitz.open(filepath)
            self.current_page = 0
            self.stamped_pages = set()

            filename = os.path.basename(filepath)
            self.filename_label.config(text=filename, fg=self.C_TEXT)

            self.display_all_pages()
        except Exception as e:
            self._msgbox("Fehler", f"PDF konnte nicht geöffnet werden:\n{str(e)}", kind="error")
    
    def display_all_pages(self):
        """Alle PDF-Seiten vertikal gestapelt im Canvas anzeigen"""
        if not self.pdf_document:
            return

        self.pdf_canvas.delete("all")
        self.page_positions = []
        self.page_photo_refs = []

        gap = 10
        current_y = gap
        max_width = 0

        for page_num in range(len(self.pdf_document)):
            page = self.pdf_document[page_num]
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat)

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            self.page_photo_refs.append(photo)

            self.pdf_canvas.create_image(gap, current_y, anchor=tk.NW, image=photo)
            self.page_positions.append((page_num, current_y, current_y + pix.height))
            current_y += pix.height + gap
            max_width = max(max_width, pix.width)

        self.pdf_canvas.configure(scrollregion=(0, 0, max_width + 2 * gap, current_y))
        self.page_label.config(text=f"{len(self.pdf_document)} Seite(n)")

    def scroll_to_page(self, page_num):
        """Canvas zu einer bestimmten Seite scrollen"""
        if not self.page_positions or page_num >= len(self.page_positions):
            return
        _, y_start, _ = self.page_positions[page_num]
        scrollregion = self.pdf_canvas.cget("scrollregion")
        if scrollregion:
            total_height = float(scrollregion.split()[3])
            if total_height > 0:
                self.pdf_canvas.yview_moveto(y_start / total_height)
    
    def prev_page(self):
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.scroll_to_page(self.current_page)

    def next_page(self):
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.scroll_to_page(self.current_page)

    def zoom_in(self):
        self.zoom = min(self.zoom + 0.2, 3.0)
        self.display_all_pages()
        self.zoom_label.config(text=f"{round(self.zoom * 100)}%")

    def zoom_out(self):
        self.zoom = max(self.zoom - 0.2, 0.5)
        self.display_all_pages()
        self.zoom_label.config(text=f"{round(self.zoom * 100)}%")

    def zoom_reset(self):
        self.zoom = 1.0
        self.display_all_pages()
        self.zoom_label.config(text=f"{round(self.zoom * 100)}%")
    
    def place_stamp(self, event):
        """Stempel an Mausposition platzieren (zentriert)"""
        if not self.selected_stamp or not self.pdf_document:
            self._msgbox("Warnung", "Bitte wählen Sie zuerst einen Stempel und öffnen Sie eine PDF.", kind="warning")
            return

        canvas_x = self.pdf_canvas.canvasx(event.x)
        canvas_y = self.pdf_canvas.canvasy(event.y)

        # Ermitteln auf welcher Seite der Klick landete
        gap = 10
        clicked_page = None
        page_y_start = 0
        for page_num, y_start, y_end in self.page_positions:
            if y_start <= canvas_y <= y_end:
                clicked_page = page_num
                page_y_start = y_start
                break

        if clicked_page is None:
            return  # Klick im Zwischenraum oder außerhalb

        self.current_page = clicked_page
        page = self.pdf_document[clicked_page]

        # Canvas-Koordinaten in PDF-Koordinaten umrechnen
        pdf_x = (canvas_x - gap) / self.zoom
        pdf_y = (canvas_y - page_y_start) / self.zoom

        try:
            stamp_img = Image.open(self.selected_stamp)

            stamp_height = 40
            stamp_width = stamp_img.width * (stamp_height / stamp_img.height)

            centered_x = pdf_x - (stamp_width / 2)
            centered_y = pdf_y - (stamp_height / 2)

            rect = fitz.Rect(centered_x, centered_y, centered_x + stamp_width, centered_y + stamp_height)

            img_byte_arr = io.BytesIO()
            stamp_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            page.insert_image(rect, stream=img_byte_arr)
            self.stamped_pages.add(clicked_page)
            self.display_all_pages()

        except Exception as e:
            self._msgbox("Fehler", f"Stempel konnte nicht platziert werden:\n{str(e)}", kind="error")
    
    def check_all_pages_stamped(self):
        """Gibt True zurück wenn alle Seiten mindestens einen Stempel haben"""
        if not self.pdf_document:
            return False
        return all(i in self.stamped_pages for i in range(len(self.pdf_document)))

    def get_matching_programm_entry(self, filename, config_key="programm_list"):
        """Gibt die 3 Teile (p1,p2,p3) des ersten passenden Programmlisten-Eintrags zurück"""
        programm_list = self.config.get(config_key, [])
        filename_lower = filename.lower()
        for entry in programm_list:
            if not entry.strip():
                continue
            parts = entry.split(';')
            if len(parts) >= 3:
                p1, p2, p3 = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if p1 and p2 and p3 and (
                    p1.lower() in filename_lower and
                    p2.lower() in filename_lower and
                    p3.lower() in filename_lower
                ):
                    return p1, p2, p3
        return None

    def extract_timestamp(self, filename):
      """Extrahiert einen Zeitstempel (YYYYMMDDHHmmss) aus dem Dateinamen"""
      import re
    
      # 14-stellig: YYYYMMDDHHmmss
      match = re.search(r'\d{14}', filename)
      if match:
          return match.group(0)
    
      # Mit Unterstrich: YYYYMMDD_HHmmss
      match = re.search(r'(\d{8})_(\d{6})', filename)
      if match:
          return match.group(1) + match.group(2)
    
      return None

    def find_dfq_by_timestamp(self, pdf_filename):
        """Sucht eine DFQ-Datei nur über den Zeitstempel – ohne Programmlisten-Prüfung."""
        ts = self.extract_timestamp(pdf_filename)
        if not ts:
            return None
        ts_variants = {ts}
        if len(ts) == 14:
            ts_variants.add(ts[:8] + "_" + ts[8:])
        dfq_path = (self.config.get("open_path", "")
                    if self.config.get("dfq_same_as_open", True)
                    else self.config.get("dfq_path", ""))
        if not os.path.exists(dfq_path):
            return None
        for root, dirs, files in os.walk(dfq_path):
            for f in files:
                if f.lower().endswith(".dfq") and any(v in f for v in ts_variants):
                    return os.path.join(root, f)
        return None

    def find_dfq_file(self, pdf_filename, config_key="programm_list"):
        """Sucht passende DFQ-Datei (gleiche Werkstück/Mblatt/Zustand-Teile + gleicher Zeitstempel)"""
        if self.config.get("dfq_same_as_open", True):
            dfq_path = self.config.get("open_path", "")
        else:
            dfq_path = self.config.get("dfq_path", "")

        if not os.path.exists(dfq_path):
            return None, f"DFQ-Ordner nicht gefunden:\n{dfq_path}"

        entry = self.get_matching_programm_entry(pdf_filename, config_key=config_key)
        if not entry:
            return None, "Kein passender Programmlisten-Eintrag für die PDF gefunden."

        p1, p2, p3 = entry
        timestamp = self.extract_timestamp(pdf_filename)
        if not timestamp:
            return None, "Kein Zeitstempel (14 Ziffern) im PDF-Dateinamen gefunden."

        # Beide Zeitstempel-Varianten abdecken: 20260614110800 und 20260614_110800
        ts_variants = {timestamp}
        if len(timestamp) == 14:
            ts_variants.add(timestamp[:8] + "_" + timestamp[8:])

        for root, dirs, files in os.walk(dfq_path):
            for file in files:
                if not file.lower().endswith('.dfq'):
                    continue
                file_lower = file.lower()
                if (p1.lower() in file_lower and
                    p2.lower() in file_lower and
                    p3.lower() in file_lower and
                    any(ts in file for ts in ts_variants)):
                    return os.path.join(root, file), None

        return None, (
            f"Keine passende DFQ-Datei gefunden.\n"
            f"Gesucht: Zeitstempel {timestamp}\n"
            f"Teile: {p1} | {p2} | {p3}"
        )

    def cleanup_archive(self, archive_path):
        """Löscht Dateien im Archiv-Ordner die älter als 7 Tage sind"""
        if not os.path.exists(archive_path):
            return
        limit = 7 * 24 * 60 * 60
        now = time.time()
        for file in os.listdir(archive_path):
            full = os.path.join(archive_path, file)
            if os.path.isfile(full) and now - os.path.getmtime(full) > limit:
                try:
                    os.remove(full)
                except Exception:
                    pass

    def save_pdf(self):
        """Gestempelte PDF speichern – je nach Modus mit oder ohne DFQ/Archiv"""
        if self.config.get("simple_stamp_mode", False):
            self.save_pdf_simple()
            return

        self.cleanup_old_files()
        if not self.pdf_document:
            self._msgbox("Warnung", "Keine PDF geöffnet.", kind="warning")
            return

        # Alle Seiten gestempelt?
        if not self.check_all_pages_stamped():
            missing = [i + 1 for i in range(len(self.pdf_document)) if i not in self.stamped_pages]
            self._msgbox(
                "Fehlende Stempel",
                f"Nicht alle Seiten haben einen Stempel!\nFehlend auf Seite(n): {', '.join(map(str, missing))}",
                kind="error"
            )
            return

        # Passende DFQ-Datei suchen
        pdf_filename = os.path.basename(self.current_pdf)
        dfq_file, dfq_error = self.find_dfq_file(pdf_filename)
        if not dfq_file:
            self._msgbox("DFQ-Datei nicht gefunden", dfq_error, kind="error")
            return

        save_path = self.config.get("save_path", "")
        dfq_out = self.config.get("dfq_out", "")
        open_path = os.path.normpath(self.config.get("open_path", ""))
        archive_path = os.path.join(open_path, "Archiv")

        # Ausgabedateiname: nur umbenennen wenn Ausgabe == Öffnungsordner
        name, ext = os.path.splitext(pdf_filename)
        if os.path.normpath(save_path) == open_path:
            out_pdf_name = f"{name}_gestempelt{ext}"
        else:
            out_pdf_name = pdf_filename

        out_pdf_path = os.path.join(save_path, out_pdf_name)
        out_dfq_path = os.path.join(dfq_out, os.path.basename(dfq_file))

        try:
            os.makedirs(save_path, exist_ok=True)
            os.makedirs(archive_path, exist_ok=True)

            # Gestempelte PDF in Ausgabeordner speichern
            self.pdf_document.save(out_pdf_path)

            # DFQ in Ausgabeordner kopieren
            shutil.copy2(dfq_file, out_dfq_path)

            # Fitz-Dokument schließen bevor Original verschoben wird (Windows-Dateisperre)
            original_pdf_path = self.current_pdf
            self.pdf_document.close()
            self.pdf_document = None

            # Originale ins Archiv verschieben
            shutil.move(original_pdf_path, os.path.join(archive_path, os.path.basename(original_pdf_path)))
            shutil.move(dfq_file, os.path.join(archive_path, os.path.basename(dfq_file)))

            # Archiv bereinigen (> 7 Tage)
            self.cleanup_archive(archive_path)

            # Als gestempelt markieren
            

            self.filename_label.config(text=f"Gespeichert: {out_pdf_name}", fg=self.C_PRIMARY)
            self.close_pdf()

        except Exception as e:
            self._msgbox("Fehler", f"Speichern fehlgeschlagen:\n{str(e)}", kind="error")
    
    def save_pdf_simple(self):
        """Einfacher Stempel-Modus: PDF speichern ohne DFQ-Suche und ohne Archivierung"""
        if not self.pdf_document:
            self._msgbox("Warnung", "Keine PDF geöffnet.", kind="warning")
            return

        pdf_filename = os.path.basename(self.current_pdf)
        save_path = self.config.get("save_path", "")
        open_path = os.path.normpath(self.config.get("open_path", ""))

        name, ext = os.path.splitext(pdf_filename)
        if os.path.normpath(save_path) == open_path:
            default_name = f"{name}_gestempelt{ext}"
        else:
            default_name = pdf_filename

        if self.config.get("auto_save", False):
            out_path = os.path.join(save_path, default_name)
        else:
            out_path = filedialog.asksaveasfilename(
                initialdir=save_path,
                initialfile=default_name,
                defaultextension=".pdf",
                filetypes=[("PDF Dateien", "*.pdf")],
                title="Gestempelte PDF speichern"
            )
            if not out_path:
                return

        try:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            self.pdf_document.save(out_path)
            self.filename_label.config(text=f"Gespeichert: {os.path.basename(out_path)}", fg=self.C_PRIMARY)
            self.close_pdf()
        except Exception as e:
            self._msgbox("Fehler", f"Speichern fehlgeschlagen:\n{str(e)}", kind="error")

    def show_settings(self):
        old_open_path = self.config.get("open_path", "")

        dlg = tk.Toplevel(self.root)
        dlg.title("Einstellungen")
        dlg.configure(bg=self.C_BG)
        dlg.resizable(True, True)
        dlg.grab_set()
        w, h = self.s(760), self.s(580)
        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width()  // 2 - w // 2
        ry = self.root.winfo_rooty() + self.root.winfo_height() // 2 - h // 2
        dlg.geometry(f"{w}x{h}+{rx}+{ry}")
        dlg.minsize(self.s(560), self.s(420))

        # ── Body: Sidebar + Inhalt ───────────────────────────────────────────
        body = tk.Frame(dlg, bg=self.C_BG)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(body, bg=self.C_WHITE, width=self.s(150))
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Frame(body, bg=self.C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        content_host = tk.Frame(body, bg=self.C_BG)
        content_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sections = {}
        nav_btns = {}
        active_sec = [None]

        def show_section(name):
            if active_sec[0] and active_sec[0] in sections:
                sections[active_sec[0]].pack_forget()
                nav_btns[active_sec[0]].config(bg=self.C_WHITE, font=self.F_BODY)
            active_sec[0] = name
            sections[name].pack(fill=tk.BOTH, expand=True)
            nav_btns[name].config(bg=self.C_SELECTED,
                                   font=(self.F_BODY[0], self.F_BODY[1], "bold"))

        for nav_lbl in ["Pfade", "Programme", "Optionen"]:
            sections[nav_lbl] = tk.Frame(content_host, bg=self.C_BG)
            b = tk.Button(sidebar, text=nav_lbl, font=self.F_BODY,
                          bg=self.C_WHITE, fg=self.C_TEXT,
                          relief=tk.FLAT, bd=0,
                          padx=self.s(14), pady=self.s(10),
                          anchor="w", cursor="hand2",
                          command=lambda n=nav_lbl: show_section(n),
                          activebackground=self.C_SELECTED,
                          activeforeground=self.C_TEXT,
                          highlightthickness=0)
            b.pack(fill=tk.X)
            nav_btns[nav_lbl] = b

        # ── Pfade ────────────────────────────────────────────────────────────
        paths = {k: [self.config.get(k, "")]
                 for k in ["open_path", "save_path", "dfq_path",
                            "dfq_out", "stabi_path", "oqis_ein_path"]}
        dfq_same_var = tk.BooleanVar(value=self.config.get("dfq_same_as_open", True))

        pfade_outer = sections["Pfade"]
        pfade_cv = tk.Canvas(pfade_outer, bg=self.C_BG, highlightthickness=0)
        pfade_sb = tk.Scrollbar(pfade_outer, orient=tk.VERTICAL, command=pfade_cv.yview)
        pfade_cv.configure(yscrollcommand=pfade_sb.set)
        pfade_sb.pack(side=tk.RIGHT, fill=tk.Y)
        pfade_cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pfade_f = tk.Frame(pfade_cv, bg=self.C_BG)
        pfade_win = pfade_cv.create_window((0, 0), window=pfade_f, anchor="nw")
        pfade_f.bind("<Configure>",
                     lambda e: pfade_cv.configure(scrollregion=pfade_cv.bbox("all")))
        pfade_cv.bind("<Configure>",
                      lambda e: pfade_cv.itemconfig(pfade_win, width=e.width))
        pfade_cv.bind("<MouseWheel>",
                      lambda e: pfade_cv.yview_scroll(int(-1 * e.delta / 120), "units"))
        pfade_f.bind("<MouseWheel>",
                     lambda e: pfade_cv.yview_scroll(int(-1 * e.delta / 120), "units"))

        p = tk.Frame(pfade_f, bg=self.C_BG)
        p.pack(fill=tk.X, padx=self.s(20), pady=self.s(16))

        def _info_tip(parent, text):
            lbl = tk.Label(parent, text=" ⓘ", font=self.F_SMALL,
                           bg=parent["bg"], fg=self.C_PRIMARY, cursor="hand2")
            _tip = [None]

            def _show(e):
                if _tip[0]:
                    return
                t = tk.Toplevel(dlg)
                t.overrideredirect(True)
                t.attributes("-topmost", True)
                t.configure(bg=self.C_TEXT)
                tk.Label(t, text=text, font=self.F_SMALL,
                         bg=self.C_TEXT, fg=self.C_WHITE,
                         padx=self.s(10), pady=self.s(6),
                         wraplength=self.s(280), justify="left").pack()
                t.update_idletasks()
                x = e.widget.winfo_rootx()
                y = e.widget.winfo_rooty() + e.widget.winfo_height() + 4
                if x + t.winfo_width() > t.winfo_screenwidth():
                    x = t.winfo_screenwidth() - t.winfo_width() - 8
                t.geometry(f"+{x}+{y}")
                _tip[0] = t

            def _hide(e):
                if _tip[0]:
                    _tip[0].destroy()
                    _tip[0] = None

            lbl.bind("<Enter>", _show)
            lbl.bind("<Leave>", _hide)
            return lbl

        def _path_row(parent, label, key, tooltip=None):
            hdr = tk.Frame(parent, bg=self.C_BG)
            hdr.pack(fill=tk.X, pady=(self.s(8), 2))
            tk.Label(hdr, text=label, font=self.F_BODY,
                     bg=self.C_BG, fg=self.C_TEXT,
                     anchor="w").pack(side=tk.LEFT)
            if tooltip:
                _info_tip(hdr, tooltip).pack(side=tk.LEFT)
            row = tk.Frame(parent, bg=self.C_BG)
            row.pack(fill=tk.X)
            cur = paths[key][0]
            border = tk.Frame(row, bg=self.C_WHITE,
                              highlightthickness=1, highlightbackground=self.C_BORDER)
            border.pack(side=tk.LEFT, fill=tk.X, expand=True)
            lbl = tk.Label(border, text=cur or "(nicht festgelegt)", anchor="w",
                           bg=self.C_WHITE,
                           fg=self.C_TEXT if cur else self.C_HINT,
                           font=self.F_SMALL, padx=6, pady=5)
            lbl.pack(fill=tk.X)

            def choose(k=key, l=lbl):
                pp = filedialog.askdirectory(title=f"{label} wählen")
                if pp:
                    paths[k][0] = pp
                    l.config(text=pp, fg=self.C_TEXT)

            self._btn(row, "Ordner wählen", command=choose,
                      style="secondary").pack(side=tk.LEFT, padx=(self.s(8), 0))
            return lbl

        _path_row(p, "PDF Öffnungspfad", "open_path",
                  tooltip="Der Ordner, den das Programm auf neue PDFs überwacht. Alle PDFs in diesem Ordner (und Unterordnern) erscheinen in der Liste.")
        _path_row(p, "PDF Speicherpfad", "save_path",
                  tooltip="Wohin die gestempelte PDF nach dem Speichern kopiert wird.")
        _path_row(p, "DFQ Ausgang", "dfq_out",
                  tooltip="Wohin die DFQ-Datei nach dem Speichern kopiert wird (falls abweichend vom normalen Speicherpfad).")
        _path_row(p, "Stabilitätsprüfung Speicherordner", "stabi_path",
                  tooltip="Zielordner für PDFs von Programmen aus der O-Qis-Programmliste. Diese werden bei 'Scan Now' automatisch hierher verschoben.")
        _path_row(p, "O-Qis Eingangsordner", "oqis_ein_path",
                  tooltip="Zielordner für DFQ-Dateien von Programmen aus der O-Qis-Programmliste.")

        tk.Frame(p, bg=self.C_BORDER, height=1).pack(fill=tk.X, pady=(self.s(14), self.s(6)))
        dfq_hdr = tk.Frame(p, bg=self.C_BG)
        dfq_hdr.pack(fill=tk.X)
        tk.Label(dfq_hdr, text="DFQ Eingang", font=self.F_BODY, bg=self.C_BG,
                 fg=self.C_TEXT, anchor="w").pack(side=tk.LEFT)
        _info_tip(dfq_hdr, "Ordner, in dem nach passenden DFQ-Messdateien gesucht wird. PDF und DFQ werden über den gemeinsamen Zeitstempel im Dateinamen zugeordnet.").pack(side=tk.LEFT)
        dfq_cb_row = tk.Frame(p, bg=self.C_BG)
        dfq_cb_row.pack(fill=tk.X, pady=(4, 4))
        tk.Checkbutton(dfq_cb_row, text="Gleicher Ordner wie PDF Öffnungspfad",
                       variable=dfq_same_var, command=lambda: _update_dfq_ui(),
                       bg=self.C_BG, fg=self.C_TEXT, font=self.F_SMALL,
                       activebackground=self.C_BG, activeforeground=self.C_TEXT,
                       selectcolor=self.C_WHITE, cursor="hand2",
                       highlightthickness=0).pack(side=tk.LEFT)
        _info_tip(dfq_cb_row, "Wenn aktiv, wird im selben Ordner wie die PDFs nach DFQ-Dateien gesucht. Sonst kann ein separater Ordner angegeben werden.").pack(side=tk.LEFT)

        dfq_row = tk.Frame(p, bg=self.C_BG)
        dfq_row.pack(fill=tk.X)
        dfq_border = tk.Frame(dfq_row, bg=self.C_WHITE,
                              highlightthickness=1, highlightbackground=self.C_BORDER)
        dfq_border.pack(side=tk.LEFT, fill=tk.X, expand=True)
        cur_dfq = paths["dfq_path"][0]
        dfq_lbl = tk.Label(dfq_border, text=cur_dfq or "(nicht festgelegt)", anchor="w",
                           bg=self.C_WHITE, fg=self.C_TEXT if cur_dfq else self.C_HINT,
                           font=self.F_SMALL, padx=6, pady=5)
        dfq_lbl.pack(fill=tk.X)

        def _choose_dfq():
            pp = filedialog.askdirectory(title="DFQ Eingang wählen")
            if pp:
                paths["dfq_path"][0] = pp
                dfq_lbl.config(text=pp, fg=self.C_TEXT)
                dfq_border.config(bg=self.C_WHITE)

        dfq_btn = self._btn(dfq_row, "Ordner wählen", command=_choose_dfq, style="secondary")
        dfq_btn.pack(side=tk.LEFT, padx=(self.s(8), 0))

        def _update_dfq_ui():
            if dfq_same_var.get():
                dfq_lbl.config(fg=self.C_HINT, bg=self.C_SURFACE)
                dfq_border.config(bg=self.C_SURFACE)
                dfq_btn.config(state=tk.DISABLED, cursor="arrow")
            else:
                dfq_lbl.config(fg=self.C_TEXT if paths["dfq_path"][0] else self.C_HINT,
                               bg=self.C_WHITE)
                dfq_border.config(bg=self.C_WHITE)
                dfq_btn.config(state=tk.NORMAL, cursor="hand2")

        _update_dfq_ui()

        # ── Programme ────────────────────────────────────────────────────────
        prog_outer = sections["Programme"]
        prog_cv = tk.Canvas(prog_outer, bg=self.C_BG, highlightthickness=0)
        prog_sb = tk.Scrollbar(prog_outer, orient=tk.VERTICAL, command=prog_cv.yview)
        prog_cv.configure(yscrollcommand=prog_sb.set)
        prog_sb.pack(side=tk.RIGHT, fill=tk.Y)
        prog_cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        prog_f = tk.Frame(prog_cv, bg=self.C_BG)
        prog_win = prog_cv.create_window((0, 0), window=prog_f, anchor="nw")
        prog_f.bind("<Configure>",
                    lambda e: prog_cv.configure(scrollregion=prog_cv.bbox("all")))
        prog_cv.bind("<Configure>",
                     lambda e: prog_cv.itemconfig(prog_win, width=e.width))
        prog_cv.bind("<MouseWheel>",
                     lambda e: prog_cv.yview_scroll(int(-1 * e.delta / 120), "units"))

        prog_c = tk.Frame(prog_f, bg=self.C_BG)
        prog_c.pack(fill=tk.X, padx=self.s(20), pady=self.s(16))

        prog_editors = {}

        def _prog_editor(parent, config_key, title, tooltip=None):
            hdr = tk.Frame(parent, bg=self.C_BG)
            hdr.pack(fill=tk.X)
            self._section_label(hdr, title).pack(side=tk.LEFT)
            if tooltip:
                _info_tip(hdr, tooltip).pack(side=tk.LEFT)
            tk.Label(parent,
                     text="Format: Werkstücknummer;MBlattnummer;Zustand  (ein Eintrag pro Zeile)",
                     font=self.F_SMALL, bg=self.C_BG, fg=self.C_HINT,
                     anchor="w").pack(fill=tk.X, pady=(2, 8))

            text_border = tk.Frame(parent, bg=self.C_WHITE,
                                   highlightthickness=1, highlightbackground=self.C_BORDER)
            text_border.pack(fill=tk.X)

            linenum = tk.Text(text_border, bg=self.C_BG, fg=self.C_HINT,
                              font=self.F_MONO, relief=tk.FLAT, width=3,
                              padx=4, pady=6, state=tk.DISABLED,
                              cursor="arrow", highlightthickness=0, takefocus=False)
            linenum.pack(side=tk.LEFT, fill=tk.Y)
            linenum.tag_configure("invalid_num", foreground=self.C_DANGER_FG,
                                  font=(self.F_MONO[0], self.F_MONO[1], "bold"))
            tk.Frame(text_border, bg=self.C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

            vsb = tk.Scrollbar(text_border, orient=tk.VERTICAL)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

            tw = tk.Text(text_border, bg=self.C_WHITE, fg=self.C_TEXT,
                         font=self.F_MONO, relief=tk.FLAT,
                         insertbackground=self.C_TEXT,
                         selectbackground=self.C_SELECTED, selectforeground=self.C_TEXT,
                         width=55, height=10, padx=6, pady=6,
                         yscrollcommand=lambda f, l: (vsb.set(f, l),
                                                      linenum.yview_moveto(f)))
            vsb.configure(command=tw.yview)
            tw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tw.tag_configure("invalid_line",
                             background=self.C_DANGER_BG, foreground=self.C_DANGER_FG)
            tw.insert("1.0", "\n".join(self.config.get(config_key, [])))

            err = tk.Label(parent, text="", font=self.F_SMALL,
                           bg=self.C_BG, fg=self.C_DANGER_FG, anchor="w")
            err.pack(fill=tk.X, pady=(4, 0))

            def upd_nums(invalid_lines=None):
                n = int(tw.index("end-1c").split(".")[0])
                linenum.config(state=tk.NORMAL)
                linenum.delete("1.0", tk.END)
                for i in range(1, n + 1):
                    linenum.insert(tk.END, f"{i:>2}\n")
                    if invalid_lines and i in invalid_lines:
                        linenum.tag_add("invalid_num", f"{i}.0", f"{i}.end")
                linenum.config(state=tk.DISABLED)
                linenum.yview_moveto(tw.yview()[0])

            tw.bind("<KeyRelease>", lambda *_: (
                tw.tag_remove("invalid_line", "1.0", tk.END),
                err.config(text=""),
                upd_nums()
            ))
            linenum.bind("<MouseWheel>",
                         lambda e: tw.event_generate("<MouseWheel>", delta=e.delta))
            upd_nums()
            prog_editors[config_key] = (tw, err, upd_nums)

        _prog_editor(prog_c, "programm_list", "Programme zum Stempeln",
                     tooltip="PDFs, deren Dateiname alle drei Teile (Werkstück;Mblatt;Zustand) enthält, werden in der Hauptliste angezeigt. Ist die Liste leer, werden alle PDFs im Öffnungsordner angezeigt.")
        tk.Frame(prog_c, bg=self.C_BORDER, height=1).pack(fill=tk.X, pady=self.s(16))
        _prog_editor(prog_c, "oqisprogramm_list", "Programme für O-Qis",
                     tooltip="PDFs dieser Programme werden bei 'Scan Now' automatisch ohne Stempel-Vorgang verschoben: PDF → Stabilitätsprüfung-Ordner, DFQ → O-Qis-Eingangsordner.")

        # ── Optionen ─────────────────────────────────────────────────────────
        opt_f = tk.Frame(sections["Optionen"], bg=self.C_BG)
        opt_f.pack(fill=tk.X, padx=self.s(20), pady=self.s(16))

        auto_save_v    = tk.BooleanVar(value=self.config.get("auto_save",           False))
        auto_delete_v  = tk.BooleanVar(value=self.config.get("auto_delete",         False))
        move_sonstige_v= tk.BooleanVar(value=self.config.get("auto_move_sonstige",  False))
        simple_v       = tk.BooleanVar(value=self.config.get("simple_stamp_mode",   False))

        def _cb(parent, text, var, hint=None, command=None, tooltip=None):
            row = tk.Frame(parent, bg=self.C_BG)
            row.pack(fill=tk.X, pady=(self.s(4), 0))
            tk.Checkbutton(row, text=text, variable=var, command=command,
                           bg=self.C_BG, fg=self.C_TEXT, font=self.F_BODY,
                           activebackground=self.C_BG, activeforeground=self.C_TEXT,
                           selectcolor=self.C_WHITE, cursor="hand2",
                           highlightthickness=0).pack(side=tk.LEFT)
            if tooltip:
                _info_tip(row, tooltip).pack(side=tk.LEFT)
            if hint:
                tk.Label(parent, text=hint, font=self.F_SMALL, bg=self.C_BG,
                         fg=self.C_HINT, anchor="w").pack(
                    fill=tk.X, padx=(self.s(22), 0), pady=(0, self.s(4)))

        self._section_label(opt_f, "Verhalten").pack(fill=tk.X, pady=(0, self.s(4)))
        _cb(opt_f, "Automatisch speichern (ohne Dialog)", auto_save_v,
            tooltip="PDFs werden nach dem Stempeln direkt in den Speicherpfad gespeichert, ohne einen Datei-Dialog zu öffnen.")
        _cb(opt_f, "Alte Protokolle automatisch löschen", auto_delete_v,
            command=lambda: _upd_del_state(),
            tooltip="Dateien im Archiv-Unterordner des Öffnungspfads werden nach der eingestellten Zeit automatisch gelöscht.")

        del_row = tk.Frame(opt_f, bg=self.C_BG)
        del_row.pack(fill=tk.X, padx=(self.s(22), 0), pady=(self.s(2), self.s(4)))
        del_lbl = tk.Label(del_row, text="Löschen nach (Stunden):", font=self.F_SMALL,
                           bg=self.C_BG, fg=self.C_TEXT)
        del_lbl.pack(side=tk.LEFT)
        del_border = tk.Frame(del_row, bg=self.C_WHITE,
                              highlightthickness=1, highlightbackground=self.C_BORDER)
        del_border.pack(side=tk.LEFT, padx=(self.s(8), 0))
        del_entry = tk.Entry(del_border, bg=self.C_WHITE, fg=self.C_TEXT,
                             font=self.F_BODY, relief=tk.FLAT, width=5,
                             insertbackground=self.C_TEXT)
        del_entry.pack(padx=6, pady=4)
        del_entry.insert(0, str(self.config.get("auto_delete_time", 12)))
        del_err = tk.Label(opt_f, text="", font=self.F_SMALL, bg=self.C_BG,
                           fg=self.C_DANGER_FG, anchor="w", padx=self.s(22))
        del_err.pack(fill=tk.X)

        def _upd_del_state():
            on = auto_delete_v.get()
            del_entry.config(state=tk.NORMAL if on else tk.DISABLED)
            del_lbl.config(fg=self.C_TEXT if on else self.C_HINT)

        _upd_del_state()

        _cb(opt_f, "Nicht zugeordnete Programme verschieben", move_sonstige_v,
            hint='PDFs und DFQs ohne Programmlisten-Eintrag landen im Unterordner "Eingang_Sonstige" des Öffnungspfads.',
            tooltip="Beim Scan-Now werden alle PDFs, die weder in der Stempel-Programmliste noch in der O-Qis-Programmliste stehen, zusammen mit ihrer DFQ in den Unterordner 'Eingang_Sonstige' im Öffnungspfad verschoben. Der Ordner wird automatisch angelegt.")

        tk.Frame(opt_f, bg=self.C_BORDER, height=1).pack(fill=tk.X, pady=self.s(12))
        self._section_label(opt_f, "Modus").pack(fill=tk.X, pady=(0, self.s(4)))
        _cb(opt_f, "Einfacher Stempel-Modus (kein DFQ, kein Archiv)", simple_v,
            hint="PDFs werden nur gestempelt gespeichert. DFQ-Suche und Archivierung entfallen.",
            tooltip="Fallback-Modus ohne DFQ-Zuordnung. Alle PDFs im Öffnungsordner werden angezeigt, die Programmliste wird ignoriert, und es wird kein Archiv angelegt.")

        # ── Fußzeile: Fehler + Buttons ────────────────────────────────────────
        tk.Frame(dlg, bg=self.C_BORDER, height=1).pack(fill=tk.X)
        foot = tk.Frame(dlg, bg=self.C_BG)
        foot.pack(fill=tk.X, pady=self.s(10), padx=self.s(20))
        foot_err = tk.Label(foot, text="", font=self.F_SMALL,
                            bg=self.C_BG, fg=self.C_DANGER_FG, anchor="w")
        foot_err.pack(side=tk.LEFT)

        def save():
            # Programmlisten validieren
            prog_new = {}
            prog_ok = True
            for key, (tw, err, uln) in prog_editors.items():
                tw.tag_remove("invalid_line", "1.0", tk.END)
                err.config(text="")
                lines = tw.get("1.0", "end-1c").splitlines()
                new_list, bad = [], []
                for i, line in enumerate(lines, 1):
                    if not line.strip():
                        continue
                    parts = [pp.strip() for pp in line.split(";")]
                    if len(parts) != 3 or any(pp == "" for pp in parts):
                        bad.append(i)
                    else:
                        new_list.append(line.strip())
                if bad:
                    for ln in bad:
                        tw.tag_add("invalid_line", f"{ln}.0", f"{ln}.end")
                    uln(invalid_lines=set(bad))
                    err.config(text=f"Zeile(n) {', '.join(map(str, bad))}: "
                                    "Format muss Werkstück;Mblatt;Zustand sein!")
                    prog_ok = False
                else:
                    prog_new[key] = new_list

            if not prog_ok:
                show_section("Programme")
                foot_err.config(text="Fehler in Programmliste – bitte korrigieren.")
                return

            # Löschzeit validieren
            del_time = None
            if auto_delete_v.get():
                try:
                    del_time = int(del_entry.get().strip())
                    if del_time <= 0:
                        raise ValueError
                    del_err.config(text="")
                except ValueError:
                    del_err.config(text="Bitte eine Zahl > 0 eingeben!")
                    show_section("Optionen")
                    foot_err.config(text="Fehler in Optionen – bitte korrigieren.")
                    return

            foot_err.config(text="")

            # Pfade übernehmen
            self.config["open_path"]     = paths["open_path"][0]
            self.config["save_path"]     = paths["save_path"][0]
            self.config["dfq_out"]       = paths["dfq_out"][0]
            self.config["stabi_path"]    = paths["stabi_path"][0]
            self.config["oqis_ein_path"] = paths["oqis_ein_path"][0]
            use_same = dfq_same_var.get()
            self.config["dfq_same_as_open"] = use_same
            self.config["dfq_path"] = (paths["open_path"][0] if use_same
                                       else paths["dfq_path"][0])

            # Programmlisten übernehmen
            for key, lst in prog_new.items():
                self.config[key] = lst

            # Optionen übernehmen
            self.config["auto_save"]          = auto_save_v.get()
            self.config["auto_delete"]         = auto_delete_v.get()
            self.config["auto_move_sonstige"]  = move_sonstige_v.get()
            self.config["simple_stamp_mode"]   = simple_v.get()
            if del_time is not None:
                self.config["auto_delete_time"] = del_time

            # Seiteneffekte
            if paths["open_path"][0] != old_open_path:
                self.watch_files = []
                self.file_listbox.delete(0, tk.END)
            self.root.title(
                "PDF Stempel Tool  [Einfacher Modus]" if simple_v.get()
                else "PDF Stempel Tool"
            )
            self.auto_save_var.set(auto_save_v.get())
            self.auto_delete_var.set(auto_delete_v.get())
            self.simple_stamp_var.set(simple_v.get())

            self.save_config()
            dlg.destroy()

        self._btn(foot, "Abbrechen", command=dlg.destroy,
                  style="secondary").pack(side=tk.RIGHT, padx=(self.s(6), 0))
        self._btn(foot, "Speichern", command=save,
                  style="primary").pack(side=tk.RIGHT)

        def _bind_scroll(widget, handler):
            if not isinstance(widget, tk.Text):
                widget.bind("<MouseWheel>", handler)
            for child in widget.winfo_children():
                _bind_scroll(child, handler)

        _bind_scroll(pfade_f, lambda e: pfade_cv.yview_scroll(int(-1 * e.delta / 120), "units"))
        _bind_scroll(prog_f,  lambda e: prog_cv.yview_scroll(int(-1 * e.delta / 120), "units"))

        show_section("Pfade")

    def close_pdf(self):
        """Schließt die aktuell geöffnete PDF und leert den Canvas"""
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None
        self.current_pdf = None
        self.current_page = 0
        self.zoom = 1.0
        self.page_positions = []
        self.page_photo_refs = []
        self.stamped_pages = set()
        self.pdf_canvas.delete("all")
        self.page_label.config(text="–")
        self.root.after(3000, lambda: self.filename_label.config(text="Keine Datei geöffnet", fg=self.C_HINT))
        
if __name__ == "__main__":
    root = tk.Tk()
    app = PDFStamperApp(root)
    root.mainloop()
