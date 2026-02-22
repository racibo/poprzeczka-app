import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import pandas as pd
from config import EDITIONS_CONFIG
from page_current_ranking import calculate_ranking

def send_email(recipients, subject, html_content):
    if not recipients:
        return False
        
    try:
        conf = st.secrets["email"]
        sender_email = conf["sender"]
        sender_password = conf["password"]
        smtp_server = conf["smtp_server"]
        smtp_port = conf["smtp_port"]
    except Exception as e:
        st.error(f"❌ Błąd konfiguracji secrets [email]: {e}")
        return False

    msg = MIMEMultipart()
    msg['From'] = f"Poprzeczka Bot <{sender_email}>"
    msg['Subject'] = subject
    
    # Obsługa listy odbiorców (BCC dla wielu, TO dla jednego)
    if isinstance(recipients, list) and len(recipients) > 1:
        msg['Bcc'] = ", ".join(recipients)
        dest_list = [sender_email] # Techniczny odbiorca "To"
    else:
        dest_list = recipients if isinstance(recipients, list) else [recipients]
        msg['To'] = dest_list[0]

    styled_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 10px; overflow: hidden;">
            <div style="background-color: #2e7d32; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">Poprzeczka</h2>
            </div>
            <div style="padding: 20px;">
                {html_content}
            </div>
            <div style="background-color: #f9f9f9; color: #888; padding: 10px; text-align: center; font-size: 12px; border-top: 1px solid #eee;">
                Wiadomość automatyczna.
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(styled_html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, dest_list, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Błąd serwera poczty (SMTP): {e}")
        return False

def check_and_send_notifications(conn, edition_key, current_user, current_day, current_status):
    """
    Wersja DEBUG - wyświetla logikę na ekranie.
    """
    
    # --- SEKCJA DEBUG UI ---
    debug_container = st.expander("🕵️ DEBUG POWIADOMIEŃ (Kliknij, aby rozwinąć)", expanded=True)
    
    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg:
        debug_container.error("Brak konfiguracji edycji.")
        return

    try:
        # Odczyt danych
        df_results = conn.read(worksheet=cfg['sheet_name'], ttl=0)
        df_emails = conn.read(worksheet="Emails", ttl=0)
        
        # Czyszczenie danych (kluczowe!)
        df_results['Participant'] = df_results['Participant'].astype(str).str.strip()
        df_results['Status'] = df_results['Status'].astype(str).str.strip()
        df_emails['Participant'] = df_emails['Participant'].astype(str).str.strip()
        
        # Normalizacja Dnia (int)
        try:
            current_day_int = int(current_day)
            df_results['Day'] = pd.to_numeric(df_results['Day'], errors='coerce').fillna(0).astype(int)
        except:
            current_day_int = 1
            debug_container.warning("⚠️ Problem z konwersją dnia na liczbę.")

    except Exception as e:
        debug_container.error(f"⚠️ Błąd odczytu danych: {e}")
        return

    # --- 1. OBLICZANIE RANKINGU I SERII ---
    # Używamy oficjalnej funkcji, ale musimy sami policzyć serię porażek (streak)
    participants_list = cfg['participants']
    ranking_df, _ = calculate_ranking(
        data=df_results, 
        max_day_reported=current_day_int, 
        lang='pl',
        participants_list=participants_list
    )
    
    # Obliczanie serii porażek "z rzędu" dla każdego gracza
    streak_map = {}
    for p in participants_list:
        p_history = df_results[df_results['Participant'] == p].sort_values('Day')
        # Filtrujemy tylko do bieżącego dnia włącznie
        p_history = p_history[p_history['Day'] <= current_day_int]
        
        current_streak = 0
        for _, row in p_history.iterrows():
            if row['Status'] != 'Zaliczone':
                current_streak += 1
            else:
                current_streak = 0 # Reset serii
        streak_map[p] = current_streak

    # --- 2. WARUNEK KOMPLETNOŚCI ---
    # Kto jest aktywny? (nie ma statusu 'Out' w rankingu)
    active_players_df = ranking_df[ranking_df['Status'] != 'Out']
    active_players_list = active_players_df['Participant'].tolist()
    
    # Kto zaraportował dzisiaj?
    day_entries = df_results[df_results['Day'] == current_day_int]
    reporters_today = day_entries['Participant'].unique().tolist()
    
    # Kogo brakuje?
    missing_players = [p for p in active_players_list if p not in reporters_today]
    is_complete = len(missing_players) == 0

    # --- DEBUG INFO ---
    debug_container.write(f"📅 **Analiza dla dnia:** {current_day_int}")
    debug_container.write(f"👥 **Aktywni gracze ({len(active_players_list)}):** {', '.join(active_players_list)}")
    debug_container.write(f"📝 **Zaraportowali dzisiaj:** {', '.join(reporters_today)}")
    
    if is_complete:
        debug_container.success("✅ Komplet wyników! Warunek spełniony.")
    else:
        debug_container.error(f"❌ Brak kompletu. Czekamy na: {', '.join(missing_players)}")

    # --- 3. WYSYŁKA MAILI (ALERT OSTRZEGAWCZY) ---
    # Wysyłamy, jeśli bieżący user ma serię dokładnie 2
    user_streak = streak_map.get(current_user, 0)
    
    if user_streak == 2:
        # Sprawdź czy user chce maila
        user_prefs = df_emails[df_emails['Participant'] == current_user]
        if not user_prefs.empty:
            wants_alert = str(user_prefs.iloc[0]['Alert_Warning']).upper() in ['TRUE', 'YES', 'PRAWDA']
            email_addr = user_prefs.iloc[0]['Email']
            
            if wants_alert and email_addr:
                debug_container.info(f"📤 Wysyłam OSTRZEŻENIE do {current_user} ({email_addr})...")
                subj = "⚠️ Ostrzeżenie: Druga porażka z rzędu!"
                body = f"""
                <h3 style='color: #d32f2f;'>Uwaga {current_user}!</h3>
                <p>To Twój drugi niezaliczony etap z rzędu (Seria: 2).</p>
                <p><b>Trzecia porażka z rzędu oznacza eliminację!</b></p>
                """
                if send_email([email_addr], subj, body):
                    debug_container.success("Ostrzeżenie wysłane.")
                else:
                    debug_container.error("Błąd wysyłki ostrzeżenia.")

    # --- 4. WYSYŁKA MAILI (NEWSLETTER ZBIORCZY) ---
    if is_complete and len(active_players_list) > 0:
        # Zabezpieczenie przed wielokrotną wysyłką w tej samej sesji
        # (W produkcji używamy st.session_state, tu w debugu pomijamy, żebyś mógł testować)
        
        debug_container.info("📧 Przygotowywanie Newslettera...")
        
        # Generowanie tabeli HTML
        rank_rows = ""
        for i, row in ranking_df.iterrows():
            p_name = row['Participant']
            p_score = row.get('Total_Score', 0) # Upewnij się, że nazwa kolumny pasuje do outputu calculate_ranking
            p_streak = streak_map.get(p_name, 0)
            
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
            streak_display = "❌" * p_streak if p_streak > 0 else ""
            if row['Status'] == 'Out': streak_display = "ELIMINACJA"
            
            bg = "#fffde7" if i <= 2 else "transparent"
            
            rank_rows += f"""
            <tr style="background-color: {bg};">
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{medal}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><b>{p_name}</b></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{p_score}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center; color: #d32f2f;">{streak_display}</td>
            </tr>"""

        rank_table = f"""
        <h3>Podsumowanie Dnia {current_day_int}</h3>
        <table style="width: 100%; border-collapse: collapse; font-family: sans-serif;">
            <thead style="background-color: #2e7d32; color: white;">
                <tr>
                    <th style="padding: 10px;">Poz.</th>
                    <th style="padding: 10px; text-align: left;">Uczestnik</th>
                    <th style="padding: 10px;">Pkt</th>
                    <th style="padding: 10px;">Seria</th>
                </tr>
            </thead>
            <tbody>{rank_rows}</tbody>
        </table>
        """

        # Pobranie subskrybentów
        subscribers = df_emails[df_emails['Alert_Results'].astype(str).str.upper().isin(['TRUE', 'YES', 'PRAWDA'])]
        recipients_list = subscribers['Email'].dropna().unique().tolist()
        
        if recipients_list:
            debug_container.write(f"📨 Próba wysyłki do: {len(recipients_list)} osób: {recipients_list}")
            
            # WYSYŁKA WŁAŚCIWA
            success = send_email(recipients_list, f"🏁 Wyniki Etapu {current_day_int}", rank_table)
            
            if success:
                debug_container.success("✅ Newsletter wysłany pomyślnie!")
            else:
                debug_container.error("❌ Błąd funkcji send_email (sprawdź logi wyżej).")
        else:
            debug_container.warning("⚠️ Brak subskrybentów (sprawdź kolumnę Alert_Results w arkuszu Emails).")
