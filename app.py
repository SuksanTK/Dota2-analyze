import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Dota 2 Analytics Dashboard", layout="wide")

st.title("Yen Trex Dota2 Analytics Dashboard")
st.markdown("วิเคราะห์ข้อมูลการเล่น dota2 ของ Yen trex")

# 1. Load Data
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("data_final1.csv")
        
        # --- Data Preprocessing (เหมือนใน analyze_dota2.py) ---
        # 1. แปลง match_date เป็น datetime
        df['match_date'] = pd.to_datetime(df['match_date'])
        
        # 2. สร้าง column is_win (1=Win, 0=Lose)
        df['is_win'] = df['result'].apply(lambda x: 1 if x == 'Win' else 0)

        # 3. จัดการ Party Size
        df['party_size'] = df['party_size'].fillna(1).astype(int)
        
        # 4. สร้าง column เดือน-ปี สำหรับ Timeline
        df['month_year'] = df['match_date'].dt.to_period('M').astype(str)
        
        # 5. เพิ่ม Columns สำหรับ Filter (Year, Month, Day, DayName)
        df['year'] = df['match_date'].dt.year
        df['month'] = df['match_date'].dt.month_name()
        df['day'] = df['match_date'].dt.day
        df['day_name'] = df['match_date'].dt.day_name()
        
        # 6. จัดการ Game Duration Category (ย้ายมาจาก Tab 3 เพื่อทำ Filter)
        def categorize_duration(min):
            if min < 30: return 'Short (<30m)'
            elif min <= 45: return 'Medium (30-45m)'
            else: return 'Long (>45m)'
        df['game_length'] = df['duration_min'].apply(categorize_duration)

        # 7. คำนวณ Hero Stats รวมทั้งหมด (Global) เพื่อใช้ในการ Filter Hero ตามความถนัด
        hero_global = df.groupby('hero_name').agg(
            hero_total_matches=('match_id', 'count'),
            hero_total_win_rate=('is_win', 'mean')
        ).reset_index()
        hero_global['hero_total_win_rate'] = hero_global['hero_total_win_rate'] * 100
        df = pd.merge(df, hero_global, on='hero_name', how='left')

        # 8. Load Hero Icons (สำหรับแสดงผลในกราฟ)
        try:
            with open("hero_master_data.json", "r", encoding="utf-8") as f:
                heroes_data = json.load(f)
            heroes_df = pd.DataFrame(heroes_data)
            # สร้าง URL เต็มสำหรับรูปภาพ (OpenDota ใช้ CDN ของ Steam)
            heroes_df['icon_url'] = "https://cdn.cloudflare.steamstatic.com" + heroes_df['icon']
            
            # Merge เอา icon_url เข้าไปใน df หลัก
            df = pd.merge(df, heroes_df[['localized_name', 'icon_url']], 
                          left_on='hero_name', right_on='localized_name', how='left')
        except Exception as e:
            st.warning(f"Could not load hero icons: {e}")

        return df
    except FileNotFoundError:
        st.error("ไม่พบไฟล์ data_final1.csv กรุณาตรวจสอบว่าไฟล์อยู่ในโฟลเดอร์เดียวกัน")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- SIDEBAR (Filter) ---
    st.sidebar.header("Filter Options")
    
    # 1. Date Filters (Year, Month, Day)
    st.sidebar.subheader("📅 Date Filter")
    all_years = sorted(df['year'].unique(), reverse=True)
    sel_years = st.sidebar.multiselect("Year", all_years)
    
    all_months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    sel_months = st.sidebar.multiselect("Month", all_months)
    
    all_days = sorted(df['day'].unique())
    sel_days = st.sidebar.multiselect("Day", all_days)

    # 2. Result (Win/Lose)
    st.sidebar.subheader("🏆 Result")
    sel_result = st.sidebar.multiselect("Result", ["Win", "Lose"])

    # 3. Day of Week
    st.sidebar.subheader("📆 Day of Week")
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    sel_dow = st.sidebar.multiselect("Day of Week", days_order)

    # 4. Party Size
    st.sidebar.subheader("👥 Party Size")
    all_party = sorted(df['party_size'].unique())
    sel_party = st.sidebar.multiselect("Party Size", all_party)

    # 5. Game Duration
    st.sidebar.subheader("⏳ Game Duration")
    all_durations = ['Short (<30m)', 'Medium (30-45m)', 'Long (>45m)']
    sel_duration = st.sidebar.multiselect("Duration Category", all_durations)

    # 6. Hero Filters
    st.sidebar.subheader("🦸 Hero Filters")
    
    # Hero Experience (Matches Played Range)
    st.sidebar.markdown("**Hero Experience (Total Matches)**")
    hero_match_range = st.sidebar.selectbox("Select Range", ["All", "0-20", "21-50", "51-100", "100+"])
    
    # Hero Win Rate Range
    st.sidebar.markdown("**Hero Win Rate %**")
    hero_wr_range = st.sidebar.slider("Select Win Rate Range", 0.0, 100.0, (0.0, 100.0))

    # Specific Hero Filter
    all_heroes = sorted(df['hero_name'].unique())
    selected_heroes = st.sidebar.multiselect("Specific Heroes:", options=all_heroes, default=[])
    
    # Lobby Type Filter
    all_lobbies = sorted(df['lobby_name'].astype(str).unique())
    selected_lobbies = st.sidebar.multiselect("เลือก Lobby Type:", options=all_lobbies, default=[])

    # Apply Filters
    filtered_df = df.copy()
    
    # Apply Date Filters
    if sel_years: filtered_df = filtered_df[filtered_df['year'].isin(sel_years)]
    if sel_months: filtered_df = filtered_df[filtered_df['month'].isin(sel_months)]
    if sel_days: filtered_df = filtered_df[filtered_df['day'].isin(sel_days)]
    
    # Apply Other Filters
    if sel_result:
        is_win_filter = [1 if r == 'Win' else 0 for r in sel_result]
        filtered_df = filtered_df[filtered_df['is_win'].isin(is_win_filter)]
    if sel_dow: filtered_df = filtered_df[filtered_df['day_name'].isin(sel_dow)]
    if sel_party: filtered_df = filtered_df[filtered_df['party_size'].isin(sel_party)]
    if sel_duration: filtered_df = filtered_df[filtered_df['game_length'].isin(sel_duration)]
    if selected_heroes:
        filtered_df = filtered_df[filtered_df['hero_name'].isin(selected_heroes)]
    
    # Apply Hero Stats Filters
    if hero_match_range != "All":
        if hero_match_range == "0-20":
            filtered_df = filtered_df[(filtered_df['hero_total_matches'] >= 0) & (filtered_df['hero_total_matches'] <= 20)]
        elif hero_match_range == "21-50":
            filtered_df = filtered_df[(filtered_df['hero_total_matches'] >= 21) & (filtered_df['hero_total_matches'] <= 50)]
        elif hero_match_range == "51-100":
            filtered_df = filtered_df[(filtered_df['hero_total_matches'] >= 51) & (filtered_df['hero_total_matches'] <= 100)]
        elif hero_match_range == "100+":
            filtered_df = filtered_df[filtered_df['hero_total_matches'] > 100]
            
    filtered_df = filtered_df[(filtered_df['hero_total_win_rate'] >= hero_wr_range[0]) & (filtered_df['hero_total_win_rate'] <= hero_wr_range[1])]

    if selected_lobbies:
        filtered_df = filtered_df[filtered_df['lobby_name'].isin(selected_lobbies)]

    # --- KPI Cards ---
    st.subheader("ข้อมูลภาพรวม")
    col1, col2, col3, col4 = st.columns(4)
    
    total_matches = len(filtered_df)
    win_count = filtered_df['is_win'].sum()
    win_rate = (win_count / total_matches * 100) if total_matches > 0 else 0
    avg_kda = filtered_df['kda'].mean()
    avg_duration = filtered_df['duration_min'].mean()

    col1.metric("Total Matches", f"{total_matches} เกม")
    col2.metric("Win Rate", f"{win_rate:.2f}%", f"{win_count} Wins")
    col3.metric("Avg KDA", f"{avg_kda:.2f}")
    col4.metric("Avg Duration", f"{avg_duration:.2f} นาที")

    st.divider()

    # --- 1. Timeline Analysis ---
    st.subheader("📅 Timeline Analysis: Monthly Trends")
    
    # Group by Month
    timeline_stats = filtered_df.groupby('month_year').agg(
        matches=('match_id', 'count'),
        win_rate=('is_win', 'mean')
    ).reset_index()
    timeline_stats['win_rate'] = timeline_stats['win_rate'] * 100
    timeline_stats = timeline_stats.sort_values('month_year')

    # Create Combo Chart (Bar for Matches, Line for Win Rate)
    fig_timeline = go.Figure()
    fig_timeline.add_trace(go.Bar(
        x=timeline_stats['month_year'], 
        y=timeline_stats['matches'], 
        name='Total Matches',
        marker_color='#636EFA'
    ))
    fig_timeline.add_trace(go.Scatter(
        x=timeline_stats['month_year'], 
        y=timeline_stats['win_rate'], 
        name='Win Rate (%)',
        yaxis='y2',
        line=dict(color='#EF553B', width=3)
    ))
    fig_timeline.update_layout(
        title='จำนวนแมทช์และ Win Rate รายเดือน',
        yaxis=dict(title='Total Matches'),
        yaxis2=dict(title='Win Rate (%)', overlaying='y', side='right', range=[0, 100]),
        legend=dict(x=0, y=1.1, orientation='h'),
        hovermode="x unified"
    )
    st.plotly_chart(fig_timeline, use_container_width=True)

    # --- 2. Hero Performance Analysis ---
    st.subheader("🦸 Hero Performance Analysis")
    
    col_hero1, col_hero2 = st.columns([2, 1])
    
    # เตรียมข้อมูล Hero Stats
    hero_stats = filtered_df.groupby('hero_name').agg(
        matches=('match_id', 'count'),
        win_rate=('is_win', 'mean'),
        avg_kda=('kda', 'mean'),
        icon_url=('icon_url', 'first') # ดึง icon มาด้วย
    ).reset_index()
    hero_stats['win_rate'] = hero_stats['win_rate'] * 100

    with col_hero1:
        # --- Scatter Plot with Icons ---
        scatter_data = hero_stats[hero_stats['matches'] >= 2]
        
        fig_hero_scatter = go.Figure()

        # คำนวณขนาด icon ตามแกน (เพื่อให้ขนาดพอดี)
        x_range = scatter_data['matches'].max() - scatter_data['matches'].min()
        y_range = scatter_data['win_rate'].max() - scatter_data['win_rate'].min()
        if x_range == 0: x_range = 1
        if y_range == 0: y_range = 1
        
        # เพิ่มจุด (Invisible markers) เพื่อให้มี Hover info
        fig_hero_scatter.add_trace(go.Scatter(
            x=scatter_data['matches'],
            y=scatter_data['win_rate'],
            mode='markers',
            marker=dict(opacity=0), # ซ่อนจุด
            text=scatter_data['hero_name'],
            customdata=scatter_data['avg_kda'],
            hovertemplate="<b>%{text}</b><br>Matches: %{x}<br>Win Rate: %{y:.2f}%<br>KDA: %{customdata:.2f}<extra></extra>"
        ))

        # เพิ่มรูปภาพ Icon ลงในกราฟ
        for i, row in scatter_data.iterrows():
            if pd.notna(row['icon_url']):
                fig_hero_scatter.add_layout_image(
                    dict(
                        source=row['icon_url'],
                        x=row['matches'],
                        y=row['win_rate'],
                        xref="x",
                        yref="y",
                        sizex=x_range * 0.08, # ปรับขนาด icon ตามสัดส่วนแกน X
                        sizey=y_range * 0.15, # ปรับขนาด icon ตามสัดส่วนแกน Y
                        xanchor="center",
                        yanchor="middle",
                        layer="above"
                    )
                )

        fig_hero_scatter.update_layout(
            title='Hero Performance Matrix',
            xaxis_title='Matches Played',
            yaxis_title='Win Rate (%)',
            height=500,
            yaxis=dict(range=[0, 105]) # เผื่อที่ด้านบน
        )
        fig_hero_scatter.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% Win Rate")
        st.plotly_chart(fig_hero_scatter, use_container_width=True)

    with col_hero2:
        # --- Top 5 Graphs ---
        top_played = hero_stats.sort_values(by='matches', ascending=False).head(10)
        fig_top_played = px.bar(top_played, x='matches', y='hero_name', orientation='h', 
                                title="🏆 Top 5 Most Played", text_auto=True)
        fig_top_played.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top_played, use_container_width=True)

        best_win = hero_stats[hero_stats['matches'] >= 5].sort_values(by='win_rate', ascending=False).head(10)
        if not best_win.empty:
            fig_best_win = px.bar(best_win, x='win_rate', y='hero_name', orientation='h', 
                                  title="🔥 Best Win Rate (min 5 games)", text_auto='.2f')
            fig_best_win.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Win Rate (%)")
            st.plotly_chart(fig_best_win, use_container_width=True)
        else:
            st.info("Not enough data for >5 games stats")

    # --- Full Hero Data Table ---
    st.markdown("##### 📋 All Hero Statistics")
    st.dataframe(
        hero_stats[['hero_name', 'matches', 'win_rate', 'avg_kda']]
        .sort_values(by='matches', ascending=False)
        .style.format({'win_rate': '{:.2f}%', 'avg_kda': '{:.2f}'}),
        use_container_width=True
    )

    # --- 3. Additional Insights (Tabs) ---
    st.subheader("🔍 Deep Dive Insights")
    tab1, tab2, tab3 = st.tabs(["📅 Day of Week", "👥 Party Size", "⏳ Game Duration"])

    with tab1:
        # Win Rate by Day
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        filtered_df['day_name'] = pd.Categorical(filtered_df['day_name'], categories=days_order, ordered=True)
        day_stats = filtered_df.groupby('day_name', observed=False).agg(
            matches=('match_id', 'mean'),
            win_rate=('is_win', 'mean')
        ).reset_index()
        day_stats['win_rate'] = day_stats['win_rate'] * 100
        
        fig_day = px.bar(day_stats, x='day_name', y='matches',
                         title="Games Played by Day of Week (Color = Win Rate)",
                         color='win_rate', color_continuous_scale='RdBu',
                         text='win_rate')
        fig_day.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig_day, use_container_width=True)

    with tab2:
        # Win Rate by Party Size
        party_stats = filtered_df.groupby('party_size').agg(
            matches=('match_id', 'count'),
            win_rate=('is_win', 'mean')
        ).reset_index()
        party_stats['win_rate'] = party_stats['win_rate'] * 100
        party_stats['party_size'] = party_stats['party_size'].astype(int).astype(str) # Convert to string for categorical axis
        
        fig_party = px.bar(party_stats, x='party_size', y='win_rate',
                           title="Win Rate by Party Size",
                           labels={'party_size': 'Party Size (1=Solo)', 'win_rate': 'Win Rate (%)'},
                           text_auto='.2s')
        st.plotly_chart(fig_party, use_container_width=True)

    with tab3:
        # Pie Chart for Duration
        def categorize_duration(min):
            if min < 30: return 'Short (<30m)'
            elif min <= 45: return 'Medium (30-45m)'
            else: return 'Long (>45m)'
        
        filtered_df['game_length'] = filtered_df['duration_min'].apply(categorize_duration)
        duration_stats = filtered_df.groupby('game_length').agg(
            matches=('match_id', 'count'),
            win_rate=('is_win', 'mean')
        ).reset_index()
        duration_stats['win_rate'] = duration_stats['win_rate'] * 100
        
        fig_duration = px.pie(duration_stats, values='matches', names='game_length',
                              title="Game Duration Distribution",
                              hover_data=['win_rate'], # Show winrate on hover
                              color_discrete_sequence=px.colors.sequential.RdBu)
        fig_duration.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_duration, use_container_width=True)

else:
    st.warning("No data available to display.")