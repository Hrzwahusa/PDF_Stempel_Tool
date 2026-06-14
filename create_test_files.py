"""
Erstellt Test-PDF und DFQ-Dateien für das PDF Stempel Tool.
Programmnamen stammen aus C:\backup_programmierstation_337\LHInspect\Data\TGear.
"""

import os
import fitz  # PyMuPDF
from datetime import datetime, timedelta

OUTPUT_DIR = r"C:\PDF_Stempel_Tool\test_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Programm-Einträge aus TGear Unterordnern (Format: p1;p2;p3)
PROGRAMME = [
    ("0001 300 049 (C)", "0001 300 049 (f)", "V1-SLF"),
    ("0001 302 321 (-)", "0001 302 321 (d)", "V1-WLS-KBL"),
    ("000 060 001 029",  "000 060 001 029",  "V1-FVZ"),
    ("000 260 005 622",  "000 260 005 622",  "Worm Gear"),
    ("0001 302 636",     "0001 302 636",     "V1-WLS"),
]

# Zeitstempel für jedes Test-Paar (14-stellig: YYYYMMDDHHmmss)
BASE_TIME = datetime(2026, 6, 14, 8, 0, 0)


def make_pdf(path, p1, p2, p3, timestamp):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    content = [
        f"Prüfprotokoll",
        f"",
        f"Werkstück:    {p1}",
        f"Mblatt:       {p2}",
        f"Zustand:      {p3}",
        f"Zeitstempel:  {timestamp}",
        f"",
        f"Datum: {timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}",
        f"Uhrzeit: {timestamp[8:10]}:{timestamp[10:12]}:{timestamp[12:14]}",
        f"",
        f"Messergebnis: Alle Merkmale innerhalb der Toleranz.",
    ]

    y = 80
    page.insert_text((60, y), "TESTPROTOKOLL", fontsize=18, color=(0.2, 0.2, 0.6))
    y += 40
    for line in content:
        page.insert_text((60, y), line, fontsize=11, color=(0, 0, 0))
        y += 20

    # Zweite Seite für mehrseitige Tests
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((60, 80), "Seite 2 – Messdetails", fontsize=14, color=(0.2, 0.2, 0.6))
    page2.insert_text((60, 120), f"Programm: {p1} / {p2} / {p3}", fontsize=11)
    page2.insert_text((60, 150), "Alle Toleranzen eingehalten.", fontsize=11)

    doc.save(path)
    doc.close()


def make_dfq(path, p1, p2, p3, timestamp):
    # Minimales Q-DAS DFQ Format (Textformat)
    content = f"""\
K0100 1
K0101 {p1}
K0102 {p2}
K0103 {p3}
K1001 {timestamp}
K1002 {timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}
K2001/1 12.003
K2001/2 11.998
K2001/3 12.001
K2001/4 12.005
K2001/5 11.997
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


created = []

# Format 1: YYYYMMDDHHmmss (14-stellig, ohne Unterstrich)
print("=== Format: YYYYMMDDHHmmss ===")
for i, (p1, p2, p3) in enumerate(PROGRAMME):
    ts = (BASE_TIME + timedelta(minutes=i * 17)).strftime("%Y%m%d%H%M%S")
    safe_name = f"{p1};{p2};{p3}_{ts}"
    pdf_path = os.path.join(OUTPUT_DIR, safe_name + ".pdf")
    dfq_path = os.path.join(OUTPUT_DIR, safe_name + ".dfq")
    make_pdf(pdf_path, p1, p2, p3, ts)
    make_dfq(dfq_path, p1, p2, p3, ts)
    created.append((pdf_path, dfq_path))
    print(f"[{i+1}] PDF: {safe_name}.pdf")
    print(f"     DFQ: {safe_name}.dfq")

# Format 2: YYYYMMDD_HHmmss (mit Unterstrich)
print("\n=== Format: YYYYMMDD_HHmmss ===")
BASE_TIME2 = datetime(2026, 6, 14, 10, 0, 0)
for i, (p1, p2, p3) in enumerate(PROGRAMME):
    dt = BASE_TIME2 + timedelta(minutes=i * 17)
    ts_display = dt.strftime("%Y%m%d_%H%M%S")   # im Dateinamen: mit Unterstrich
    ts_raw     = dt.strftime("%Y%m%d%H%M%S")    # für DFQ-Inhalt: ohne Unterstrich
    safe_name = f"{p1};{p2};{p3}_{ts_display}"
    pdf_path = os.path.join(OUTPUT_DIR, safe_name + ".pdf")
    dfq_path = os.path.join(OUTPUT_DIR, safe_name + ".dfq")
    make_pdf(pdf_path, p1, p2, p3, ts_display)
    make_dfq(dfq_path, p1, p2, p3, ts_raw)
    created.append((pdf_path, dfq_path))
    print(f"[{i+1}] PDF: {safe_name}.pdf")
    print(f"     DFQ: {safe_name}.dfq")

print(f"\n{len(created)} Paare gesamt erstellt in: {OUTPUT_DIR}")
