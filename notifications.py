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
        st.error(f"❌ Błąd secrets: {e}")
        return False

    msg = MIMEMultipart()
    msg['From'] = f"Poprzeczka <{sender_email}>"
    msg['To'] = ", ".join(recipients) if isinstance(recipients, list) else recipients
    msg['Subject'] = subject

    styled_html = f"""
    <html>
    <body style="font-family: sans-serif; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px; overflow: hidden;">
            <div style="background-color: #2e7d32; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">System Poprzeczka</h2>
            </div>
            <div style="padding: 20px;">{html_content}</div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(styled_html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Błąd SMTP: {e}")
        return False

def check_and_send_notifications(conn, data, edition_key, lang='pl'):
    cfg = EDITIONS_CONFIG.get(edition_key)
    if not cfg: return

    try:
        subscribers = conn.read(worksheet="Emails", ttl=0)
    except:
        return

    participants = cfg['participants']
    max_day = int(data['Day'].max()) if not data.empty else 0
    
    # Pobieramy ranking (zgodnie z Twoim page_current_ranking.py)
    ranking_df, _ = calculate_ranking(data, max_day, lang, participants)

    # OBLICZANIE SERII PORAŻEK (Logika identyczna z Twoją)
    # Musimy to przeliczyć, bo ranking_df nie zwraca tej kolumny
    streak_info = {}
    for p in participants:
        p_data = data[data['Participant'] == p].sort_values('Day')
        current_streak = 0
        for d in range(1, max_day + 1):
            day_row = p_data[p_data['Day'] == d]
            status = day_row['Status'].iloc[0] if not day_row.empty else "Brak danych"
            if status != "Zaliczone":
                current_streak += 1
            else:
                current_streak = 0
            if current_streak >= 3: break
        streak_info[p] = current_streak

    # Sprawdzanie kompletności dnia dla aktywnych
    active_players = ranking_df[ranking_df['Status'] != 'Out']['Participant'].tolist()
    current_day_data = data[data['Day'] == max_day]
    reported = current_day_data['Participant'].unique()
    is_complete = all(p in reported for p in active_players)

    # 1. ALERT OSTRZEGAWCZY (Przy 2 porażkach z rzędu)
    for p, streak in streak_info.items():
        if streak == 2:
            # Sprawdź czy to nowy wpis (tylko dla osoby która właśnie wysłała)
            sub = subscribers[subscribers['Participant'] == p]
            if not sub.empty and str(sub.iloc[0]['Alert_Warning']).upper() in ['TRUE', 'YES']:
                send_email(
                    sub.iloc[0]['Email'], 
                    "⚠️ Druga porażka z rzędu!", 
                    f"Cześć <b>{p}</b>, uważaj! Masz 2 porażki z rzędu. Trzecia oznacza koniec gry."
                )

    # 2. NEWSLETTER (Na koniec dnia)
    if is_complete:
        sent_key = f"sent_{edition_key}_{max_day}"
        if sent_key not in st.session_state:
            rows = ""
            for i, row in ranking_df.iterrows():
                p = row['Participant']
                streak = streak_info.get(p, 0)
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                # Pokazujemy X tylko dla porażek Z RZĘDU
                fails_display = "❌" * streak if row['Status'] != 'Out' else "ELIMINACJA"
                
                rows += f"<tr><td>{medal}</td><td>{p}</td><td>{row['Total_Score']}</td><td>{fails_display}</td></tr>"

            table = f"""
            <table border="1" style="width:100%; border-collapse: collapse; text-align: left;">
                <tr style="background:#f4f4f4;"><th>Poz.</th><th>Uczestnik</th><th>Pkt</th><th>Seria</th></tr>
                {rows}
            </table>"""
            
            recipients = subscribers[subscribers['Alert_Results'].astype(str).str.upper().isin(['TRUE', 'YES'])]['Email'].tolist()
            if recipients:
                if send_email(recipients, f"🏁 Wyniki Etapu {max_day}", f"<h3>Podsumowanie dnia:</h3>{table}"):
                    st.session_state[sent_key] = True
