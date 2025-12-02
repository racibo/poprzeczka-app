# config.py

# === LISTY UCZESTNIKÓW ===

# Lista bazowa (Zaktualizowana wg Twojej prośby)
PARTICIPANTS_LIST_BASE = [
    "navidjahanshahi", "new.things", "cezary-io", "manuvert", "racibo", 
    "ervin-lemark", "merthin", "sk1920", "edycu007", "ataraksja", 
    "homesteadlt", "browery", "fredkese", "marianomariano", "patif2025"
]

# 1. Uczestnicy Edycji Listopadowej
PARTICIPANTS_NOVEMBER = list(PARTICIPANTS_LIST_BASE)

# 2. Uczestnicy Edycji Grudniowej (Na razie taka sama jak listopadowa)
PARTICIPANTS_DECEMBER = list(PARTICIPANTS_LIST_BASE)

# Lista zbiorcza do formularza
ALL_POSSIBLE_PARTICIPANTS = sorted(list(set(PARTICIPANTS_NOVEMBER + PARTICIPANTS_DECEMBER)))

# Alias dla kompatybilności
CURRENT_PARTICIPANTS = ALL_POSSIBLE_PARTICIPANTS 

SUBMITTER_LIST = sorted(list(set(ALL_POSSIBLE_PARTICIPANTS + ["poprzeczka (Admin)"])))

# ID folderu na Google Drive
GOOGLE_DRIVE_FOLDER_ID = "1b-mUxDmKEUoOyLtTePeb7RaJWGfO_Xre"

# === KONFIGURACJA EDYCJI ===
EDITIONS = {
    "november": {
        "sheet_name": "BiezacaEdycja",
        "label_pl": "🍂 Listopad",
        "label_en": "🍂 November",
        "participants": PARTICIPANTS_NOVEMBER
    },
    "december": {
        "sheet_name": "EdycjaGrudzien",
        "label_pl": "❄️ Grudzień",
        "label_en": "❄️ December",
        "participants": PARTICIPANTS_DECEMBER
    }
}

# === OVERLAP (ZAKŁADKA) ===
OVERLAP_START_DAY_OLD = 31
