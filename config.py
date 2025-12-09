# config.py
from datetime import date
from collections import OrderedDict

# === LISTY UCZESTNIKÓW ===
PARTICIPANTS_LIST_BASE = [
    "navidjahanshahi", "new.things", "cezary-io", "manuvert", "racibo", 
    "ervin-lemark", "merthin", "sk1920", "edycu007", "ataraksja", 
    "homesteadlt", "browery", "fredkese", "marianomariano", "patif2025"
]

# Listy dla konkretnych edycji
PARTICIPANTS_NOVEMBER = list(PARTICIPANTS_LIST_BASE)
PARTICIPANTS_DECEMBER = [p for p in PARTICIPANTS_LIST_BASE if p != "patif2025"]
PARTICIPANTS_JANUARY = list(PARTICIPANTS_LIST_BASE)

SUBMITTER_LIST = sorted(list(set(PARTICIPANTS_LIST_BASE + ["poprzeczka (Admin)"])))
ALL_POSSIBLE_PARTICIPANTS = sorted(list(set(PARTICIPANTS_NOVEMBER + PARTICIPANTS_DECEMBER + PARTICIPANTS_JANUARY)))

# ID folderu na Google Drive
GOOGLE_DRIVE_FOLDER_ID = "1b-mUxDmKEUoOyLtTePeb7RaJWGfO_Xre"

# === DEFINICJE MIESIĘCY ===
MONTH_NAMES = {
    "november": {"pl": "Listopad", "en": "November", "icon": "🍂", "url_param_pl": "listopad", "url_param_en": "november"},
    "december": {"pl": "Grudzień", "en": "December", "icon": "❄️", "url_param_pl": "grudzien", "url_param_en": "december"},
    "january":  {"pl": "Styczeń",  "en": "January",  "icon": "⛄", "url_param_pl": "styczen",  "url_param_en": "january"},
}

# === KONFIGURACJA EDYCJI ===
# WAŻNE: Edycja startuje 1-go dnia miesiąca i trwa aż wszyscy uczestnicy odpadną
# Status automatycznie:
# - 🟢 ACTIVE: jeśli start_date <= dzisiaj (edycja się zaczęła i nie wszyscy odpadli)
# - ⏳ UPCOMING: jeśli start_date > dzisiaj (edycja się jeszcze nie zaczęła)
# - 🏁 FINISHED: jeśli wszyscy uczestnicy odpadli LUB jest_manually_closed = True

EDITIONS_CONFIG = OrderedDict([
    ("november", {
        "start_date": date(2025, 11, 1),  # Edycja startuje 1 listopada
        "sheet_name": "BiezacaEdycja",
        "participants": PARTICIPANTS_NOVEMBER,
        "is_manually_closed": False  # Zmień na True gdy wszyscy odpadną
    }),
    ("december", {
        "start_date": date(2025, 12, 1),  # Edycja startuje 1 grudnia
        "sheet_name": "EdycjaGrudzien",
        "participants": PARTICIPANTS_DECEMBER,
        "is_manually_closed": False  # Zmień na True gdy wszyscy odpadną
    }),
    ("january", {
        "start_date": date(2026, 1, 1),  # Edycja startuje 1 stycznia
        "sheet_name": "EdycjaStyczen",
        "participants": PARTICIPANTS_JANUARY,
        "is_manually_closed": False  # Zmień na True gdy wszyscy odpadną
    }),
])
