# Was macht das Programm?

Das Tool überwacht einen Eingangsordner auf neue PDF-Prüfprotokolle. Du wählst einen Stempel, klickst ihn auf jede Seite der PDF, und drückst "Speichern". Das Programm sucht dann automatisch die passende DFQ-Messdatei (gleicher Programmname + gleicher Zeitstempel), kopiert beide Dateien in den Ausgabeordner und verschiebt die Originale ins Archiv.

# Konfiguration

## Öffnungspfad  (Einstellungen → Öffnungspfad festlegen)

Der Ordner, den das Tool auf neue PDFs überwacht. Hier müssen auch die DFQ-Dateien liegen, sofern kein separater DFQ-Ordner gesetzt ist.

## Speicherpfad  (Einstellungen → Speicherpfad festlegen)

Wohin die gestempelte PDF und die DFQ-Datei nach dem Speichern kopiert werden.

## DFQ-Ordner  (Einstellungen → DFQ Ordner festlegen)

Falls DFQ-Dateien in einem anderen Ordner als die PDFs liegen, kann hier ein separater Pfad gesetzt werden. Standardmäßig wird der Öffnungspfad verwendet.

## Programme konfigurieren  (Einstellungen → Programme zum Stempeln festlegen)

Legt fest, welche PDFs in der Liste angezeigt werden. Jeder Eintrag besteht aus drei Teilen, getrennt durch Semikolon:

```
Werkstück;Mblatt;Zustand
z. B.  0001_300_049_C_V1;0001_300_049_F;H_4PLT_da_df_MdK
```

Eine PDF erscheint in der Liste, wenn alle drei Teile im Dateinamen enthalten sind. Ist die Liste leer, werden alle PDFs im Öffnungsordner angezeigt.

# Dateinamens-Format

PDFs und DFQ-Dateien müssen alle drei Programmteile sowie einen Zeitstempel im Namen tragen. Zwei Formate werden erkannt:

```
YYYYMMDDHHmmss        →  20260614143022
YYYYMMDD_HHmmss       →  20260614_143022
```

PDF und DFQ brauchen denselben Zeitstempel – so findet das Tool die zusammengehörenden Dateien. Beispiel für ein gültiges Dateinamens-Paar:

```
0001 300 049 (C);0001 300 049 (f);V1-SLF_20260614_143022.pdf
0001 300 049 (C);0001 300 049 (f);V1-SLF_20260614_143022.dfq
```

# Workflow

1. PDF in der Liste links auswählen → sie öffnet sich im Viewer.
2. Stempel oben links anklicken (iO, iT, niO ...) → Vorschau erscheint.
3. Auf jede Seite der PDF klicken um den Stempel zu platzieren.
4. "Speichern" drücken → DFQ wird gesucht, beide Dateien gespeichert, Originale archiviert.

# Einfacher Stempel-Modus  (Fallback)

Unter Einstellungen → "Einfacher Stempel-Modus (kein DFQ, kein Archiv)" kann ein vereinfachter Betrieb aktiviert werden: Die DFQ-Suche und das Verschieben der Originale entfallen. Es wird nur die gestempelte PDF gespeichert. Der Modus ist in der Titelleiste als [Einfacher Modus] sichtbar.

# Archiv

Originaldateien (PDF + DFQ) werden nach dem Speichern automatisch in den Unterordner "Archiv" im Öffnungspfad verschoben und nach 7 Tagen automatisch gelöscht.
