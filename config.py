# config.py
from datetime import date, datetime
from collections import OrderedDict
import json
import os

# === LISTY UCZESTNIKÓW (BAZOWE) ===
# Zostawiamy bez zmian - to chroni historię
PARTICIPANTS_LIST_BASE = [
    "new.things", "cezary-io", "manuvert", "racibo", 
    "ervin-lemark", "merthin", "sk1920", "edycu007", "ataraksja", 
    "homesteadlt", "browery", "fredkese", "marianomariano", "patif2025"
]

# === LISTY DLA KONKRETNYCH EDYCJI ===

PARTICIPANTS_DECEMBER = [p for p in PARTICIPANTS_LIST_BASE if p != "patif2025"]

PARTICIPANTS_JANUARY = [
    p for p in PARTICIPANTS_LIST_BASE 
    if p not in ["patif2025", "ataraksja"]
]

PARTICIPANTS_FEBRUARY = [p for p in PARTICIPANTS_LIST_BASE if p not in ["patif2025", "ataraksja"]]

PARTICIPANTS_MARCH = [p for p in PARTICIPANTS_LIST_BASE if p not in ["patif2025", "ataraksja"]] + ["stranger27"]

# === NOWA LISTA: KWIECIEŃ ===
PARTICIPANTS_APRIL = [p for p in PARTICIPANTS_LIST_BASE if p not in ["patif2025", "ataraksja"]] + ["stranger27"]


# === LISTY POMOCNICZE ===
# Dodajemy stranger27 ręcznie do submitterów, bo nie ma go w BASE
SUBMITTER_LIST = sorted(list(set(PARTICIPANTS_LIST_BASE + ["poprzeczka (Admin)", "stranger27"])))

# Aktualizacja wszystkich możliwych uczestników o listę marcową i kwietniową
ALL_POSSIBLE_PARTICIPANTS = sorted(list(set(PARTICIPANTS_DECEMBER + PARTICIPANTS_JANUARY + PARTICIPANTS_FEBRUARY + PARTICIPANTS_MARCH + PARTICIPANTS_APRIL)))

# ID folderu na Google Drive
GOOGLE_DRIVE_FOLDER_ID = "1b-mUxDmKEUoOyLtTePeb7RaJWGfO_Xre"

# === DEFINICJE MIESIĘCY ===
MONTH_NAMES = {
    "november": {"pl": "Listopad", "en": "November", "icon": "🍂", "url_param_pl": "listopad", "url_param_en": "november"},
    "december": {"pl": "Grudzień", "en": "December", "icon": "❄️", "url_param_pl": "grudzien", "url_param_en": "december"},
    "january":  {"pl": "Styczeń",  "en": "January",  "icon": "⛄", "url_param_pl": "styczen",  "url_param_en": "january"},
    "february": {"pl": "Luty",     "en": "February", "icon": "💘", "url_param_pl": "luty",     "url_param_en": "february"},
    "march":    {"pl": "Marzec",   "en": "March",    "icon": "🌱", "url_param_pl": "marzec",   "url_param_en": "march"},
    "april":    {"pl": "Kwiecień", "en": "April",    "icon": "🌸", "url_param_pl": "kwiecien", "url_param_en": "april"},
}

# === DOMYŚLNA KONFIGURACJA ===
DEFAULT_EDITIONS_CONFIG = OrderedDict([
    ("december", {
        "start_date": date(2025, 12, 1),
        "sheet_name": "EdycjaGrudzien",
        "participants": PARTICIPANTS_DECEMBER,
        "is_manually_closed": True,
        "is_hidden": True
    }),
    ("january", {
        "start_date": date(2026, 1, 1),
        "sheet_name": "EdycjaStyczen",
        "participants": PARTICIPANTS_JANUARY,
        "is_manually_closed": True,
        "is_hidden": True
    }),
    ("february", {
        "start_date": date(2026, 2, 1),
        "sheet_name": "EdycjaLuty",
        "participants": PARTICIPANTS_FEBRUARY,
        "is_manually_closed": True,
        "is_hidden": True  # Ukryto - wyniki są w statystykach
    }),
    ("march", {
        "start_date": date(2026, 3, 1),
        "sheet_name": "EdycjaMarzec",
        "participants": PARTICIPANTS_MARCH,
        "is_manually_closed": False,
        "is_hidden": False
    }),
    ("april", {  # === NOWA EDYCJA ===
        "start_date": date(2026, 4, 1),
        "sheet_name": "EdycjaKwiecien",
        "participants": PARTICIPANTS_APRIL,
        "is_manually_closed": False,  # Otwarta
        "is_hidden": False
    }),
])

CONFIG_FILE_PATH = 'config_override.json'

def save_config_to_json(config_dict):
    """Zapisuje aktualną konfigurację do pliku JSON, konwertując daty na stringi."""
    serializable_config = {}
    for key, val in config_dict.items():
        serializable_config[key] = val.copy()
        if isinstance(val['start_date'], date):
            serializable_config[key]['start_date'] = val['start_date'].isoformat()
            
    try:
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(serializable_config, f, indent=4)
        return True
    except Exception as e:
        print(f"Błąd zapisu configu: {e}")
        return False

def load_config_with_overrides():
    """Ładuje konfigurację, nadpisując domyślną wersję danymi z JSON (jeśli istnieje)."""
    current_config = DEFAULT_EDITIONS_CONFIG.copy()
    
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                saved_config = json.load(f)
            
            for key, val in saved_config.items():
                if key in current_config:
                    if 'is_manually_closed' in val:
                        current_config[key]['is_manually_closed'] = val['is_manually_closed']
                    if 'participants' in val:
                        current_config[key]['participants'] = val['participants']
                    if 'is_hidden' in val:
                        current_config[key]['is_hidden'] = val.get('is_hidden', False)
        except Exception as e:
            print(f"Błąd odczytu configu JSON: {e}")
            
    return current_config

EDITIONS_CONFIG = load_config_with_overrides()
