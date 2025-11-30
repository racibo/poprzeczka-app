import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime
from translations import _t
from data_loader import load_historical_data_from_json

def show_historical_stats(lang):
    st.header(_t('title', lang))
    
    df = load_historical_data_from_json() 

    if df.empty:
        st.info("Brak danych historycznych do wyświetlenia.")
        st.stop()
        
    participant_col_name = _t('participant', lang)

    # === SIDEBAR FILTERS ===
    st.sidebar.markdown("---")
    st.sidebar.header(_t('sidebar_header', lang))

    # Zabezpieczenie: max_value nie może być mniejsze niż min_value (1)
    max_counts = int(df['uczestnik'].value_counts().max()) if not df.empty else 1
    if max_counts < 1: max_counts = 1

    min_editions_count = st.sidebar.slider(
        _t('min_editions', lang),
        min_value=1,
        max_value=max_counts,
        value=1,
        key="hist_min_editions"
    )

    # Wybieramy tylko tych, którzy mają jakiekolwiek wyniki (nie tylko PAUZA)
    df_active = df.dropna(subset=['rezultat_numeric'])
    if df_active.empty:
        st.warning(_t('no_data_selected', lang))
        st.stop()

    user_counts = df_active['uczestnik'].value_counts()
    eligible_users = user_counts[user_counts >= min_editions_count].index.tolist()
    eligible_df = df[df['uczestnik'].isin(eligible_users)]

    if eligible_df.empty:
        st.warning(_t('no_data_selected', lang))
        st.stop()

    all_users_sorted = sorted(eligible_df['uczestnik'].unique())
    selected_users_all = st.sidebar.checkbox(_t('select_all_users', lang), value=True, key="hist_all_users")
    
    if selected_users_all:
        selected_users = all_users_sorted
    else:
        default_sel = all_users_sorted[:5] if len(all_users_sorted) > 5 else all_users_sorted
        selected_users = st.sidebar.multiselect(
            _t('select_users', lang),
            all_users_sorted,
            default=default_sel,
            key="hist_select_users"
        )

    period_option_labels = [
        _t('all_editions', lang), 
        _t('last_n_editions', lang, ''), 
        _t('manual_select', lang)
    ]
    period_option = st.sidebar.radio(
        _t('select_period', lang),
        options=period_option_labels,
        index=0,
        key="hist_period"
    )

    filtered_df = eligible_df[eligible_df['uczestnik'].isin(selected_users)].copy()

    # --- OBSŁUGA FILTRÓW CZASU ---
    if period_option == _t('last_n_editions', lang, ''):
        n_max = int(filtered_df['edycja_nr'].max()) if not filtered_df.empty else 1
        
        # NAPRAWA BŁĘDU SLIDERA: Wyświetlamy slider tylko jeśli jest co wybierać
        if n_max > 1:
            n_val = min(12, n_max)
            n_editions = st.sidebar.slider(
                _t('last_n_editions', lang, n_val), 
                min_value=1, 
                max_value=n_max, 
                value=n_val, 
                key="hist_n_editions"
            )
        else:
            n_editions = 1
            
        if not filtered_df.empty:
            max_edycja_nr = filtered_df['edycja_nr'].max()
            min_edycja_nr = max_edycja_nr - n_editions + 1
            filtered_df = filtered_df[filtered_df['edycja_nr'] >= min_edycja_nr]

    elif period_option == _t('manual_select', lang):
        if not filtered_df.empty:
            unique_months = filtered_df['miesiac'].dt.to_period('M').unique().to_timestamp()
            options_list = sorted(unique_months)
            
            if len(options_list) > 1:
                start_date, end_date = st.sidebar.select_slider(
                    _t('manual_select', lang),
                    options=options_list,
                    value=(options_list[0], options_list[-1]),
                    format_func=lambda x: x.strftime('%Y-%m'),
                    key="hist_slider"
                )
                filtered_df = filtered_df[(filtered_df['miesiac'] >= pd.to_datetime(start_date)) & (filtered_df['miesiac'] <= pd.to_datetime(end_date))]
            else:
                st.sidebar.info("Dostępny tylko jeden miesiąc danych.")
        else:
            st.sidebar.warning(_t('no_data_selected', lang))

    if filtered_df.empty or not selected_users:
        st.warning(_t('no_data_selected', lang))
        st.stop()

    chart_type_labels = [_t('results', lang), _t('positions', lang)]
    chart_type = st.sidebar.radio(_t('chart_type', lang), chart_type_labels, key="hist_chart_type")

    # === SZCZEGÓŁY UCZESTNIKA ===
    st.subheader(_t('user_details_header', lang))
    if len(selected_users) == 1:
        user = selected_users[0]
        user_df = filtered_df[filtered_df['uczestnik'] == user]
        st.markdown(f"#### {user}") 
        col1, col2, col3, col4 = st.columns(4)
        
        best_result_row = user_df.loc[user_df['rezultat_numeric'].idxmax()] if not user_df['rezultat_numeric'].isnull().all() else None
        col1.metric(label=_t('best_result', lang), value=f"{best_result_row['rezultat_raw']} ({best_result_row['miesiac_rok_str']})" if best_result_row is not None else "N/A")
        
        worst_result_row = user_df.loc[user_df['rezultat_numeric'].idxmin()] if not user_df['rezultat_numeric'].isnull().all() else None
        col2.metric(label=_t('worst_result', lang), value=f"{worst_result_row['rezultat_raw']} ({worst_result_row['miesiac_rok_str']})" if worst_result_row is not None else "N/A")
        
        best_position_row = user_df.loc[user_df['miejsce'].idxmin()] if not user_df['miejsce'].isnull().all() else None
        col3.metric(label=_t('best_position', lang), value=f"{int(best_position_row['miejsce'])} ({best_position_row['miesiac_rok_str']})" if best_position_row is not None else "N/A")
        
        worst_position_row = user_df.loc[user_df['miejsce'].idxmax()] if not user_df['miejsce'].isnull().all() else None
        col4.metric(label=_t('worst_position', lang), value=f"{int(worst_position_row['miejsce'])} ({worst_position_row['miesiac_rok_str']})" if worst_position_row is not None else "N/A")
    else:
        st.info(_t('select_single_user', lang))

    # === WYKRES PORÓWNAWCZY ===
    st.subheader(_t('comparison_chart_title_results', lang) if chart_type == _t('results', lang) else _t('comparison_chart_title_positions', lang))
    st.caption(_t('comparison_chart_note', lang))

    if chart_type == _t('results', lang):
        plot_df = filtered_df.copy()
        y_col, y_label = 'rezultat_numeric', _t('y_axis_results', lang)
        invert_yaxis = False
    else: 
        plot_df = filtered_df.copy()
        y_col, y_label = 'miejsce', _t('y_axis_positions', lang)
        invert_yaxis = True 

    if not plot_df.empty:
        fig, ax = plt.subplots(figsize=(16, 8))
        plt.style.use('dark_background')
        ax.set_facecolor('#0e1117')
        fig.patch.set_facecolor('#0e1117')

        for user in selected_users:
            user_data = plot_df[plot_df['uczestnik'] == user].sort_values('miesiac')
            user_data_for_plot = user_data.dropna(subset=[y_col])
            if not user_data_for_plot.empty:
                ax.plot(user_data_for_plot['miesiac'], user_data_for_plot[y_col], marker='o', linestyle='-', label=user)
                last_point = user_data_for_plot.iloc[-1]
                ax.text(last_point['miesiac'], last_point[y_col], f" {user}", verticalalignment='center', fontsize=9, color=ax.get_lines()[-1].get_color())

        ax.set_xlabel(_t('x_axis_month', lang))
        ax.set_ylabel(y_label)
        ax.legend().set_visible(False)
        ax.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        
        if invert_yaxis:
            ax.invert_yaxis() 

        plt.tight_layout()
        st.pyplot(fig) 
    else:
        st.info(_t('no_data_selected', lang))

    # === ZESTAWIENIE MIESIĘCZNE (TABELE) ===
    st.subheader(_t('monthly_summary', lang))
    st.write(_t('monthly_summary_desc', lang))

    summary_data = filtered_df.copy()
    if not summary_data.empty:
        sorted_columns = filtered_df['miesiac'].sort_values().dt.strftime('%m.%Y').unique()
        
        # Tabela Wyników
        if 'rezultat_raw' in summary_data.columns:
            monthly_results_pivot = summary_data.pivot_table(
                index='uczestnik',
                columns='miesiac_rok_str',
                values='rezultat_raw', 
                aggfunc='first'
            )
            monthly_results_pivot = monthly_results_pivot.fillna('—').replace({'None': '—', None: '—'})
            monthly_results_pivot = monthly_results_pivot.reindex(columns=sorted_columns)
            
            avg_result_sort = summary_data.groupby('uczestnik')['rezultat_numeric'].mean().sort_values(ascending=False)
            monthly_results_pivot = monthly_results_pivot.reindex(index=avg_result_sort.index)
            
            monthly_results_display = monthly_results_pivot.reset_index().rename(columns={'uczestnik': participant_col_name})
            st.dataframe(monthly_results_display, hide_index=True)
        else:
            st.error("Błąd danych: brak kolumny 'rezultat_raw'.")

        # Tabela Miejsc
        st.subheader(_t('monthly_summary_positions', lang))
        monthly_positions_pivot = summary_data.pivot_table(
            index='uczestnik',
            columns='miesiac_rok_str',
            values='miejsce',
            aggfunc=lambda x: f"{int(x.iloc[0])}" if pd.notna(x.iloc[0]) else '—'
        )
        monthly_positions_pivot = monthly_positions_pivot.fillna('—').replace({'None': '—', None: '—'})
        monthly_positions_pivot = monthly_positions_pivot.reindex(columns=sorted_columns)
        
        avg_pos_sort = summary_data.groupby('uczestnik')['miejsce'].mean().sort_values()
        monthly_positions_pivot = monthly_positions_pivot.reindex(index=avg_pos_sort.index)
        
        monthly_positions_display = monthly_positions_pivot.reset_index().rename(columns={'uczestnik': participant_col_name})
        st.dataframe(monthly_positions_display, hide_index=True)
    else:
        st.info(_t('no_data_selected', lang))

    # === WYŚCIG MEDALOWY ===
    st.subheader(_t('medal_race_title', lang))
    st.write(_t('medal_race_desc', lang))

    medal_range_labels = [
        _t('top_1', lang), _t('top_3', lang), _t('top_5', lang), 
        _t('top_10', lang), _t('custom_range', lang)
    ]
    medal_range_option = st.selectbox(
        _t('select_medal_range', lang),
        medal_range_labels,
        key="hist_medal_range"
    )

    min_medal_pos = 1
    max_medal_pos = 0

    if medal_range_option == _t('top_1', lang):
        max_medal_pos = 1
    elif medal_range_option == _t('top_3', lang):
        max_medal_pos = 3
    elif medal_range_option == _t('top_5', lang):
        max_medal_pos = 5
    elif medal_range_option == _t('top_10', lang):
        max_medal_pos = 10
    elif medal_range_option == _t('custom_range', lang):
        col_min, col_max = st.columns(2)
        with col_min:
            min_medal_pos = st.number_input(_t('min_medal_position', lang), min_value=1, value=1, step=1, key="hist_min_medal")
        with col_max:
            max_possible = int(df['miejsce'].max()) if not df['miejsce'].isnull().all() else 10
            max_input_val = max(max_possible, min_medal_pos)
            max_medal_pos = st.number_input(_t('max_medal_position', lang), min_value=min_medal_pos, value=max(min_medal_pos, 3), max_value=max_input_val, step=1, key="hist_max_medal")

    medals_history_df = df.dropna(subset=['miejsce'])

    if max_medal_pos > 0:
        medals_history_df = medals_history_df[
            (medals_history_df['miejsce'] >= min_medal_pos) & 
            (medals_history_df['miejsce'] <= max_medal_pos)
        ]

    if not medals_history_df.empty:
        medals_history_df = medals_history_df.sort_values('edycja_nr')
        medals_history_df['medal_count'] = 1
        
        medals_agg = medals_history_df.groupby(['uczestnik', 'edycja_nr'])['medal_count'].sum().reset_index()
        
        if not medals_agg.empty:
            all_editions = range(1, df['edycja_nr'].max() + 1)
            race_pivot = medals_agg.pivot_table(index='edycja_nr', columns='uczestnik', values='medal_count').reindex(all_editions).fillna(0).cumsum()
            
            race_long = race_pivot.melt(var_name='uczestnik', value_name='laczna_liczba_medali', ignore_index=False).reset_index()
            race_long_filtered = race_long[race_long['uczestnik'].isin(selected_users)]

            if not race_long_filtered.empty:
                fig_race, ax_race = plt.subplots(figsize=(16, 8))
                plt.style.use('dark_background')
                ax_race.set_facecolor('#0e1117')
                fig_race.patch.set_facecolor('#0e1117')

                for user in race_long_filtered['uczestnik'].unique():
                    user_data = race_long_filtered[race_long_filtered['uczestnik'] == user].sort_values('edycja_nr')
                    ax_race.plot(user_data['edycja_nr'], user_data['laczna_liczba_medali'], marker='o', linestyle='-', label=user)
                    if not user_data.empty:
                        last_point = user_data.iloc[-1]
                        ax_race.text(last_point['edycja_nr'], last_point['laczna_liczba_medali'], f" {user}", verticalalignment='center', fontsize=9, color=ax_race.get_lines()[-1].get_color())

                medal_title_text = ""
                if max_medal_pos == 1: medal_title_text = _t('cumulative_medals', lang, 1)
                elif medal_range_option == _t('custom_range', lang): medal_title_text = f"{_t('cumulative_medals', lang, '')} ({min_medal_pos}-{max_medal_pos})"
                else: medal_title_text = _t('cumulative_medals', lang, max_medal_pos)

                ax_race.set_title(_t('medal_race_title', lang))
                ax_race.set_xlabel(_t('x_axis_edition', lang))
                ax_race.set_ylabel(medal_title_text)
                ax_race.legend().set_visible(False)
                ax_race.grid(True, which='both', linestyle='--', linewidth=0.3)
                st.pyplot(fig_race)
            else:
                st.info(_t('no_data_selected', lang))
        else:
            st.info(_t('no_data_selected', lang))
    else:
        st.info(_t('no_data_selected', lang))

    # === HEATMAP ===
    st.subheader(_t('heatmap_title', lang))
    st.write(_t('heatmap_desc', lang))
    heatmap_df = filtered_df.dropna(subset=['miejsce'])
    if not heatmap_df.empty:
        heatmap_pivot = heatmap_df.pivot_table(index='uczestnik', columns='miesiac_rok_str', values='miejsce')
        sorted_cols = filtered_df['miesiac'].sort_values().dt.strftime('%m.%Y').unique()
        heatmap_pivot = heatmap_pivot.reindex(columns=sorted_cols)
        avg_pos_hm = heatmap_df.groupby('uczestnik')['miejsce'].mean().sort_values().index
        heatmap_pivot = heatmap_pivot.reindex(index=avg_pos_hm)

        fig_heatmap, ax_heatmap = plt.subplots(figsize=(18, max(6, len(heatmap_pivot.index) * 0.5)))
        sns.heatmap(
            heatmap_pivot, 
            annot=True, 
            fmt=".0f", 
            cmap="viridis_r", 
            linewidths=.5, 
            ax=ax_heatmap,
            cbar_kws={'label': _t('position', lang)}
        )
        ax_heatmap.set_title(_t('heatmap_title', lang))
        ax_heatmap.set_xlabel(_t('edition', lang))
        ax_heatmap.set_ylabel(_t('participant', lang))
        plt.xticks(rotation=45)
        st.pyplot(fig_heatmap)
    else:
        st.info(_t('no_data_selected', lang))

    # === SCATTER PLOT ===
    st.subheader(_t('scatter_plot_title', lang))
    st.write(_t('scatter_plot_desc', lang))

    scatter_df = filtered_df.dropna(subset=['rezultat_numeric', 'miejsce'])
    if not scatter_df.empty:
        fig_scatter, ax_scatter = plt.subplots(figsize=(16, 8))
        plt.style.use('dark_background')
        ax_scatter.set_facecolor('#0e1117')
        fig_scatter.patch.set_facecolor('#0e1117')

        unique_positions = sorted(scatter_df['miejsce'].dropna().unique())
        custom_palette = {}
        for pos in unique_positions:
            if pos == 1: custom_palette[pos] = 'red'
            elif pos == 2: custom_palette[pos] = 'orange'
            elif pos == 3: custom_palette[pos] = 'yellow'
            else:
                if len(unique_positions) > 3:
                    viridis_idx = int(np.interp(pos, [unique_positions[3], unique_positions[-1]], [0, len(sns.color_palette("viridis", n_colors=max(1, len(unique_positions) - 3))) - 1]))
                    custom_palette[pos] = sns.color_palette("viridis", n_colors=max(1, len(unique_positions) - 3))[viridis_idx]
                else:
                    custom_palette[pos] = 'gray'

        sns.scatterplot(
            data=scatter_df, x='miesiac', y='rezultat_numeric', hue='miejsce', 
            palette=custom_palette, size='miejsce', sizes=(50, 400), alpha=0.7, ax=ax_scatter, legend='full'
        )
        
        for user in selected_users:
            user_data = scatter_df[scatter_df['uczestnik'] == user].sort_values('miesiac')
            if not user_data.empty:
                for i, row in user_data.iterrows():
                    ax_scatter.text(row['miesiac'], row['rezultat_numeric'], f" {user}", verticalalignment='bottom', horizontalalignment='left', fontsize=7, color='white', alpha=0.8)

        ax_scatter.set_xlabel(_t('x_axis_month', lang))
        ax_scatter.set_ylabel(_t('y_axis_results', lang))
        ax_scatter.set_title(_t('scatter_plot_title', lang))
        ax_scatter.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        
        handles, labels = ax_scatter.get_legend_handles_labels()
        numeric_labels_with_handles = []
        for i, label_str in enumerate(labels[1:]): 
            try: numeric_labels_with_handles.append((int(float(label_str)), handles[i+1]))
            except ValueError: pass
        
        numeric_labels_with_handles.sort(key=lambda x: x[0])
        sorted_handles = [h for _, h in numeric_labels_with_handles]
        sorted_labels = [str(l) for l, _ in numeric_labels_with_handles]
        
        if handles:
            sorted_handles.insert(0, handles[0])
            sorted_labels.insert(0, labels[0])

        ax_scatter.legend(sorted_handles, sorted_labels, title=_t('position_legend', lang), bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        st.pyplot(fig_scatter)
    else:
        st.info(_t('no_data_selected', lang))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(_t('medal_classification_title', lang))
        all_positions_df = filtered_df.dropna(subset=['miejsce'])
        if not all_positions_df.empty:
            position_counts = pd.crosstab(all_positions_df['uczestnik'], all_positions_df['miejsce'])
            all_possible_positions = range(1, int(all_positions_df['miejsce'].max()) + 1)
            for pos in all_possible_positions:
                if pos not in position_counts.columns: position_counts[pos] = 0
            position_counts = position_counts.reindex(columns=sorted(position_counts.columns), fill_value=0)
            participation_count = filtered_df['uczestnik'].value_counts().rename(_t('total_participations', lang))
            position_counts = position_counts.join(participation_count)
            sort_cols = [col for col in position_counts.columns if isinstance(col, (int, np.integer))]
            position_counts = position_counts.sort_values(by=sort_cols, ascending=[False]*len(sort_cols))
            st.dataframe(position_counts.reset_index().rename(columns={'uczestnik': participant_col_name}), hide_index=True)
        else:
            st.info(_t('no_data_selected', lang))

    with col2:
        st.subheader(_t('medal_classification_classic_title', lang))
        if not all_positions_df.empty:
            top3_positions_df = all_positions_df[all_positions_df['miejsce'].isin([1, 2, 3])]
            if not top3_positions_df.empty:
                medal_counts = pd.crosstab(top3_positions_df['uczestnik'], top3_positions_df['miejsce'])
                for pos in [1, 2, 3]:
                    if pos not in medal_counts.columns: medal_counts[pos] = 0
                medal_counts = medal_counts[[1, 2, 3]]
                medal_counts.columns = ['1. miejsce', '2. miejsce', '3. miejsce']
                medal_counts[_t('total_medals_col', lang)] = medal_counts['1. miejsce'] + medal_counts['2. miejsce'] + medal_counts['3. miejsce']
                medal_counts = medal_counts.sort_values(by=['1. miejsce', '2. miejsce', '3. miejsce'], ascending=[False, False, False])
                st.dataframe(medal_counts.reset_index().rename(columns={'uczestnik': participant_col_name}), hide_index=True)
            else:
                st.info(_t('no_data_selected', lang))
        else:
            st.info(_t('no_data_selected', lang))

    st.subheader(_t('player_stats', lang))
    stats_df = df[df['uczestnik'].isin(eligible_users)].copy()
    if not stats_df.empty:
        agg_funcs = {
            'count': ('rezultat_numeric', 'count'),
            'mean_result': ('rezultat_numeric', 'mean'),
            'median_result': ('rezultat_numeric', 'median'),
            'min_result': ('rezultat_numeric', 'min'),
            'max_result': ('rezultat_numeric', 'max'),
            'mean_pos': ('miejsce', 'mean'),
            'median_pos': ('miejsce', 'median'),
            'best_pos': ('miejsce', 'min'),
        }
        player_stats = stats_df.groupby('uczestnik').agg(**agg_funcs).reset_index()
        player_stats.columns = [
            _t('participant', lang), _t('count_col', lang), 
            f"{_t('mean_col', lang)} ({_t('results', lang)})", f"{_t('median_col', lang)} ({_t('results', lang)})", f"{_t('min_col', lang)} ({_t('results', lang)})", f"{_t('max_col', lang)} ({_t('results', lang)})",
            f"{_t('mean_col', lang)} ({_t('positions', lang)})", f"{_t('median_col', lang)} ({_t('positions', lang)})", f"{_t('best_position', lang)}"
        ]
        col_mean_res = f"{_t('mean_col', lang)} ({_t('results', lang)})"
        col_mean_pos = f"{_t('mean_col', lang)} ({_t('positions', lang)})"
        player_stats[col_mean_res] = player_stats[col_mean_res].round(1)
        player_stats[col_mean_pos] = player_stats[col_mean_pos].round(1)
        st.dataframe(player_stats.sort_values(by=col_mean_pos), hide_index=True)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('participants_per_edition', lang))
    if not df.empty:
        # Tylko unikalni z wynikami
        df_active_only = df.dropna(subset=['rezultat_numeric'])
        participants_per_edition = df_active_only.groupby('miesiac_rok_str')['uczestnik'].nunique().reset_index()
        participants_per_edition.columns = ['miesiac_rok_str', _t('count_col', lang)] 
        participants_per_edition['miesiac'] = participants_per_edition['miesiac_rok_str'].apply(lambda x: datetime.strptime(x, '%m.%Y'))
        participants_per_edition = participants_per_edition.sort_values('miesiac').drop(columns='miesiac')
        
        st.dataframe(participants_per_edition.set_index('miesiac_rok_str')) 

        fig_participants, ax_participants = plt.subplots(figsize=(16, 6))
        plt.style.use('dark_background')
        ax_participants.set_facecolor('#0e1117')
        fig_participants.patch.set_facecolor('#0e1117')

        ax_participants.plot(
            participants_per_edition['miesiac_rok_str'],
            participants_per_edition[_t('count_col', lang)],
            marker='o',
            linestyle='-',
            color='skyblue'
        )
        ax_participants.set_title(_t('participants_chart_title', lang))
        ax_participants.set_xlabel(_t('edition', lang))
        ax_participants.set_ylabel(_t('participants_chart_ylabel', lang))
        ax_participants.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig_participants)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('avg_result_pos_per_edition', lang))
    if not df.empty:
        avg_edition_stats = df.groupby('miesiac_rok_str').agg(
            avg_result=('rezultat_numeric', 'mean'),
        ).reset_index()
        avg_edition_stats.columns = ['miesiac_rok_str', _t('avg_result_edition', lang)] 
        avg_edition_stats[_t('avg_result_edition', lang)] = avg_edition_stats[_t('avg_result_edition', lang)].round(1)
        avg_edition_stats['miesiac'] = avg_edition_stats['miesiac_rok_str'].apply(lambda x: datetime.strptime(x, '%m.%Y'))
        avg_edition_stats = avg_edition_stats.sort_values('miesiac').drop(columns='miesiac')
        st.dataframe(avg_edition_stats.set_index('miesiac_rok_str'))

        fig_avg_stats, ax_avg_stats = plt.subplots(figsize=(16, 6))
        plt.style.use('dark_background')
        ax_avg_stats.set_facecolor('#0e1117')
        fig_avg_stats.patch.set_facecolor('#0e1117')
        ax_avg_stats.plot(avg_edition_stats['miesiac_rok_str'], avg_edition_stats[_t('avg_result_edition', lang)], marker='o', linestyle='-', color='lightgreen')
        ax_avg_stats.set_title(f"{_t('avg_result_edition', lang)} w poszczególnych edycjach")
        ax_avg_stats.set_xlabel(_t('edition', lang))
        ax_avg_stats.set_ylabel(_t('avg_result_edition', lang))
        ax_avg_stats.grid(True, which='both', linestyle='--', linewidth=0.3)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        st.pyplot(fig_avg_stats)
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('edition_ranking_title', lang))
    st.write(_t('edition_ranking_desc', lang))
    if not df.empty:
        edition_ranking_data = []
        df_sorted_by_edition_full = df.sort_values(by='edycja_nr').copy()
        for ed_nr in sorted(df_sorted_by_edition_full['edycja_nr'].unique()):
            edition_data = df_sorted_by_edition_full[df_sorted_by_edition_full['edycja_nr'] == ed_nr]
            avg_result_ed = edition_data['rezultat_numeric'].mean()
            winner = "N/A"
            if not edition_data['miejsce'].isnull().all():
                best_place_in_edition = edition_data['miejsce'].min()
                winners_in_edition = edition_data[edition_data['miejsce'] == best_place_in_edition]['uczestnik'].unique()
                winner = ", ".join(winners_in_edition)
            edition_ranking_data.append({'Miesiąc/Rok': edition_data['miesiac_rok_str'].iloc[0], _t('avg_result_edition', lang): avg_result_ed.round(1) if pd.notna(avg_result_ed) else 'N/A', _t('participants_chart_ylabel', lang): edition_data['uczestnik'].nunique(), _t('edition_winner', lang): winner})
        edition_ranking = pd.DataFrame(edition_ranking_data)
        edition_ranking['miesiac_sort'] = edition_ranking['Miesiąc/Rok'].apply(lambda x: datetime.strptime(x, '%m.%Y'))
        edition_ranking = edition_ranking.sort_values('miesiac_sort').drop(columns='miesiac_sort')
        st.dataframe(edition_ranking.set_index('Miesiąc/Rok'))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('overall_records_title', lang))
    st.write(_t('overall_records_desc', lang))
    if not df.empty:
        overall_records = []
        current_best_result = -np.inf 
        df_sorted_by_edition = df.sort_values(by='edycja_nr').copy()
        for ed_nr in sorted(df_sorted_by_edition['edycja_nr'].unique()):
            edition_data = df_sorted_by_edition[df_sorted_by_edition['edycja_nr'] == ed_nr]
            best_result_in_edition = edition_data['rezultat_numeric'].max()
            if pd.notna(best_result_in_edition) and best_result_in_edition > current_best_result:
                record_holders_in_edition = edition_data[edition_data['rezultat_numeric'] == best_result_in_edition]['uczestnik'].unique()
                overall_records.append({_t('edition', lang): edition_data['miesiac_rok_str'].iloc[0], _t('record_holder', lang): ", ".join(record_holders_in_edition), _t('record_value', lang): f"{best_result_in_edition:.1f}", _t('previous_record', lang): f"{current_best_result:.1f}" if current_best_result != -np.inf else "N/A"})
                current_best_result = best_result_in_edition
        if overall_records: st.dataframe(pd.DataFrame(overall_records), hide_index=True)
        else: st.info(_t('no_data_selected', lang))
    else:
        st.info(_t('no_data_selected', lang))

    st.subheader(_t('personal_records_timeline_title', lang))
    st.write(_t('personal_records_timeline_desc', lang))
    if not df.empty:
        personal_records_timeline = []
        for user in df['uczestnik'].unique():
            user_df = df[df['uczestnik'] == user].sort_values(by='edycja_nr').copy()
            current_personal_best = -np.inf 
            for index, row in user_df.iterrows():
                if pd.notna(row['rezultat_numeric']) and row['rezultat_numeric'] > current_personal_best:
                    personal_records_timeline.append({_t('participant', lang): user, _t('edition', lang): row['miesiac_rok_str'], _t('new_record', lang): f"{row['rezultat_numeric']:.1f}", _t('old_record', lang): f"{current_personal_best:.1f}" if current_personal_best != -np.inf else "Brak"})
                    current_personal_best = row['rezultat_numeric']
        if personal_records_timeline:
            personal_records_df = pd.DataFrame(personal_records_timeline)
            personal_records_df['miesiac_sort'] = personal_records_df[_t('edition', lang)].apply(lambda x: datetime.strptime(x, '%m.%Y'))
            personal_records_df = personal_records_df.sort_values(by='miesiac_sort').drop(columns='miesiac_sort')
            st.dataframe(personal_records_df, hide_index=True)
        else: st.info(_t('no_data_selected', lang))
    else: st.info(_t('no_data_selected', lang))

    st.subheader(_t('survival_analysis_title', lang))
    st.write(_t('survival_analysis_desc', lang))
    all_editions_sorted = sorted(df['miesiac_rok_str'].unique(), key=lambda x: datetime.strptime(x, '%m.%Y'), reverse=True)
    selected_editions_survival = st.multiselect(_t('survival_analysis_select_editions', lang), options=all_editions_sorted, default=all_editions_sorted[:min(3, len(all_editions_sorted))], key="hist_survival_select")
    if not selected_editions_survival:
        st.info(_t('survival_analysis_no_selection', lang))
    else:
        fig_survival, ax_survival = plt.subplots(figsize=(16, 8))
        plt.style.use('dark_background')
        ax_survival.set_facecolor('#0e1117')
        fig_survival.patch.set_facecolor('#0e1117')
        max_day_overall = 0 
        for edition_str in selected_editions_survival:
            edition_df = df[df['miesiac_rok_str'] == edition_str].copy()
            if not edition_df.empty:
                edition_df['dropout_day'] = edition_df['rezultat_numeric'] + 3
                max_dropout_day_in_edition = int(edition_df['dropout_day'].max()) if not edition_df['dropout_day'].isnull().all() else 3
                competition_days = np.arange(1, max_dropout_day_in_edition + 2) 
                active_participants_count = []
                for day in competition_days:
                    active_count = (edition_df['dropout_day'] > day).sum()
                    active_participants_count.append(active_count)
                last_active_day_index = next((i for i, count in reversed(list(enumerate(active_participants_count))) if count > 0), 0)
                if active_participants_count and active_participants_count[last_active_day_index] > 0: current_max_day = competition_days[last_active_day_index] + 1 
                elif competition_days.any(): current_max_day = competition_days[last_active_day_index]
                else: current_max_day = 1
                max_day_overall = max(max_day_overall, current_max_day)
                ax_survival.plot(competition_days, active_participants_count, marker='.', linestyle='-', label=edition_str)
        ax_survival.set_title(_t('survival_analysis_title', lang))
        ax_survival.set_xlabel(_t('survival_analysis_x_axis', lang))
        ax_survival.set_ylabel(_t('survival_analysis_y_axis', lang))
        ax_survival.legend(title=_t('survival_analysis_legend', lang))
        ax_survival.grid(True, which='both', linestyle='--', linewidth=0.3)
        ax_survival.yaxis.get_major_locator().set_params(integer=True)
        if max_day_overall > 0: ax_survival.set_xlim(1, max_day_overall)
        plt.tight_layout()
        st.pyplot(fig_survival)
