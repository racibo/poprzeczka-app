# config.py
from datetime import date, datetime
from collections import OrderedDict
import json
import os

# === LISTY UCZESTNIKÓW (BAZOWE) ===
PARTICIPANTS_LIST_BASE = [
    "new.things", "cezary-io", "manuvert", "racibo", 
    "ervin-lemark", "merthin", "sk1920", "edycu007", "ataraksja", 
    "homesteadlt", "browery", "fredkese", "marianomariano", "patif2025"
]

# Listy dla konkretnych edycji
PARTICIPANTS_DECEMBER = [p for p in PARTICIPANTS_LIST_BASE if p != "patif2025"]

# === ZMIANA 1: USUNIĘCIE OSÓB ZE STYCZNIA ===
PARTICIPANTS_JANUARY = [
    p for p in PARTICIPANTS_LIST_BASE 
    if p not in ["patif2025", "ataraksja"]
]

PARTICIPANTS_FEBRUARY = [p for p in PARTICIPANTS_LIST_BASE if p not in ["patif2025", "ataraksja"]]

SUBMITTER_LIST = sorted(list(set(PARTICIPANTS_LIST_BASE + ["poprzeczka (Admin)"])))
ALL_POSSIBLE_PARTICIPANTS = sorted(list(set(PARTICIPANTS_DECEMBER + PARTICIPANTS_JANUARY + PARTICIPANTS_FEBRUARY)))

# ID folderu na Google Drive
GOOGLE_DRIVE_FOLDER_ID = "1b-mUxDmKEUoOyLtTePeb7RaJWGfO_Xre"

# === DEFINICJE MIESIĘCY ===
MONTH_NAMES = {
    "november": {"pl": "Listopad", "en": "November", "icon": "🍂", "url_param_pl": "listopad", "url_param_en": "november"},
    "december": {"pl": "Grudzień", "en": "December", "icon": "❄️", "url_param_pl": "grudzien", "url_param_en": "december"},
    "january":  {"pl": "Styczeń",  "en": "January",  "icon": "⛄", "url_param_pl": "styczen",  "url_param_en": "january"},
    "february": {"pl": "Luty",     "en": "February", "icon": "💘", "url_param_pl": "luty",     "url_param_en": "february"},
}

# === DOMYŚLNA KONFIGURACJA (Hardcoded) ===
DEFAULT_EDITIONS_CONFIG = OrderedDict([
    ("december", {
        "start_date": date(2025, 12, 1),
        "sheet_name": "EdycjaGrudzien",
        "participants": PARTICIPANTS_DECEMBER,
        "is_manually_closed": True,
        "is_hidden": True # Nowa flaga do ukrywania w menu
    }),
    ("january", {
        "start_date": date(2026, 1, 1),
        "sheet_name": "EdycjaStyczen",
        "participants": PARTICIPANTS_JANUARY,
        "is_manually_closed": True,
        "is_hidden": False
    }),
    ("february", {
        "start_date": date(2026, 2, 1),
        "sheet_name": "EdycjaLuty",
        "participants": PARTICIPANTS_FEBRUARY,
        "is_manually_closed": False,
        "is_hidden": False
    }),
])

CONFIG_FILE_PATH = 'config_override.json'

def save_config_to_json(config_dict):
    """Zapisuje aktualną konfigurację do pliku JSON, konwertując daty na stringi."""
    serializable_config = {}
    for key, val in config_dict.items():
        serializable_config[key] = val.copy()
        # Konwersja daty na string ISO
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
                    # Aktualizujemy pola dynamiczne
                    if 'is_manually_closed' in val:
                        current_config[key]['is_manually_closed'] = val['is_manually_closed']
                    if 'participants' in val:
                        current_config[key]['participants'] = val['participants']
                    if 'is_hidden' in val:
                        current_config[key]['is_hidden'] = val.get('is_hidden', False)
                    # Opcjonalnie data startu (jeśli zmieniasz)
                    # if 'start_date' in val:
                    #     current_config[key]['start_date'] = date.fromisoformat(val['start_date'])
        except Exception as e:
            print(f"Błąd odczytu configu JSON: {e}")
            
    return current_config

# Ładujemy konfigurację przy starcie
EDITIONS_CONFIG = load_config_with_overrides()


