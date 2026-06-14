"""
Generiert das Programm-Icon für das PDF Stempel Tool.
Ausgabe: icon.ico (16, 32, 48, 256 px)
"""

from PIL import Image, ImageDraw, ImageFont
import os
import math

C_BLUE   = (0, 87, 183, 255)    # #0057B7
C_WHITE  = (255, 255, 255, 255)
C_LIGHT  = (219, 235, 252, 255) # #DBEBFC
C_DARK   = (31,  39,  46, 255)  # #1F272E


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size

    # ── Hintergrund: abgerundetes Quadrat ──────────────────────────────────
    r = max(2, s // 6)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=C_BLUE)

    # ── Dokument (weißes Rechteck mit Eselsecke) ───────────────────────────
    ml  = round(s * 0.18)   # margin left/right
    mt  = round(s * 0.10)   # margin top
    mb  = round(s * 0.12)   # margin bottom
    fold = round(s * 0.20)  # Eselsecke

    doc_l = ml
    doc_r = s - ml
    doc_t = mt
    doc_b = s - mb

    # Dokument-Body (ohne Ecke)
    d.polygon([
        (doc_l,          doc_t + fold),
        (doc_l,          doc_b),
        (doc_r,          doc_b),
        (doc_r,          doc_t),
        (doc_l + fold,   doc_t),
    ], fill=C_WHITE)

    # Eselsecke (hellblau)
    d.polygon([
        (doc_l,          doc_t + fold),
        (doc_l + fold,   doc_t + fold),
        (doc_l + fold,   doc_t),
    ], fill=C_LIGHT)

    # ── Stempel-Kreis (unten rechts, überlappend) ──────────────────────────
    cr  = round(s * 0.285)          # Kreis-Radius
    cx  = round(s * 0.685)          # Mittelpunkt x
    cy  = round(s * 0.685)          # Mittelpunkt y
    bw  = max(1, round(s * 0.055))  # Randbreite

    # Äußerer Kreis (blau ausgefüllt mit weißem Rand)
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=C_WHITE)
    d.ellipse([cx - cr + bw, cy - cr + bw, cx + cr - bw, cy + cr - bw], fill=C_BLUE)

    # ── Geschwungene Textlinien auf dem Dokument ──────────────────────────
    if size >= 32:
        lw   = max(1, round(s * 0.020))   # Linienstärke
        amp  = max(1, round(s * 0.018))   # Wellenhöhe
        col  = (90, 110, 130, 210)        # gedämpftes Blaugrau

        # Linie 2+3 enden vor dem Stempel-Kreis (linke Kreisgrenze bei y=0.42: ~0.58, bei y=0.56: ~0.43)
        line_defs = [
            (0.28, 0.40, 0.72),   # (y_rel, x_start_rel, x_end_rel) – startet nach dem Knick
            (0.42, 0.28, 0.52),
            (0.56, 0.28, 0.38),
        ]
        ref_len = 0.32   # Länge der längsten Linie in relativen Einheiten
        steps   = max(8, round(s * 0.15))
        for y_rel, xs_rel, xe_rel in line_defs:
            y0        = round(s * y_rel)
            x0        = round(s * xs_rel)
            x1        = round(s * xe_rel)
            amp_scaled = max(1, round(amp * (xe_rel - xs_rel) / ref_len))
            pts = []
            for j in range(steps + 1):
                t_  = j / steps
                px  = round(x0 + t_ * (x1 - x0))
                py  = round(y0 + amp_scaled * math.sin(t_ * math.pi * 2))
                pts.append((px, py))
            d.line(pts, fill=col, width=lw)

    # ── Häkchen im Kreis ───────────────────────────────────────────────────
    if size >= 32:
        t  = max(1, round(cr * 0.20))
        p1 = (cx - round(cr * 0.42), cy + round(cr * 0.02))
        p2 = (cx - round(cr * 0.08), cy + round(cr * 0.40))
        p3 = (cx + round(cr * 0.44), cy - round(cr * 0.36))
        # Als einzelne Polylinie → sauberer Knick
        d.line([p1, p2, p3], fill=C_WHITE, width=t, joint="curve")
    else:
        pr = max(1, round(cr * 0.35))
        d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=C_WHITE)

    return img


sizes = [256, 48, 32, 16]
frames = [draw_icon(s) for s in sizes]

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
frames[0].save(
    out_path,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=frames[1:]
)
print(f"Icon gespeichert: {out_path}")

# Vorschau als PNG (zum Kontrollieren)
preview_path = out_path.replace(".ico", "_preview.png")
draw_icon(256).save(preview_path)
print(f"Vorschau: {preview_path}")
