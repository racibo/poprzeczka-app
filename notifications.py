import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import pandas as pd
from config import EDITIONS_CONFIG
from page_current_ranking import calculate_ranking
from data_loader import load_google_sheet_data, process_raw_data
from google_connect import connect_to_google_sheets

# --- KONFIGURACJA KOLUMN SUBSKRYPCJI ---
# Nazwy kolumn w arkuszu 'Emails'
COL_ALERT_RISK = 'Alert_Risk'     # Dla ostrzeżeń indywidualnych (Ryzyko/Eliminacja)
COL_ALERT_RESULTS = 'Alert_Results' # Dla rankingu ogólnego

def send_email(recipients, subject, html_content):
    """Bezpieczne wysyłanie e-maili przez SMTP."""
    try:
        conf = st.secrets["email"]
        msg = MIMEMultipart()
        msg['From'] = f"Poprzeczka App <{conf['sender']}>"
        msg['Subject'] = subject
        
        if isinstance(recipients, list):
            msg['To'] = conf['sender']
            msg['Bcc'] = ", ".join(recipients)
            dest = recipients + [conf['sender']]
        else:
            msg['To'] = recipients
            dest = [recipients]

        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP(conf["smtp_server"], conf["smtp_port"])
        server.starttls()
        server.login(conf["sender"], conf["password"])
        server.sendmail(conf["sender"], dest, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ SMTP Error: {e}")
        return False

def is_failure(status):
    """Pomocnicza funkcja sprawdzająca czy status oznacza niezaliczenie."""
    if not status: return True # Brak statusu to też brak zaliczenia
    return str(status).strip().lower() not in ["zaliczone", "completed", "done", "ok", "yes", "tak"]

def check_and_send_notifications(conn, edition_key, current_user, current_day, current_status):
    debug = st.expander("🕵️ DEBUG POWIADOMIEŃ", expanded=True)
    
    # 0. Zapewnienie połączenia
    if conn is None:
        try: conn = connect_to_google_sheets()
        except: return

    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg: return

    try:
        # 1. Pobranie danych
        df_raw = load_google_sheet_data(conn, cfg['sheet_name'])
        sub_df = load_google_sheet_data(conn, "Emails")
        
        expected_cols = ['Participant', 'Day', 'Status', 'Timestamp', 'Notes']
        processed_data, max_d_raw, success = process_raw_data(df_raw, 'pl', expected_cols, cfg['sheet_name'])
        
        if not success:
            debug.error("Błąd przetwarzania danych.")
            return

        # ==============================================================================
        # CZĘŚĆ 1: POWIADOMIENIA INDYWIDUALNE (RYZYKO vs ELIMINACJA)
        # Dotyczy TYLKO osoby, która właśnie klika "Zapisz" (current_user)
        # ==============================================================================
        
        if current_user and current_day and current_status:
            
            # Sprawdzamy status dzisiejszy
            if is_failure(current_status):
                c_day = int(current_day)
                prev_day = c_day - 1
                prev_prev_day = c_day - 2
                
                # Pobieramy historię użytkownika
                user_history = processed_data.get(current_user, {})
                
                # Sprawdzamy dzień wcześniejszy (d-1)
                prev_status_val = user_history.get(prev_day)
                
                if prev_day > 0 and prev_status_val and is_failure(prev_status_val):
                    # Mamy już 2 porażki z rzędu (Dziś + Wczoraj).
                    # TERAZ SPRAWDZAMY 3. KROK WSTECZ (d-2)
                    
                    is_elimination = False
                    prev_prev_status_val = user_history.get(prev_prev_day)
                    
                    if prev_prev_day > 0 and prev_prev_status_val and is_failure(prev_prev_status_val):
                        # 3 porażki z rzędu!
                        is_elimination = True
                    
                    # --- Przygotowanie wysyłki ---
                    col_nick = next((c for c in sub_df.columns if c.lower() in ['nick', 'participant', 'uczestnik', 'user']), None)
                    col_email = next((c for c in sub_df.columns if c.lower() in ['email', 'e-mail', 'mail']), None)
                    col_risk_sub = next((c for c in sub_df.columns if c in [COL_ALERT_RISK, 'Alert_Risk']), None)

                    if col_nick and col_email:
                        user_row = sub_df[sub_df[col_nick].astype(str).str.strip() == str(current_user).strip()]
                        
                        if not user_row.empty:
                            user_email = user_row.iloc[0][col_email]
                            
                            # Sprawdzamy zgodę (domyślnie wysyłamy, chyba że wyraźnie FALSE)
                            should_send = True
                            if col_risk_sub:
                                val = str(user_row.iloc[0][col_risk_sub]).upper()
                                if val in ['FALSE', 'NO', 'NIE', '0']:
                                    should_send = False
                            
                            if should_send and user_email:
                                if is_elimination:
                                    # --- SCENARIUSZ ELIMINACJI (3x Fail) ---
                                    debug.warning(f"⛔ {current_user}: Wykryto 3 porażki z rzędu. Wysyłam info o eliminacji.")
                                    subject = f"ℹ️ Poprzeczka: Ważna informacja o statusie ({current_user})"
                                    html_content = f"""
                                    <html><body style="font-family: Arial, sans-serif; color: #333;">
                                        <h2 style="color: #d32f2f;">⛔ Status Uczestnictwa</h2>
                                        <p>Cześć <b>{current_user}</b>,</p>
                                        <p>Do bazy danych wpłynął Twój wynik za etap {c_day}. System odnotował <b>3 niezaliczone etapy z rzędu</b>:</p>
                                        <ul style="color: #555;">
                                            <li>Etap {prev_prev_day}: ❌ Niezaliczone</li>
                                            <li>Etap {prev_day}: ❌ Niezaliczone</li>
                                            <li>Etap {c_day}: ❌ Niezaliczone (Dzisiaj)</li>
                                        </ul>
                                        <p>Zgodnie z zasadami, oznacza to zakończenie rywalizacji w bieżącej edycji.</p>
                                        <p style="background-color: #fff3e0; padding: 15px; border-left: 5px solid #ff9800;">
                                            <b>⚠️ To pomyłka?</b><br>
                                            Jeśli wprowadzono błędne dane, możesz je natychmiast skorygować w swoim formularzu na stronie aplikacji. 
                                            System automatycznie przeliczy Twój status po poprawieniu wyniku.
                                        </p>
                                        <p><a href="https://poprzeczka.streamlit.app" style="color: #d32f2f; font-weight: bold;">Przejdź do formularza w aplikacji</a></p>
                                    </body></html>
                                    """
                                else:
                                    # --- SCENARIUSZ RYZYKA (2x Fail) ---
                                    debug.warning(f"⚠️ {current_user}: Wykryto 2 porażki z rzędu. Wysyłam ostrzeżenie.")
                                    subject = f"⚠️ Poprzeczka: Ryzyko braku zaliczenia ({current_user})"
                                    html_content = f"""
                                    <html><body style="font-family: Arial, sans-serif; color: #333;">
                                        <h2 style="color: #f57c00;">⚠️ Ostrzeżenie o wynikach</h2>
                                        <p>Cześć <b>{current_user}</b>,</p>
                                        <p>Odnotowaliśmy <b>drugi niezaliczony etap z rzędu</b> (Etapy: {prev_day} i {c_day}).</p>
                                        <p>To tylko przypomnienie: kolejny niezaliczony etap (trzeci z rzędu) będzie skutkował automatyczną eliminacją.</p>
                                        <p>Sprawdź, czy wszystko się zgadza w Twoim dzienniku aktywności:</p>
                                        <p><a href="https://poprzeczka.streamlit.app" style="background-color: #f57c00; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Sprawdź swoje wyniki</a></p>
                                    </body></html>
                                    """

                                if send_email(user_email, subject, html_content):
                                    debug.success(f"Powiadomienie indywidualne wysłane do: {current_user}")

        # ==============================================================================
        # CZĘŚĆ 2: POWIADOMIENIE O KOMPLECIE (OFICJALNY RANKING)
        # ==============================================================================
        
        participants = cfg['participants']
        found_complete_day = None
        
        try: start_search = int(max_d_raw)
        except: start_search = 1

        for d in range(start_search, 0, -1):
            if d > 1:
                _, prev_elim_map = calculate_ranking(processed_data, d-1, 'pl', participants, ranking_type='official')
            else:
                prev_elim_map = {}

            # Czekamy na aktywnych (nie OUT dzień wcześniej)
            active_players_in_round = [p for p in participants if not prev_elim_map.get(p, False)]
            
            missing_active = []
            for p in active_players_in_round:
                if d not in processed_data.get(p, {}):
                    missing_active.append(p)
            
            if len(missing_active) == 0:
                found_complete_day = d
                break
        
        if found_complete_day:
            ranking_df, elim_map = calculate_ranking(processed_data, found_complete_day, 'pl', participants, ranking_type='official')
            
            rows = ""
            c = ranking_df.columns
            col_rank, col_part, col_score = c[0], c[1], c[2]
            
            for _, row in ranking_df.iterrows():
                p_name = row[col_part]
                is_out = elim_map.get(p_name, False)
                style = "color: #999; text-decoration: line-through;" if is_out else "color: #333;"
                status_txt = " <span style='color:red; font-size:0.8em;'>(OUT)</span>" if is_out else ""
                
                rows += f"""<tr>
                    <td style='padding:8px; border-bottom:1px solid #ddd;'>{row[col_rank]}.</td>
                    <td style='padding:8px; border-bottom:1px solid #ddd; {style}'>{p_name}{status_txt}</td>
                    <td style='padding:8px; border-bottom:1px solid #ddd; text-align:center;'>{row[col_score]}</td>
                </tr>"""

            html_ranking = f"""
            <html><body style="font-family: Arial, sans-serif;">
                <div style="background-color: #f4f4f4; padding: 20px;">
                    <h2 style="color: #2e7d32; margin-top:0;">🏁 Oficjalne Wyniki - Etap {found_complete_day}</h2>
                    <p>Wszystkie wyniki dla etapu {found_complete_day} są już dostępne.</p>
                    <table style="border-collapse: collapse; width: 100%; max-width: 500px; background: white; border: 1px solid #ddd;">
                        <tr style="background-color: #e8f5e9; border-bottom: 2px solid #4CAF50;">
                            <th style="padding: 10px; text-align:left;">Poz.</th>
                            <th style="padding: 10px; text-align:left;">Uczestnik</th>
                            <th style="padding: 10px; text-align:center;">Pkt</th>
                        </tr>
                        {rows}
                    </table>
                    <br>
                    <a href="https://poprzeczka.streamlit.app" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">Pełny Ranking</a>
                </div>
            </body></html>
            """
            
            # Pobieramy subskrybentów rankingu
            col_res_sub = next((c for c in sub_df.columns if c in [COL_ALERT_RESULTS, 'Alert_Results']), None)
            col_email = next((c for c in sub_df.columns if c.lower() in ['email', 'e-mail', 'mail']), None)
            
            if col_res_sub and col_email:
                emails_to_send = sub_df[sub_df[col_res_sub].astype(str).str.upper().isin(['TRUE', 'YES', 'TAK', '1'])]
                recipients = emails_to_send[col_email].dropna().tolist()
                
                if recipients:
                    # Tutaj logika: zazwyczaj nie chcemy wysyłać tego samego maila wiele razy
                    # Ale w trybie prostym wysyłamy przy każdym "dotknięciu" kompletu.
                    # Możesz to ograniczyć w przyszłości.
                    if send_email(recipients, f"🏁 Poprzeczka: Wyniki Etapu {found_complete_day}", html_ranking):
                        debug.success(f"Newsletter ogólny wysłany do {len(recipients)} osób.")

    except Exception as e:
        debug.error(f"Błąd krytyczny: {e}")
