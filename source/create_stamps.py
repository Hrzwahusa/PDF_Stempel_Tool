from PIL import Image, ImageDraw, ImageFont
import os

def create_stamp(text, color, filename, size=(150, 100)):
    """
    Erstellt einen Stempel mit transparentem Hintergrund
    
    Args:
        text: Der Text auf dem Stempel
        color: Farbe des Textes (RGB-Tupel)
        filename: Dateiname zum Speichern
        size: Größe des Stempels (Breite, Höhe)
    """
    # Bild mit transparentem Hintergrund erstellen
    img = Image.new('RGBA', size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Versuche eine große, fette Schrift zu verwenden
    font_size = 60
    try:
        # Versuche Arial Bold zu laden (Windows)
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        try:
            # Alternative: Arial normal
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            # Fallback: Standard-Schrift
            font = ImageFont.load_default()
    
    # Textgröße ermitteln
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Text zentrieren
    x = (size[0] - text_width) / 2
    y = ((size[1] - text_height) / 2) - 8
    
    # Rahmen zeichnen
    border_width = 8
    draw.rectangle(
        [(border_width, border_width), 
         (size[0] - border_width, size[1] - border_width)],
        outline=color,
        width=border_width
    )
    
    # Text zeichnen
    draw.text((x, y), text, font=font, fill=color)
    
    # Speichern
    img.save(filename, 'PNG')
    print(f"Stempel erstellt: {filename}")

# Ausgabeordner erstellen
output_folder = "Stempel"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Farben definieren
GREEN = (0, 150, 0, 255)  # Dunkelgrün
RED = (200, 0, 0, 255)    # Dunkelrot

# Grüne Stempel erstellen
create_stamp("i.T.", GREEN, os.path.join(output_folder, "iT_gruen.png"))
create_stamp("i.O.", GREEN, os.path.join(output_folder, "iO_gruen.png"))
create_stamp("bez. Seite", GREEN, os.path.join(output_folder, "bez_Seite_gruen.png"), size=(350, 100))

# Rote Stempel erstellen
create_stamp("a.T.", RED, os.path.join(output_folder, "aT_rot.png"))
create_stamp("n.i.O.", RED, os.path.join(output_folder, "niO_rot.png"), size=(200, 100))

print("\nAlle Stempel wurden erfolgreich erstellt!")
print(f"Sie finden die Stempel im Ordner: {os.path.abspath(output_folder)}")