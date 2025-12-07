import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from translations import _t

def calculate_records_history(df):
    """
    Analizuje historię chronologicznie, aby ustalić, kto i kiedy pobił rekord.
    Zwraca słowniki z informacjami o rekordach dla konkretnych edycji.
    """
    # Sortujemy od najstarszej do najnowszej
    df_sorted = df.sort_values('miesiac')
    
    # Słowniki do przechowywania stanu
    user_pbs = {} # {user: current_best_score}
    overall_record = 0
    
    # Słownik wynikowy: {(user, edycja_str): [lista_odznak]}
    badges_map = {}
    
    # Iterujemy po unikalnych edycjach
    unique_editions = df_sorted['miesiac_rok_str'].unique()
    # Sortujemy edycje po dacie, bo unique() bierze w kolejności występowania
    unique_editions = sorted(unique_editions, key=lambda x: datetime.strptime(x, '%m.%Y'))

    for edition in unique_editions:
        edition_df = df_sorted[df_sorted['miesiac_rok_str'] == edition]
        
        # Sprawdzamy wyniki w tej edycji
        for idx, row in edition_df.iterrows():
            user = row['uczestnik']
            score = row['rezultat_numeric']
            
            if pd.isna(score):
                continue
                
            badges = []
            
            # 1. Sprawdzenie Rekordu Życiowego (PB)
            current_pb = user_pbs.get(user, 0)
            if score > current_pb:
                user_pbs[user] = score
                # Jeśli to nie jest pierwszy wynik (0), to jest to nowe PB
                # (opcjonalnie można uznać pierwszy wynik za PB, tu uznajemy pobicie)
                if current_pb > 0:
                    badges.append("PB")
            
            # 2. Sprawdzenie Rekordu Rozgrywek (WR)
            if score > overall_record:
                overall_record = score
                badges.append("WR")
            
            # Zapisujemy odznaki dla tego wpisu
            if badges:
                badges_map[(user, edition)] = badges

    return badges_map, overall_record

def render_edition_table(edition_df, badges_map, edition_str, lang):
    """Wyświetla tabelę wyników dla konkretnej edycji."""
    
    # Sortowanie: Miejsce (rosnąco), potem Wynik (malejąco)
    df_display = edition_df.sort_values(by=['miejsce', 'rezultat_numeric'], ascending=[True, False]).copy()
    
    data_for_table = []
    
    for _, row in df_display.iterrows():
        user = row['uczestnik']
        rank = row['miejsce']
        score = row['rezultat_numeric']
        
        # Pobierz odznaki
        badges = badges_map.get((user, edition_str), [])
        
        # Budowanie wyglądu uczestnika z ikonkami
        participant_display = f"@{user}"
        if "WR" in badges:
            participant_display += " 🏆🔥 (REKORD)"
        elif "PB" in badges:
            participant_display += " ⭐ (PB)"
            
        # Formatowanie wyniku
        score_display = f"{score:.0f}" if pd.notna(score) else "—"
        
        # Formatowanie miejsca
        rank_display = f"{int(rank)}." if pd.notna(rank) else "—"
        
        data_for_table.append({
            "Miejsce": rank_display,
            "Uczestnik": participant_display,
            "Wynik": score_display
        })
        
    st.dataframe(
        pd.DataFrame(data_for_table),
        column_config={
            "Miejsce": st.column_config.TextColumn("Miejsce", width="small"),
            "Uczestnik": st.column_config.TextColumn("Uczestnik", width="large"),
            "Wynik": st.column_config.TextColumn("Wynik", width="small"),
        },
        hide_index=True,
        width='stretch' # ✅ Poprawiona linia: zamiast use_container_width=True
    )

def show_chronicle(df, lang):
    """Główna funkcja wyświetlająca kronikę."""
    
    # 1. Przygotowanie danych
    if df.empty:
        st.info("Brak danych historycznych.")
        return

    # Tylko wiersze z wynikiem (żeby nie psuć obliczeń rekordów)
    df_clean = df.dropna(subset=['rezultat_numeric']).copy()
    
    # Obliczamy historię rekordów
    badges_map, current_wr = calculate_records_history(df_clean)
    
    # 2. Nagłówek i Legenda
    st.markdown("### 📜 Kronika Rozgrywek (Hall of Fame)")
    st.caption("Kompletna historia wszystkich edycji, podzielona na lata.")
    
    col_leg1, col_leg2 = st.columns(2)
    with col_leg1:
        st.info("🏆🔥 **(REKORD)** – Ustanowiono nowy rekord wszech czasów w danej chwili.")
    with col_leg2:
        st.info("⭐ **(PB)** – Uczestnik pobił swój dotychczasowy rekord życiowy.")

    st.markdown("---")

    # 3. Grupowanie edycji po latach
    # Dodajemy kolumnę 'year'
    df_clean['year'] = df_clean['miesiac'].dt.year
    unique_years = sorted(df_clean['year'].unique(), reverse=True) # Od najnowszego
    
    if not unique_years:
        st.warning("Brak dat w pliku historycznym.")
        return

    # 4. Tworzenie zakładek (Tabs) dla lat
    tabs = st.tabs([str(y) for y in unique_years])
    
    for tab, year in zip(tabs, unique_years):
        with tab:
            # Filtrujemy dane dla danego roku
            df_year = df_clean[df_clean['year'] == year]
            
            # Pobieramy unikalne edycje w tym roku, sortujemy malejąco (od grudnia do stycznia)
            editions_in_year = sorted(
                df_year['miesiac_rok_str'].unique(), 
                key=lambda x: datetime.strptime(x, '%m.%Y'), 
                reverse=True
            )
            
            for edition_str in editions_in_year:
                # Dane dla tej konkretnej edycji
                ed_df = df_year[df_year['miesiac_rok_str'] == edition_str]
                
                # Zliczamy statystyki edycji
                winner = ed_df.loc[ed_df['miejsce'] == 1, 'uczestnik'].values
                winner_str = ", ".join(winner) if len(winner) > 0 else "Brak"
                max_score = ed_df['rezultat_numeric'].max()
                count_participants = len(ed_df)
                
                # Nazwa miesiąca (ładniejsza)
                try:
                    date_obj = datetime.strptime(edition_str, '%m.%Y')
                    month_name = date_obj.strftime('%B') # Angielska nazwa
                    # Szybkie tłumaczenie na PL jeśli trzeba, lub zostawiamy cyfry
                    month_display = f"{edition_str}" 
                except:
                    month_display = edition_str

                # Ekspander dla edycji
                label = f"🗓️ {month_display} | 🥇 {winner_str} | 👥 {count_participants} os. | Max: {max_score:.0f}"
                
                with st.expander(label, expanded=False):
                    render_edition_table(ed_df, badges_map, edition_str, lang)
