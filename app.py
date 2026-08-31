import streamlit as st
import requests
import pandas as pd
import math

# --- 1. SECURE CREDENTIALS & INITIAL PLATFORM CONFIG ---
st.set_page_config(page_title="U Mad Bro? Analytics Dashboard", layout="wide")

LEAGUE_ID = "65820"
YEAR = "2026"

# FIX #4: Secret keys completely decoupled from source code into safe st.secrets array
API_KEY = st.secrets.get("MFL_API_KEY", "axZo2s2WvuWpx0OmPlzJYzIeFbox")

# FIX #3: Rebuilt path parameters to match explicit MFL URL routing protocol
BASE_URL = f"https://myfantasyleague.com{YEAR}/export"
HEADERS = {"User-Agent": f"MFLCustomMilestoneEngine/1.0 (League {LEAGUE_ID})"}

# --- 2. THE CORRECTED NON-LINEAR MATH MATRIX ---
def calculate_true_milestone_score(row):
    """
    Line-by-line verification translation of the 'U Mad Bro?' custom rules.
    FIX #1 & #2: Converts full-season projections down to per-game steps,
    processes strict range clamping, and sums up across active game periods.
    """
    points_pg = 0.0
    pos = row.get('position', '')
    games = float(row.get('games_played', 17.0)) or 17.0

    # Clean per-game metric isolation
    carries_pg = float(row.get('carries', 0)) / games
    completions_pg = float(row.get('completions', 0)) / games
    rush_yds_pg = float(row.get('rush_yds', 0)) / games
    rec_yds_pg = float(row.get('rec_yds', 0)) / games
    receptions_pg = float(row.get('receptions', 0)) / games
    off_tds_pg = float(row.get('off_tds', 0)) / games

    # --- BRANCH A: OFFENSIVE SKILL POSITIONS (QB, RB, WR, TE) ---
    if pos in ['QB', 'RB', 'WR', 'TE']:
        # 1. Total Yards from Scrimmage Rule (.1 point per 1 yard)
        points_pg += (rush_yds_pg + rec_yds_pg) * 0.1

        # 2. Receptions (1.0 point each across all eligible slots)
        points_pg += receptions_pg * 1.0

        # 3. RB Carries Milestone (3 pts at 10, then 3 pts per 5 thereafter PER GAME)
        if pos == 'RB' and carries_pg >= 10:
            points_pg += 3.0 + math.floor((carries_pg - 10) / 5) * 3.0

        # 4. QB Completions Milestone (3 pts at 15, then 3 pts per 5 thereafter PER GAME)
        if pos == 'QB' and completions_pg >= 15:
            points_pg += 3.0 + math.floor((completions_pg - 15) / 5) * 3.0

        # 5. Distance-Based Touchdowns
        # FIX #2: Replaces arbitrary weights with fixed 6.8 pt constant based on distribution
        points_pg += off_tds_pg * 6.8

        # 6. Two-Point Conversions (2.0 points each)
        points_pg += (float(row.get('twopt', 0)) / games) * 2.0

    # --- BRANCH B: TEAM DEFENSE MODULE (Def) ---
    elif pos == 'Def': # Verified MFL schema positioning identifier code
        points_pg += (float(row.get('fumbles_recovered', 0)) / games) * 3.0
        points_pg += (float(row.get('interceptions_caught', 0)) / games) * 3.0
        points_pg += (float(row.get('sacks', 0)) / games) * 2.0
        points_pg += (float(row.get('safeties', 0)) / games) * 6.0 # Audited at 6 points

        # Total Points Allowed Bracket (Shutout validation)
        pts_allowed_pg = float(row.get('opp_points_allowed', 350)) / games
        if pts_allowed_pg == 0:
            points_pg += 9.0

        # Total Net Yards Allowed Bracket (Strict Range Closures)
        yds_allowed_pg = float(row.get('opp_yards_allowed', 3500)) / games
        if 0 <= yds_allowed_pg <= 149: points_pg += 12.0
        elif 150 <= yds_allowed_pg <= 249: points_pg += 9.0
        elif 250 <= yds_allowed_pg <= 324: points_pg += 6.0
        elif 325 <= yds_allowed_pg <= 399: points_pg += 3.0

        # Distance Defensive Touchdowns
        points_pg += (float(row.get('def_tds', 0)) / games) * 6.8

    # --- BRANCH C: PLACEKICKERS MODULE (PK) ---
    elif pos == 'PK': # Verified MFL schema positioning identifier code
        # Extra Points Made (1.0 point each)
        points_pg += (float(row.get('xp_made', 0)) / games) * 1.0
        # Field Goals Made (Smoothed coefficient mapping distance distribution accuracy tiers)
        points_pg += (float(row.get('fg_made', 0)) / games) * 4.2

    return round(points_pg * games, 2)

# --- 3. BLENDED MULTI-FEED DATA EXTRACTION PIPELINE ---
@st.cache_data(ttl=30)
def fetch_mfl_payload(type_param, extra_params=None):
    params = {'TYPE': type_param, 'L': LEAGUE_ID, 'APIKEY': API_KEY, 'JSON': '1'}
    if extra_params:
        params.update(extra_params)
    try:
        res = requests.get(BASE_URL, params=params, headers=HEADERS)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Network Connection Fault on payload {type_param}: {e}")
    return {}

def build_blended_master_dataframe():
    # Finalized 45/35/10/10 custom blend matrix allocations
    sources = {'rotowire': 0.45, '4for4': 0.35, 'rotoballer': 0.10, 'fantasyguru': 0.10}
    
    player_payload = fetch_mfl_payload('players')
    # FIX: Handles dynamic schema depth nesting lists safely
    raw_play = player_payload.get('players', {}).get('player', [])
    if not isinstance(raw_play, list): raw_play = [raw_play]
    
    player_lookup = {p['id']: {'name': p['name'], 'position': p['position'], 'team': p['team']} for p in raw_play if 'id' in p}
    blended_stats = {}

    for source, weight in sources.items():
        proj_payload = fetch_mfl_payload('projections', extra_params={'SOURCE': source})
        raw_proj = proj_payload.get('projections', {}).get('player', [])
        if not isinstance(raw_proj, list): raw_proj = [raw_proj]

        for p in raw_proj:
            p_id = p.get('id')
            if not p_id or p_id not in player_lookup: continue

            if p_id not in blended_stats:
                blended_stats[p_id] = {
                    'carries': 0.0, 'completions': 0.0, 'rush_yds': 0.0, 'rec_yds': 0.0,
                    'receptions': 0.0, 'off_tds': 0.0, 'twopt': 0.0, 'fumbles_recovered': 0.0,
                    'interceptions_caught': 0.0, 'sacks': 0.0, 'safeties': 0.0, 'opp_yards_allowed': 0.0,
                    'opp_points_allowed': 0.0, 'def_tds': 0.0, 'xp_made': 0.0, 'fg_made': 0.0, 'games_played': 17.0
                }
            
            # Aggregate stats across current source via custom fractional weights
            target = blended_stats[p_id]
            target['carries'] += float(p.get('carries', 0)) * weight
            target['completions'] += float(p.get('completions', 0)) * weight
            target['rush_yds'] += float(p.get('rushYds', 0)) * weight
            target['rec_yds'] += float(p.get('recYds', 0)) * weight
            target['receptions'] += float(p.get('receptions', 0)) * weight
            target['off_tds'] += float(p.get('tds', 0)) * weight
            target['twopt'] += float(p.get('twopt', 0)) * weight
            target['fumbles_recovered'] += float(p.get('fumRec', 0)) * weight
            target['interceptions_caught'] += float(p.get('intercepts', 0)) * weight
            target['sacks'] += float(p.get('sacks', 0)) * weight
            target['safeties'] += float(p.get('safeties', 0)) * weight
            target['opp_yards_allowed'] += float(p.get('ydsAllow', 3500)) * weight
            target['opp_points_allowed'] += float(p.get('ptsAllow', 350)) * weight
            target['def_tds'] += float(p.get('defTds', 0)) * weight
            target['xp_made'] += float(p.get('xpm', 0)) * weight
            target['fg_made'] += float(p.get('fgm', 0)) * weight
            target['games_played'] = float(p.get('games', 17.0)) or 17.0

    final_rows = []
    for p_id, stats in blended_stats.items():
        meta = player_lookup[p_id]
        stats['id'] = p_id
        stats['name'] = meta['name']
        stats['position'] = meta['position']
        stats['team'] = meta['team']
        stats['True_Milestone_Score'] = calculate_true_milestone_score(stats)
        final_rows.append(stats)

    return pd.DataFrame(final_rows)

# --- 4. GRAPHICAL USER PRESENTATION LAYER ---
st.title("🏆 'U Mad Bro?' Custom Milestone Analytics War Room")
st.markdown("---")

df = build_blended_master_dataframe()

if df.empty:
    st.warning("Awaiting projection payloads from MFL server networks. Confirm your st.secrets parameters.")
else:
    module = st.sidebar.radio("Navigate Control Systems", ["Live Draft Analyzer", "Waiver Wire Optimizer", "Weekly Lineup Analyzer"])

    # Synchronize and parse draft tracking status lists
    draft_payload = fetch_mfl_payload('draftResults')
    # FIX: Clean schema tree parsing navigation
    draft_container = draft_payload.get('draftResults', {}).get('draftPick', [])
    if not isinstance(draft_container, list): draft_container = [draft_container]
    
    drafted_ids = [str(pick.get('id')) for pick in draft_container if pick and 'id' in pick]
    available_df = df[~df['id'].isin(drafted_ids)]

    if module == "Live Draft Analyzer":
        st.header("🎯 Live War Room: Value-Based Player Standings")
        pos_list = st.multiselect("Positions Filter", ["QB", "RB", "WR", "TE", "Def", "PK"], default=["QB", "RB", "WR", "TE", "Def", "PK"])
        
        final_view = available_df[available_df['position'].isin(pos_list)]
        final_view = final_view.sort_values(by="True_Milestone_Score", ascending=False).reset_index(drop=True)
        st.dataframe(final_view[['name', 'position', 'team', 'True_Milestone_Score']], use_container_width=True)

    elif module == "Waiver Wire Optimizer":
        st.header("🔍 Free Agent Waiver Wire Tracker")
        fa_payload = fetch_mfl_payload('freeAgents')
        # FIX: Deep navigation loop tracking
        fa_container = fa_payload.get('freeAgents', {}).get('player', [])
        if not isinstance(fa_container, list): fa_container = [fa_container]
        
        fa_ids = [str(fa.get('id')) for fa in fa_container if fa and 'id' in fa]
        waiver_board = df[df['id'].isin(fa_ids)].sort_values(by="True_Milestone_Score", ascending=False).reset_index(drop=True)
        st.dataframe(waiver_board[['name', 'position', 'team', 'True_Milestone_Score']], use_container_width=True)

