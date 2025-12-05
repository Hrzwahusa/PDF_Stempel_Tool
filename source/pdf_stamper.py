import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import PhotoImage
import json
import os
import sys
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import io


class PDFStamperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Stempel Tool")
        self.root.geometry("1200x800")
        
        # Pfad zum Verzeichnis der ausführbaren Datei
        if getattr(sys, 'frozen', False):
            # Wenn als .exe kompiliert
            self.app_path = os.path.dirname(sys.executable)
        else:
            # Wenn als Python-Skript ausgeführt
            self.app_path = os.path.dirname(os.path.abspath(__file__))
        
        # Konfigurationsdatei
        self.config_file = "pdf_stamper_config.json"
        self.config = self.load_config()
        
        # Variablen
        self.current_pdf = None
        self.pdf_document = None
        self.current_page = 0
        self.zoom = 1.0
        self.selected_stamp = None
        self.stamps = []
        self.watch_files = []
        self.file_paths = {}  # Mapping von Anzeigenamen zu vollständigen Pfaden
        # Liste bearbeiteter Dateien laden und normalisieren
        raw_stamped = self.config.get("stamped_files", [])
        self.stamped_files = [os.path.normpath(f.strip()) for f in raw_stamped]
        self.stamped_files_timestamps = self.config.get("stamped_files_timestamps", {})
        self.hide_stamped = tk.BooleanVar(value=False)
        self.auto_save_var = tk.BooleanVar(value=self.config.get("auto_save", False))
        self.auto_delete_var=tk.BooleanVar(value=self.config.get("auto_delete", False))
        
        # GUI erstellen
        self.create_gui()
        
        # Überwachung starten
        self.watch_folder()
        
    def load_config(self):
        """Konfiguration laden oder Standard erstellen"""
        default_config = {
            "open_path": str(Path.home() / "Documents"),
            "save_path": str(Path.home() / "Documents"),
            "auto_save": False,  # Automatisch speichern ohne Dialog
            "auto_delete": False, # Automatisches löschen alter Protokolle
            "auto_delete_time": 12 # Protokolle älter x Stunden löschen
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    # Alte gestempelte Dateien bereinigen (älter als 24 Stunden)
                    if "stamped_files_timestamps" in config:
                        self.cleanup_old_stamped_files(config)
                    
                    return config
            except:
                return default_config
        return default_config

    def cleanup_old_files(self):
        import time
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
            # Alte gestempelte löschen
            if(os.path.exists(stamped_files_path)):
                for root, dirs, files in os.walk(stamped_files_path):
                    for file in files:
                        if(file.lower().endswith('.pdf')):
                            full_path = os.path.normpath(os.path.join(root, file))
                            file_time = os.path.getmtime(full_path)
                            if(current_time - file_time > time_limit):
                                try:
                                    os.remove(full_path)
                                    print(f"Datei '{file}' erfolgreich geloescht!")
                                except FileNotFoundError: print(f"Datei '{file}' nicht gefunden.")
        
    def cleanup_old_stamped_files(self, config):
        """Entfernt gestempelte Dateien die älter als 24 Stunden sind"""
        import time
        
        current_time = time.time()
        time_limit = 24 * 60 * 60  # 24 Stunden in Sekunden
        
        stamped_files = config.get("stamped_files", [])
        timestamps = config.get("stamped_files_timestamps", {})
        
        # Nur Dateien behalten die jünger als 24 Stunden sind
        new_stamped_files = []
        new_timestamps = {}
        
        for file in stamped_files:
            file_timestamp = timestamps.get(file, current_time)
            if current_time - file_timestamp < time_limit:
                new_stamped_files.append(file)
                new_timestamps[file] = file_timestamp
        
        config["stamped_files"] = new_stamped_files
        config["stamped_files_timestamps"] = new_timestamps
    
    def on_mousewheel(self, event):
        """Mausrad-Scrollen im PDF Canvas"""
        if event.num == 5 or event.delta < 0:
            # Scroll down
            self.pdf_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            # Scroll up
            self.pdf_canvas.yview_scroll(-1, "units")
        return "break"
    
    def get_stamp_folder(self):
        """Gibt den Stempel-Ordner-Pfad zurück (immer relativ zur .exe)"""
        return os.path.join(self.app_path, "Stempel")
    
    def save_config(self):
        """Konfiguration speichern"""
        self.config["stamped_files"] = self.stamped_files
        
        # Timestamps für gestempelte Dateien speichern
        if not hasattr(self, 'stamped_files_timestamps'):
            self.stamped_files_timestamps = self.config.get("stamped_files_timestamps", {})
        
        self.config["stamped_files_timestamps"] = self.stamped_files_timestamps
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
    
    def create_gui(self):
        """GUI-Elemente erstellen"""
        # Menüleiste
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Datei", menu=file_menu)
        file_menu.add_command(label="PDF öffnen", command=self.open_pdf)
        file_menu.add_command(label="PDF speichern", command=self.save_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.root.quit)
        
        self.settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Einstellungen", menu=self.settings_menu)
        self.settings_menu.add_command(label="Öffnungspfad festlegen", command=self.set_open_path)
        self.settings_menu.add_command(label="Speicherpfad festlegen", command=self.set_save_path)
        self.settings_menu.add_separator()
        self.settings_menu.add_checkbutton(label="Automatisch speichern (ohne Dialog)", 
                                      command=self.toggle_auto_save,
                                      variable=self.auto_save_var)
        self.settings_menu.add_checkbutton(label="Alte Protokolle automatisch löschen",
                                      command=self.toggle_auto_delete,
                                      variable=self.auto_delete_var)
        self.settings_menu.add_command(label=f"Lösche Protokolle älter {self.config.get("auto_delete_time")}h", command=self.set_delete_time) 
                                      
        info_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="?", menu=info_menu)
        info_menu.add_command(label="Info", command=self.show_info)
        
        # Hauptcontainer
        main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Linke Seite - Stempel und Dateiliste
        left_frame = tk.Frame(main_container, width=350)
        main_container.add(left_frame)
        
        # Stempel-Bereich
        stamp_label = tk.Label(left_frame, text="Stempel:", font=("Arial", 10, "bold"))
        stamp_label.pack(pady=5)
        
        # Vorschau des ausgewählten Stempels
        self.preview_frame = tk.Frame(left_frame, relief=tk.SUNKEN, borderwidth=2, bg="white", height=80)
        self.preview_frame.pack(fill=tk.X, padx=5, pady=5)
        self.preview_frame.pack_propagate(False)
        
        self.preview_label = tk.Label(self.preview_frame, text="Kein Stempel ausgewählt", bg="white", fg="gray")
        self.preview_label.pack(expand=True)
        
        # Button zum Abwählen des Stempels
        deselect_btn = tk.Button(left_frame, text="Stempel abwählen", command=self.deselect_stamp)
        deselect_btn.pack(pady=5)
        
        # Button zum Löschen aller Stempel
        clear_btn = tk.Button(left_frame, text="🗑️ Alle Stempel entfernen", 
                              command=self.clear_all_stamps, bg="salmon")
        clear_btn.pack(pady=5)
        
        stamp_frame = tk.Frame(left_frame, relief=tk.SUNKEN, borderwidth=2)
        stamp_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.stamp_canvas = tk.Canvas(stamp_frame, bg="white")
        stamp_scrollbar = tk.Scrollbar(stamp_frame, command=self.stamp_canvas.yview)
        self.stamp_canvas.configure(yscrollcommand=stamp_scrollbar.set)
        
        stamp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.stamp_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.stamp_inner_frame = tk.Frame(self.stamp_canvas)
        self.stamp_canvas.create_window((0, 0), window=self.stamp_inner_frame, anchor="nw")
        
        # Dateiliste
        file_label = tk.Label(left_frame, text="Neue Dateien:", font=("Arial", 10, "bold"))
        file_label.pack(pady=5)
        
        # Checkbox zum Ausblenden gestempelter Dateien
        hide_check = tk.Checkbutton(left_frame, text="Gestempelte Dateien ausblenden", 
                                    variable=self.hide_stamped, command=self.update_file_list)
        hide_check.pack(pady=2)
        
        file_frame = tk.Frame(left_frame, relief=tk.SUNKEN, borderwidth=2)
        file_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Listbox mit fester Schriftart für richtige Ausrichtung
        self.file_listbox = tk.Listbox(file_frame, font=("Courier New", 9))
        file_scrollbar = tk.Scrollbar(file_frame, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.file_listbox.bind('<Double-Button-1>', self.open_from_list)
        
        open_btn = tk.Button(left_frame, text="Ausgewählte Datei öffnen", command=self.open_from_list)
        open_btn.pack(pady=5)
        
        # Rechte Seite - PDF-Anzeige
        right_frame = tk.Frame(main_container)
        main_container.add(right_frame)
        
        # Toolbar
        toolbar = tk.Frame(right_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(toolbar, text="📁 PDF öffnen", command=self.open_pdf, 
                 bg="lightblue", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Vorherige Seite", command=self.prev_page).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Nächste Seite", command=self.next_page).pack(side=tk.LEFT, padx=2)
        
        self.page_label = tk.Label(toolbar, text="Keine PDF geladen")
        self.page_label.pack(side=tk.LEFT, padx=10)
        
        tk.Button(toolbar, text="Zoom +", command=self.zoom_in).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Zoom -", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        
        # Speichern-Button rechts
        tk.Button(toolbar, text="💾 PDF speichern", command=self.save_pdf, 
                 bg="lightgreen", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=5)
        
        # Dateiname-Anzeige
        filename_frame = tk.Frame(right_frame, bg="lightgray", relief=tk.SUNKEN, borderwidth=1)
        filename_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.filename_label = tk.Label(filename_frame, text="Keine Datei geöffnet", 
                                       bg="lightgray", anchor="w", padx=10, pady=5)
        self.filename_label.pack(fill=tk.X)
        
        # PDF Canvas
        canvas_frame = tk.Frame(right_frame, relief=tk.SUNKEN, borderwidth=2)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.pdf_canvas = tk.Canvas(canvas_frame, bg="gray")
        h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.pdf_canvas.xview)
        v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.pdf_canvas.yview)
        
        self.pdf_canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.pdf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.pdf_canvas.bind('<Button-1>', self.place_stamp)
        
        # Mausrad-Scrollen aktivieren
        self.pdf_canvas.bind('<MouseWheel>', self.on_mousewheel)  # Windows
        self.pdf_canvas.bind('<Button-4>', self.on_mousewheel)    # Linux scroll up
        self.pdf_canvas.bind('<Button-5>', self.on_mousewheel)    # Linux scroll down

        # Stempel laden
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
                               relief=tk.RAISED, borderwidth=2)
                btn.image = photo  # Referenz behalten
                btn.grid(row=i//2, column=i%2, padx=5, pady=5)
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
        self.preview_label.configure(image="", text="Kein Stempel ausgewählt", fg="gray")
        self.preview_label.image = None
        
    def show_info(self):
        messagebox.showinfo("Info", "Erstellt von: Jan Schmidt \nBei Fragen und Anregungen Email an: jan.schmidt2@zf.com \n\nPDF_Stempel_Tool v1.0.0")
    
    def clear_all_stamps(self):
        """Alle Stempel von der aktuellen PDF entfernen"""
        if not self.pdf_document or not self.current_pdf:
            messagebox.showwarning("Warnung", "Keine PDF geöffnet.")
            return
        
        # Bestätigungsdialog
        result = messagebox.askyesno(
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
                self.display_page()
                messagebox.showinfo("Erfolg", "Alle Stempel wurden entfernt.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Entfernen der Stempel:\n{str(e)}")
    
    def watch_folder(self):
        """Überwachten Ordner auf neue PDF-Dateien prüfen (inkl. Unterordner)"""
        self.scan_folder_now()
        self.root.after(2000, self.watch_folder)  # Alle 2 Sekunden prüfen
    
    def scan_folder_now(self):
        """Führt den Ordner-Scan sofort aus"""
        open_path = self.config.get("open_path", "")
        
        if os.path.exists(open_path):
            try:
                from datetime import datetime, timedelta
                
                # Zeitgrenze: 12 Stunden zurück
                time_limit = datetime.now().timestamp() - (12 * 60 * 60)
                
                # Alle PDF-Dateien inkl. Unterordner finden
                all_pdf_files = []
                for root, dirs, files in os.walk(open_path):
                    for file in files:
                        if file.lower().endswith('.pdf'):
                            full_path = os.path.normpath(os.path.join(root, file))
                            # Relativen Pfad zum überwachten Ordner erstellen
                            rel_path = os.path.relpath(full_path, open_path)
                            # Änderungszeit ermitteln
                            mtime = os.path.getmtime(full_path)
                            
                            # Nur Dateien der letzten 12 Stunden
                            if mtime >= time_limit:
                                all_pdf_files.append((rel_path, mtime, full_path))
                
                # Nach Änderungszeit sortieren (neueste zuerst)
                all_pdf_files.sort(key=lambda x: x[1], reverse=True)
                
                # Gestempelte Dateien filtern wenn aktiviert
                pdf_files = []
                for item in all_pdf_files:
                    rel_path, mtime, full_path = item
                    if self.hide_stamped.get() and full_path in self.stamped_files:
                        continue
                    pdf_files.append(item)
                
                # Liste immer aktualisieren (auch bei Filteränderung)
                self.watch_files = [f[0] for f in pdf_files]
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
        self.file_paths = {}  # Mapping zurücksetzen
        
        # Filterung basierend auf Checkbox
        pdf_files = []
        for item in all_pdf_files:
            rel_path, mtime, full_path = item
            if self.hide_stamped.get() and full_path in self.stamped_files:
                continue
            pdf_files.append(item)
        
        for rel_path, mtime, full_path in pdf_files:
            # Nur Dateiname ohne Pfad
            filename = os.path.basename(rel_path)
            
            # Zeitstempel formatieren
            time_str = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")
            
            # Markierung für gestempelte Dateien
            marker = "✓ " if full_path in self.stamped_files else "  "
            
            # Dateiname eventuell kürzen wenn zu lang (max 30 Zeichen)
            max_filename_len = 30
            if len(filename) > max_filename_len:
                display_filename = filename[:max_filename_len-3] + "..."
            else:
                display_filename = filename
            
            # Feste Breite für Dateiname (linksbündig) + Zeitstempel (rechtsbündig)
            spaces = max(1, 35 - len(display_filename))
            display_text = f"{marker}{display_filename}{' ' * spaces}[{time_str}]"
            self.file_listbox.insert(tk.END, display_text)
            
            # Mapping speichern: Anzeigename -> vollständiger Pfad
            self.file_paths[display_text] = full_path
            
            # Gestempelte Dateien grau färben
            if full_path in self.stamped_files:
                self.file_listbox.itemconfig(tk.END, fg="gray")
    
    def open_from_list(self, event=None):
        """PDF aus der Dateiliste öffnen"""
        selection = self.file_listbox.curselection()
        if not selection:
            return
        
        # Text aus Listbox holen
        display_text = self.file_listbox.get(selection[0])
        
        # Vollständigen Pfad aus Mapping holen
        filepath = self.file_paths.get(display_text)
        
        if filepath and os.path.exists(filepath):
            self.open_pdf(filepath)
        else:
            messagebox.showerror("Fehler", f"Datei nicht gefunden")
    
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
            
            # Dateiname anzeigen
            filename = os.path.basename(filepath)
            self.filename_label.config(text=f"📄 {filename}")
            
            self.display_page()
        except Exception as e:
            messagebox.showerror("Fehler", f"PDF konnte nicht geöffnet werden:\n{str(e)}")
    
    def display_page(self):
        """Aktuelle PDF-Seite anzeigen"""
        if not self.pdf_document:
            return
        
        page = self.pdf_document[self.current_page]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Pixmap zu PIL Image konvertieren
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        photo = ImageTk.PhotoImage(img)
        
        self.pdf_canvas.delete("all")
        self.pdf_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.pdf_canvas.image = photo  # Referenz behalten
        
        self.pdf_canvas.configure(scrollregion=self.pdf_canvas.bbox("all"))
        
        self.page_label.config(text=f"Seite {self.current_page + 1} von {len(self.pdf_document)}")
    
    def prev_page(self):
        """Vorherige Seite anzeigen"""
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.display_page()
    
    def next_page(self):
        """Nächste Seite anzeigen"""
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.display_page()
    
    def zoom_in(self):
        """Vergrößern"""
        self.zoom = min(self.zoom + 0.2, 3.0)
        self.display_page()
    
    def zoom_out(self):
        """Verkleinern"""
        self.zoom = max(self.zoom - 0.2, 0.5)
        self.display_page()
    
    def place_stamp(self, event):
        """Stempel an Mausposition platzieren (zentriert)"""
        if not self.selected_stamp or not self.pdf_document:
            messagebox.showwarning("Warnung", "Bitte wählen Sie zuerst einen Stempel und öffnen Sie eine PDF.")
            return
        
        # Koordinaten relativ zum Canvas
        canvas_x = self.pdf_canvas.canvasx(event.x)
        canvas_y = self.pdf_canvas.canvasy(event.y)
        
        # In PDF-Koordinaten umrechnen
        page = self.pdf_document[self.current_page]
        pdf_x = canvas_x / self.zoom
        pdf_y = canvas_y / self.zoom
        
        try:
            # Stempel-Bild laden
            stamp_img = Image.open(self.selected_stamp)
            
            # Stempel-Größe (in PDF-Punkten) - Höhe ist fix, Breite proportional
            stamp_height = 40
            stamp_width = stamp_img.width * (stamp_height / stamp_img.height)
            
            # Position zentrieren - Stempel-Mitte auf Mauszeiger
            centered_x = pdf_x - (stamp_width / 2)
            centered_y = pdf_y - (stamp_height / 2)
            
            # Stempel zur PDF hinzufügen
            rect = fitz.Rect(centered_x, centered_y, centered_x + stamp_width, centered_y + stamp_height)
            
            # Bild in Bytes konvertieren
            img_byte_arr = io.BytesIO()
            stamp_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            page.insert_image(rect, stream=img_byte_arr)
            
            # Seite neu anzeigen
            self.display_page()
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Stempel konnte nicht platziert werden:\n{str(e)}")
    
    def save_pdf(self):
        """Gestempelte PDF speichern"""
        self.cleanup_old_files()
        if not self.pdf_document:
            messagebox.showwarning("Warnung", "Keine PDF geöffnet.")
            return
        
        filename = os.path.basename(self.current_pdf)
        name, ext = os.path.splitext(filename)
        default_name = f"{name}_gestempelt{ext}"
        
        # Automatisch speichern ohne Dialog
        if self.config.get("auto_save", False):
            filepath = os.path.join(self.config.get("save_path", ""), default_name)
        else:
            # Mit Speichern-Dialog
            filepath = filedialog.asksaveasfilename(
                initialdir=self.config.get("save_path", ""),
                initialfile=default_name,
                title="PDF speichern",
                filetypes=[("PDF-Dateien", "*.pdf")]
            )
        
        if filepath:
            try:
                self.pdf_document.save(filepath)
                
                # Datei als gestempelt markieren (ohne Leerzeichen!)
                normalized_path = os.path.normpath(self.current_pdf)
                if normalized_path not in self.stamped_files:
                    import time
                    self.stamped_files.append(normalized_path)
                    self.stamped_files_timestamps[normalized_path] = time.time()
                    self.save_config()
                    
                
                if self.config.get("auto_save", False):
                    # Kurze Bestätigung bei Auto-Save
                    self.filename_label.config(text=f"✅ Gespeichert: {os.path.basename(filepath)}")
                    #self.root.after(3000, lambda: self.filename_label.config(text=f"📄 {os.path.basename(self.current_pdf)}"))
                    self.close_pdf()
                else:
                    messagebox.showinfo("Erfolg", f"PDF wurde gespeichert:\n{filepath}")
                    self.close_pdf()
            except Exception as e:
                messagebox.showerror("Fehler", f"PDF konnte nicht gespeichert werden:\n{str(e)}")
    
    def close_pdf(self):
        """Schließt die aktuell geöffnete PDF"""
        if self.pdf_document:
            self.pdf_document.close()
            self.pdf_document = None
            self.current_pdf = None
            self.current_page = 0
            self.zoom = 1.0
            self.pdf_canvas.delete("all")
            self.page_label.config(text="Keine PDF geladen")
            self.root.after(3000, lambda: self.filename_label.config(text="Keine Datei geöffnet"))
        

    def set_open_path(self):
        """Öffnungspfad festlegen"""
        path = filedialog.askdirectory(title="Öffnungspfad wählen")
        if path:
            self.config["open_path"] = path
            self.save_config()
            self.watch_files = []  # Liste zurücksetzen
            self.file_listbox.delete(0, tk.END)  # Listbox leeren
            messagebox.showinfo("Erfolg", f"Öffnungspfad festgelegt:\n{path}")
            
    def set_delete_time(self):
        inputbox = tk.Tk()
        inputbox.title("Lösche Protokolle älter X Stunden")
        tk.Label(inputbox, text='Zeit in Stunden nach der alte Protokolle gelöscht werden sollen').pack()
        entry = tk.Entry(inputbox)
        entry.pack()
        
        error_label = tk.Label(inputbox, text='', fg='red')
        error_label.pack()
        
        def save_delete_time_in_config():
            eingabewert = entry.get()  # Direkt vom Entry-Widget holen
            
            # Debug: Schauen was tatsächlich ausgelesen wird
            print(f"Eingabewert: '{eingabewert}'")
            
            if not eingabewert or eingabewert.strip() == '' or eingabewert.strip() == '0':
                error_label.config(text='Bitte einen Wert > 0 eingeben!')
                return
            
            try:
                self.config["auto_delete_time"] = int(eingabewert.strip())
                self.save_config()
                self.settings_menu.entryconfig(5, label=f"Lösche Protokolle älter {self.config.get('auto_delete_time')}h")
            
                inputbox.destroy()
            except ValueError:
                error_label.config(text='Bitte eine gültige Zahl eingeben!')
        
        tk.Button(inputbox, text='Speichern', command=save_delete_time_in_config).pack()
        entry.bind('<Return>', lambda e: save_delete_time_in_config())
    
    def set_save_path(self):
        """Speicherpfad festlegen"""
        path = filedialog.askdirectory(title="Speicherpfad wählen")
        if path:
            self.config["save_path"] = path
            self.save_config()
            messagebox.showinfo("Erfolg", f"Speicherpfad festgelegt:\n{path}")
    
    def toggle_auto_save(self):
        """Automatisches Speichern umschalten"""
        # Wert aus der Variable nehmen (die ist jetzt aktuell)
        new_value = self.auto_save_var.get()
        self.config["auto_save"] = new_value
        self.save_config()
        
        if new_value:
            messagebox.showinfo("Auto-Save aktiviert", 
                              "PDFs werden jetzt automatisch ohne Dialog gespeichert.\n\n" +
                              f"Speicherort: {self.config.get('save_path', '')}")
        else:
            messagebox.showinfo("Auto-Save deaktiviert", 
                              "PDFs werden mit Speichern-Dialog gespeichert.")
                              
    def toggle_auto_delete(self):
        new_value = self.auto_delete_var.get()
        self.config["auto_delete"] = new_value
        self.save_config()

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFStamperApp(root)
    root.mainloop()