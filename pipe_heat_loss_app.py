
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# --- Branding ---
st.set_page_config(page_title="Pipeline Heat Loss Calculator", page_icon="💧", layout="centered")

# Logo at the top (make sure logo.png is in the same folder as this script)
st.image("logo.png", width=150)

# Custom CSS for branding
st.markdown("""
    <style>
    /* Background */
    .main {
        background-color: #ffffff;
    }
    /* Subheader & headings in brand color */
    h1, h2, h3 {
        color: #0E6251;
    }
    /* Table styling */
    table {
        border-collapse: collapse;
        width: 100%;
    }
    th, td {
        text-align: center !important;
        border: 1px solid #ddd;
        padding: 8px;
    }
    tr:nth-child(even) {background-color: #f2f2f2;}
    th {
        background-color: #0E6251;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Calculation function ---
def inlet_temp_curve(T_amb, wind_mph, length_miles, diameter_in, T_out_target, 
                     flow_min=15, flow_max=60, flow_step=5):
    cp = 1.0  # Btu/lb-F
    lb_per_bbl = 42 * 8.34  # water (350.3 lb/bbl)
    wall_in = 0.15  # fixed wall thickness (inches)

    # Outside convection coefficient from wind speed (simple linear model)
    h = 1.5 + 0.25 * wind_mph  # Btu/hr-ft²-F

    # Geometry
    r_i = diameter_in / 24.0  # ft (12 in/ft, diameter/24 = radius in ft)
    r_o = r_i + wall_in / 12.0
    perimeter = 2 * np.pi * r_o  # ft
    area_per_mile = perimeter * 5280  # ft² per mile

    # Wall conduction resistance
    k_tpu = 0.116  # Btu/hr-ft-F
    R_wall = np.log(r_o / r_i) / (2 * np.pi * k_tpu * 5280)
    R_out = 1.0 / (h * area_per_mile)
    UA_per_mile = 1.0 / (R_wall + R_out)
    UA_total = UA_per_mile * length_miles

    flows = np.arange(flow_min, flow_max+1, flow_step)
    required_in = []
    for f in flows:
        m_dot = f * lb_per_bbl * 60.0  # lb/hr
        exponent = UA_total / (m_dot * cp)
        T_in = T_amb + (T_out_target - T_amb) * np.exp(exponent)
        required_in.append(T_in)

    df = pd.DataFrame({
        "Flow (bbl/min)": flows,
        "Required Inlet Temp (°F)": np.round(required_in, 1)
    })
    return df

# --- Sidebar Inputs ---
st.sidebar.header("Inputs")
T_amb = st.sidebar.number_input("Ambient Temperature (°F)", value=-10.0, step=1.0)
wind_mph = st.sidebar.number_input("Wind Speed (mph)", value=20.0, step=1.0)
length_miles = st.sidebar.number_input("Line Length (miles)", value=9.5, step=0.1)
diameter_in = st.sidebar.number_input("Inside Diameter (inches)", value=12.0, step=0.5)
T_out_target = st.sidebar.number_input("Desired Outlet Temp (°F)", value=35.0, step=1.0)
flow_min = st.sidebar.number_input("Min Flow (bbl/min)", value=15, step=5)
flow_max = st.sidebar.number_input("Max Flow (bbl/min)", value=60, step=5)
flow_step = st.sidebar.number_input("Flow Step (bbl/min)", value=5, step=5)

# --- Run calculation ---
df = inlet_temp_curve(T_amb, wind_mph, length_miles, diameter_in, T_out_target, flow_min, flow_max, flow_step)

# --- Results Table ---
st.subheader(
    f"Results Table (Target Outlet: {T_out_target} °F | Ambient: {T_amb} °F | Wind: {wind_mph} mph)"
)

# Format and center-align
df_formatted = df.copy()
df_formatted["Flow (bbl/min)"] = df_formatted["Flow (bbl/min)"].map("{:.0f}".format)
df_formatted["Required Inlet Temp (°F)"] = df_formatted["Required Inlet Temp (°F)"].map("{:.1f} °F".format)

st.markdown(df_formatted.to_html(index=False, justify="center"), unsafe_allow_html=True)

# --- Chart ---
fig, ax = plt.subplots()
ax.plot(df["Flow (bbl/min)"], df["Required Inlet Temp (°F)"], marker="o", color="#0E6251")
ax.set_title(
    f"Required Inlet Temp vs Flow\n(Target Outlet: {T_out_target} °F | Ambient: {T_amb} °F | Wind: {wind_mph} mph)",
    color="#0E6251"
)
ax.set_xlabel("Flow (bbl/min)")
ax.set_ylabel("Required Inlet Temp (°F)")
ax.grid(True)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

st.pyplot(fig)
