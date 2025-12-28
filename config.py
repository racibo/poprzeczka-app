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
PARTICIPANTS_DECEMBER = [p for p in PARTICIPANTS_LIST_BASE if p != "patif2025"]
PARTICIPANTS_JANUARY = list(PARTICIPANTS_LIST_BASE)
PARTICIPANTS_FEBRUARY = list(PARTICIPANTS_LIST_BASE) # Zakładamy tę samą listę, zmień jeśli trzeba

SUBMITTER_LIST = sorted(list(set(PARTICIPANTS_LIST_BASE + ["poprzeczka (Admin)"])))
ALL_POSSIBLE_PARTICIPANTS = sorted(list(set(PARTICIPANTS_DECEMBER + PARTICIPANTS_JANUARY + PARTICIPANTS_FEBRUARY)))
# ID folderu na Google Drive
GOOGLE_DRIVE_FOLDER_ID = "1b-mUxDmKEUoOyLtTePeb7RaJWGfO_Xre"

# === DEFINICJE MIESIĘCY ===
MONTH_NAMES = {
    # Listopad usunięty z definicji URL (opcjonalnie można zostawić dla historii, ale config edycji decyduje o menu)
    "november": {"pl": "Listopad", "en": "November", "icon": "🍂", "url_param_pl": "listopad", "url_param_en": "november"},
    "december": {"pl": "Grudzień", "en": "December", "icon": "❄️", "url_param_pl": "grudzien", "url_param_en": "december"},
    "january":  {"pl": "Styczeń",  "en": "January",  "icon": "⛄", "url_param_pl": "styczen",  "url_param_en": "january"},
    "february": {"pl": "Luty",     "en": "February", "icon": "💘", "url_param_pl": "luty",     "url_param_en": "february"},
}

# === KONFIGURACJA EDYCJI ===
# WAŻNE: Edycja startuje 1-go dnia miesiąca i trwa aż wszyscy uczestnicy odpadną
# Status automatycznie:
# - 🟢 ACTIVE: jeśli start_date <= dzisiaj (edycja się zaczęła i nie wszyscy odpadli)
# - ⏳ UPCOMING: jeśli start_date > dzisiaj (edycja się jeszcze nie zaczęła)
# - 🏁 FINISHED: jeśli wszyscy uczestnicy odpadli LUB jest_manually_closed = True

# === KONFIGURACJA EDYCJI (To decyduje co widać w MENU) ===
EDITIONS_CONFIG = OrderedDict([
    # Listopad USUNIĘTY z tej listy -> zniknie z menu
    ("december", {
        "start_date": date(2025, 12, 1),
        "sheet_name": "EdycjaGrudzien",
        "participants": PARTICIPANTS_DECEMBER,
        "is_manually_closed": False 
    }),
    ("january", {
        "start_date": date(2026, 1, 1),
        "sheet_name": "EdycjaStyczen",
        "participants": PARTICIPANTS_JANUARY,
        "is_manually_closed": False
    }),
    ("february", {
        "start_date": date(2026, 2, 1),
        "sheet_name": "EdycjaLuty",
        "participants": PARTICIPANTS_FEBRUARY,
        "is_manually_closed": False
    }),
])
