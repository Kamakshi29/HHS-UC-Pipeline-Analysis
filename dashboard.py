import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# -------------------------------------------------------------
# 1. PAGE CONFIGURATION & THEME
# -------------------------------------------------------------
st.set_page_config(
    page_title="UAC Care Pipeline Analytics",
    page_icon="📊",
    layout="wide"
)

st.title("Care Transition Efficiency & Placement Outcome Analytics")
st.markdown("### U.S. Department of Health and Human Services (HHS) — Unaccompanied Children Program")
st.markdown("This interactive application shifts focus from simple capacity tracking to process efficiency, transition speed, and pipeline bottlenecks.")

# -------------------------------------------------------------
# 2. DATA INGESTION & CLEANING PIPELINE
# -------------------------------------------------------------
@st.cache_data # This makes the app load incredibly fast by caching the data
def load_and_clean_data():
    # Load the CSV
    df = pd.read_csv('HHS_Unaccompanied_Alien_Children_Program.csv')
    
    # Standardize the Date column format
    df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%y')
    
    # robustly clean 'Children in HHS Care' and force convert to numbers
    df['Children in HHS Care'] = df['Children in HHS Care'].astype(str).str.replace(',', '').str.strip()
    df['Children in HHS Care'] = pd.to_numeric(df['Children in HHS Care'], errors='coerce').fillna(0).astype(int)
    
    # Rename columns to clean Pythonic names for easier coding
    df.rename(columns={
        'Children apprehended and placed in CBP custody*': 'CBP_Intake',
        'Children in CBP custody': 'CBP_Active_Load',
        'Children transferred out of CBP custody': 'HHS_Inflow',
        'Children in HHS Care': 'HHS_Active_Load',
        'Children discharged from HHS Care': 'Sponsor_Placements'
    }, inplace=True)
    
    # Sort chronologically to make sure line graphs draw correctly
    return df.sort_values('Date')

# Run the cleaning function
try:
    df = load_and_clean_data()
except Exception as e:
    st.error(f"Error loading CSV file. Make sure 'HHS_Unaccompanied_Alien_Children_Program.csv' is in the same folder as app.py. Error details: {e}")
    st.stop()

# -------------------------------------------------------------
# 3. USER CAPABILITIES (Sidebar Filters & Controls)
# -------------------------------------------------------------
st.sidebar.header("User Control Panel")

# Capability A: Date Range Selection
min_date = df['Date'].min().date()
max_date = df['Date'].max().date()
st.sidebar.markdown("#### 📅 Date Filter")
start_date = st.sidebar.date_input("Start Date", min_date)
end_date = st.sidebar.date_input("End Date", max_date)

# Filter dataframe based on date selection
filtered_df = df[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)].copy()

# Add Weekday/Weekend feature for temporal pattern analysis
filtered_df['Day_Type'] = filtered_df['Date'].dt.dayofweek.apply(lambda x: 'Weekend' if x >= 5 else 'Weekday')

# Capability B: Ratio-Based Metric Toggle
st.sidebar.markdown("#### ⚙️ Metric Configurations")
metric_toggle = st.sidebar.radio(
    "Primary Focus Metric:",
    options=["Transfer Efficiency Ratio", "Discharge Effectiveness Index"],
    help="Toggle between evaluating upstream CBP -> HHS velocity or downstream Sponsor Placement effectiveness."
)

# Capability C: Threshold-Based Visual Alerts Configuration
st.sidebar.markdown("#### 🚨 Alert Settings")
backlog_threshold = st.sidebar.slider(
    "Active CBP Custody Critical Alert Threshold",
    min_value=50,
    max_value=500,
    value=200,
    step=10
)

# Calculate daily active metrics for KPIs (CORRECTED)
current_cbp_load = int(filtered_df['CBP_Active_Load'].iloc[-1]) if not filtered_df.empty else 0
avg_hhs_load = filtered_df['HHS_Active_Load'].mean() if not filtered_df.empty else 0
avg_daily_placements = filtered_df['Sponsor_Placements'].mean() if not filtered_df.empty else 0

avg_daily_inflow = filtered_df['HHS_Inflow'].mean() if not filtered_df.empty else 0
avg_cbp_load = filtered_df['CBP_Active_Load'].mean() if not filtered_df.empty else 0

# 1. Daily Transfer Efficiency (Average daily movement relative to average daily backlog)
transfer_ratio = avg_daily_inflow / avg_cbp_load if avg_cbp_load > 0 else 0

# 2. Daily Discharge Effectiveness Index (Daily placement rate of current active census)
discharge_index = avg_daily_placements / avg_hhs_load if avg_hhs_load > 0 else 0

# 3. Pipeline Throughput Rate (HHS Inflow vs. Sponsor Placements)
total_hhs_inflow = filtered_df['HHS_Inflow'].sum()
total_placements = filtered_df['Sponsor_Placements'].sum()
# throughput_rate = total_placements / total_hhs_inflow if total_hhs_inflow > 0 else 0
# 3. Pipeline Throughput Rate (Calculated as average daily discharges relative to total daily active volume handled)
# This represents what % of the active daily caseload is successfully transitioned/cleared daily.
throughput_rate = avg_daily_placements / (avg_hhs_load + avg_daily_inflow) if (avg_hhs_load + avg_daily_inflow) > 0 else 0

# -------------------------------------------------------------
# 4. EXECUTIVE BANNER & VISUAL ALERTS
# -------------------------------------------------------------
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.metric(
        label="Transfer Efficiency Ratio", 
        value=f"{transfer_ratio:.2%}", 
        help="Measures how fast children transition from CBP to HHS"
    )

with kpi_col2:
    st.metric(
        label="Discharge Effectiveness Index", 
        value=f"{discharge_index:.2%}", 
        help="Measures placement success relative to total system load"
    )

with kpi_col3:
    st.metric(
        label="Pipeline Throughput", 
        value=f"{throughput_rate:.2%}", 
        help="Overall exits compared to overall entries"
    )

with kpi_col4:
    # Threshold Alert Logic (Visual Alert)
    if current_cbp_load > backlog_threshold:
        st.metric(
            label="Current CBP Custody",
            value=f"{current_cbp_load} children",
            delta="⚠️ CRITICAL VOLUME ALERT",
            delta_color="inverse",
            help="Active load exceeds the safe threshold set in your sidebar."
        )
    else:
        st.metric(
            label="Current CBP Custody",
            value=f"{current_cbp_load} children",
            delta="🟢 System Normal",
            delta_color="normal",
            help="Active load is safely below the configured threshold."
        )

st.markdown("---")

# -------------------------------------------------------------
# 5. CORE MODULES
# -------------------------------------------------------------

# --- Module 1: Care Pipeline Flow Visualization ---
st.subheader("1. Care Pipeline Flow Visualization")
st.markdown("This chart tracks the daily flow rates: how many enter (Intake) vs. how many transition successfully (Discharges).")

fig_flow = go.Figure()
fig_flow.add_trace(go.Scatter(
    x=filtered_df['Date'], y=filtered_df['CBP_Intake'], 
    mode='lines', name='CBP Intake (Entries)', line=dict(color='#1f77b4', width=2)
))
fig_flow.add_trace(go.Scatter(
    x=filtered_df['Date'], y=filtered_df['Sponsor_Placements'], 
    mode='lines', name='Sponsor Placements (Exits)', line=dict(color='#ff7f0e', width=2)
))
fig_flow.update_layout(
    xaxis_title="Reporting Date",
    yaxis_title="Daily Count of Children",
    legend_orientation="h",
    margin=dict(l=20, r=20, t=30, b=20)
)
st.plotly_chart(fig_flow, width='stretch')


# --- Module 2: Transfer & Discharge Efficiency Panels ---
st.subheader("2. Transition & Placement Efficiency Analysis")
st.markdown(f"Currently displaying: **{metric_toggle}** based on your sidebar selection.")

col_panel1, col_panel2 = st.columns(2)

with col_panel1:
    if metric_toggle == "Transfer Efficiency Ratio":
        # Calculate weekly average of Transfer Efficiency
        filtered_df['Calculated_Transfer_Ratio'] = filtered_df['HHS_Inflow'] / filtered_df['CBP_Active_Load'].replace(0, 1)
        fig_metric = px.line(
            filtered_df, x='Date', y='Calculated_Transfer_Ratio',
            title="Daily CBP to HHS Transfer Speed",
            labels={'Calculated_Transfer_Ratio': 'Transfer Efficiency Ratio'}
        )
        st.plotly_chart(fig_metric, width='stretch')
    else:
        filtered_df['Calculated_Discharge_Index'] = filtered_df['Sponsor_Placements'] / filtered_df['HHS_Active_Load'].replace(0, 1)
        fig_metric = px.line(
            filtered_df, x='Date', y='Calculated_Discharge_Index',
            title="Daily Sponsor Placement Success Index",
            labels={'Calculated_Discharge_Index': 'Discharge Effectiveness Index'},
            color_discrete_sequence=['#2ca02c']
        )
        st.plotly_chart(fig_metric, width='stretch')

with col_panel2:
    st.markdown("#### Weekday vs. Weekend Transition Speeds")
    st.markdown("Temporal patterns reveal if staffing or process variations on weekends create systemic delays.")
    
    # Grouping data to compare Weekday vs Weekend performance
    avg_patterns = filtered_df.groupby('Day_Type')[['HHS_Inflow', 'Sponsor_Placements']].mean().reset_index()
    
    fig_patterns = px.bar(
        avg_patterns, x='Day_Type', y=['HHS_Inflow', 'Sponsor_Placements'],
        barmode='group',
        title="Average Daily Movements: Weekdays vs. Weekends",
        labels={'value': 'Average Daily Volume', 'Day_Type': 'Time of Week'}
    )
    st.plotly_chart(fig_patterns, width='stretch')


# --- Module 3: Bottleneck Detection Charts ---
st.subheader("3. Bottleneck & System Strain Detection")
st.markdown("Bottlenecks occur when active custodial loads expand rapidly due to delayed downstream discharges.")

col_bot1, col_bot2 = st.columns(2)

with col_bot1:
    st.markdown("#### Active Custodial Loads (CBP vs. HHS)")
    fig_active = go.Figure()
    fig_active.add_trace(go.Scatter(
        x=filtered_df['Date'], y=filtered_df['CBP_Active_Load'], 
        fill='tozeroy', name='Active CBP Custody Load', line=dict(color='#d62728')
    ))
    fig_active.add_trace(go.Scatter(
        x=filtered_df['Date'], y=filtered_df['HHS_Active_Load'], 
        fill='tonexty', name='Active HHS Care Load', line=dict(color='#9467bd')
    ))
    fig_active.update_layout(xaxis_title="Date", yaxis_title="Active Care Load Count")
    st.plotly_chart(fig_active, width='stretch')

with col_bot2:
    st.markdown("#### Dynamic Pipeline Flow Strain (Inflow - Outflow)")
    filtered_df['Net_System_Strain'] = filtered_df['CBP_Intake'] - filtered_df['Sponsor_Placements']
    
    fig_strain = px.bar(
        filtered_df, x='Date', y='Net_System_Strain',
        title="Daily Intake vs. Placement Discrepancy",
        labels={'Net_System_Strain': 'Volume Delta (Intake - Placements)'},
        color='Net_System_Strain',
        color_continuous_scale=px.colors.diverging.RdYlGn_r
    )
    st.plotly_chart(fig_strain, width='stretch')


# --- Module 4: Outcome Trend Analysis ---
st.subheader("4. Long-Term Outcome & Operational Trends")

fig_trends = px.scatter(
    filtered_df, x='HHS_Active_Load', y='Sponsor_Placements',
    trendline="ols",
    title="Relationship: Sponsor Placements vs. HHS Active Census",
    labels={'HHS_Active_Load': 'Active HHS Care Load', 'Sponsor_Placements': 'Sponsor Placements'},
    color_discrete_sequence=['#bcbd22']
)
st.plotly_chart(fig_trends, width='stretch')
st.markdown("The trendline demonstrates whether successful placements scale up proportionally with system capacity, or if placement rates flatten out (stagnate) as the system fills up.")