# Was macht das Programm?

Das Tool überwacht einen Eingangsordner auf neue PDF-Prüfprotokolle. Du wählst einen Stempel, klickst ihn auf jede Seite der PDF, und drückst "Speichern". Das Programm sucht dann automatisch die passende DFQ-Messdatei (gleicher Programmname + gleicher Zeitstempel), kopiert beide Dateien in die entsprechenden Ausgabeordner und verschiebt die Originale ins Archiv. Dateien älter 7 Tage im Archiv werden automatisch gelöscht.

# Konfiguration

## PDF Öffnungspfad  (Einstellungen → PDF Öffnungspfad festlegen)

Der Ordner, den das Tool auf neue PDFs überwacht. Hier müssen auch die DFQ-Dateien liegen, sofern kein separater DFQ-Ordner gesetzt ist.

## PDF Speicherpfad  (Einstellungen → PDF Speicherpfad festlegen)

Wohin die gestempelte PDF und die DFQ-Datei nach dem Speichern kopiert werden.

## DFQ Eingang festlegen  (Einstellungen → DFQ Eingang festlegen)

Falls DFQ-Dateien in einem anderen Ordner als die PDFs liegen, kann hier ein separater Pfad gesetzt werden. Standardmäßig wird der Öffnungspfad verwendet.

## DFQ Ausgang festlegen (Einstellungen → DFQ Ausgang festlegen)

Speicherort für DFQ Dateien festlegen (für Upload)

## Programme konfigurieren  (Einstellungen → Programme zum Stempeln festlegen)

Legt fest, welche PDFs in der Liste angezeigt werden. Jeder Eintrag besteht aus drei Teilen, getrennt durch Semikolon:

```
Werkstück;Mblatt;Zustand
z. B.  0001_300_049_C_V1;0001_300_049_F;H_4PLT_da_df_MdK
```

Eine PDF erscheint in der Liste, wenn alle drei Teile im Dateinamen enthalten sind. Ist die Liste leer, werden alle PDFs im Öffnungsordner angezeigt.

## Programme für O-Qis festlegen (Einstellungen → Programme für O-Qis festlegen)

PDFs werden in Ordner zur Stabilitätsprüfung abgelegt und DFQ Dateien von diesen Programmen werden in den alten O-Qis_Eingang Ordner verschoben um den normalen O-Qis Uploadflow zu durchlaufen.
z.B. Programme zur Stabilitätsprüfung
Format gleich "Programme konfigurieren"

## PDF Stabilitätsprüfung Ordner festlegen (Einstellungen → Stabilitätsprüfung PDF Ordner festlegen)

In diesem Ordner werden die PDFs aus der Liste Programme für O-Qis abgelegt

## O-Qis Eingang Ordner festlegen (Einstellungen → O-Qis-Eingang Pfad festlegen)

Pfad zum normalen O-Qis Upload Ordner (standart C:\users\public\zff\O-Qis\O-Qis_Eingang)

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

oder

0001 300 049 (C);0001 300 049 (f);V1-SLF_20260614_143022.pdf
0001 300 049 (f);0001 300 049 (C);V1-SLF_20260614143022.dfq
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
