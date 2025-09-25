import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ---------------- Page / Branding ----------------
st.set_page_config(page_title="Pipeline Heat Loss Calculator", page_icon="💧", layout="centered")

# Logo (place logo.png next to this script)
try:
    st.image("logo.png", width=150)
except Exception:
    pass  # continue without logo if not found

# Branded CSS
st.markdown("""
<style>
h1, h2, h3 { color: #0E6251; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: center !important; border: 1px solid #ddd; padding: 8px; }
tr:nth-child(even) { background-color: #f2f2f2; }
th { background-color: #0E6251; color: white; }
</style>
""", unsafe_allow_html=True)

# ---------------- Physics helpers ----------------
def convective_h(wind_mph: float) -> float:
    """Outside air film coefficient [Btu/hr-ft^2-F]."""
    return 1.5 + 0.25 * float(wind_mph)

def compute_UA_per_mile(r_i_ft: float, r_o_ft: float, k_wall: float, h_out: float) -> float:
    """UA per mile [Btu/hr-F-mile] for bare pipe."""
    perimeter = 2 * np.pi * r_o_ft
    area_per_mile = perimeter * 5280.0
    R_wall_per_mile = np.log(r_o_ft / r_i_ft) / (2 * np.pi * k_wall * 5280.0)
    R_out_per_mile = 1.0 / (h_out * area_per_mile)
    UA_per_mile = 1.0 / (R_wall_per_mile + R_out_per_mile)
    return UA_per_mile

def inlet_temp_curve(T_amb, wind_mph, length_miles, id_in, wall_in, k_wall, T_out_target,
                     flow_min=15, flow_max=60, flow_step=5):
    cp = 1.0  # Btu/lb-F
    lb_per_bbl = 42.0 * 8.34  # 350.28 lb/bbl

    r_i = (id_in / 12.0) / 2.0
    r_o = r_i + (wall_in / 12.0)

    h = convective_h(wind_mph)
    UA_per_mile = compute_UA_per_mile(r_i, r_o, k_wall, h)
    UA_total = UA_per_mile * float(length_miles)

    flows = np.arange(flow_min, flow_max + 1, flow_step, dtype=float)
    required_in = []
    losses = []

    for f in flows:
        m_dot = f * lb_per_bbl * 60.0
        mcp = m_dot * cp
        k = UA_total / mcp if mcp > 0 else 0.0
        T_in = T_amb + (T_out_target - T_amb) * np.exp(k)
        Q_loss = mcp * (T_in - T_out_target)  # BTU/hr
        required_in.append(T_in)
        losses.append(Q_loss / 1e6)  # MMBtu/hr

    df = pd.DataFrame({
        "Flow (bbl/min)": flows.astype(int),
        "Required Inlet Temp (°F)": np.round(required_in, 1),
        "Heat Loss (MMBtu/hr)": np.round(losses, 2)
    })
    return df, UA_per_mile, UA_total

# ---------------- Sidebar Inputs ----------------
st.sidebar.header("Pipe Selection")

pipe_type = st.sidebar.selectbox("Pipe Type", ["Layflat TPU", "HDPE"])

# Nominal diameter options up to 24 in
nominal_options = ["4 in", "6 in", "8 in", "10 in", "12 in",
                   "14 in", "16 in", "18 in", "20 in", "22 in", "24 in"]

nominal_choice = st.sidebar.selectbox("Nominal Diameter", nominal_options, index=nominal_options.index("12 in"))

if pipe_type == "Layflat TPU":
    od_in = float(nominal_choice.split()[0])  # assume OD ≈ nominal
    wall_in = 0.15
    id_in = od_in - 2 * wall_in
    k_wall = 0.116
else:
    HDPE_OD_MAP = {
        "4 in": 4.500,
        "6 in": 6.625,
        "8 in": 8.625,
        "10 in": 10.750,
        "12 in": 12.750,
        "14 in": 14.000,
        "16 in": 16.000,
        "18 in": 18.000,
        "20 in": 20.000,
        "22 in": 22.000,
        "24 in": 24.000,
    }
    od_in = HDPE_OD_MAP[nominal_choice]
    dr_list = [7, 9, 11, 13.5, 17, 21, 26, 32.5]
    dr = st.sidebar.selectbox("HDPE DR Rating", dr_list, index=dr_list.index(17))
    wall_in = od_in / float(dr)
    id_in = od_in - 2 * wall_in
    k_wall = 0.26

st.sidebar.write(f"**Nominal Diameter:** {nominal_choice}")
st.sidebar.write(f"**Actual OD:** {od_in:.3f} in | **ID:** {id_in:.3f} in")

# Conditions
st.sidebar.header("Conditions")
T_amb = st.sidebar.number_input("Ambient Temperature (°F)", value=-10.0, step=1.0)
wind_mph = st.sidebar.number_input("Wind Speed (mph)", value=20.0, step=1.0)
length_miles = st.sidebar.number_input("Line Length (miles)", value=9.5, step=0.1)
T_out_target = st.sidebar.number_input("Desired Outlet Temp (°F)", value=35.0, step=1.0)

# Flow range
st.sidebar.header("Flow Range")
flow_min = st.sidebar.number_input("Min Flow (bbl/min)", value=15, step=5)
flow_max = st.sidebar.number_input("Max Flow (bbl/min)", value=60, step=5)
flow_step = st.sidebar.number_input("Flow Step (bbl/min)", value=5, step=5)

# ---------------- Run Calculation ----------------
df, UA_per_mile, UA_total = inlet_temp_curve(
    T_amb=T_amb,
    wind_mph=wind_mph,
    length_miles=length_miles,
    id_in=id_in,
    wall_in=wall_in,
    k_wall=k_wall,
    T_out_target=T_out_target,
    flow_min=flow_min,
    flow_max=flow_max,
    flow_step=flow_step
)

# ---------------- Results Table ----------------
st.subheader(
    f"Results Table (Target Outlet: {T_out_target} °F | Ambient: {T_amb} °F | Wind: {wind_mph} mph)"
)

df_formatted = df.copy()
df_formatted["Flow (bbl/min)"] = df_formatted["Flow (bbl/min)"].map("{:.0f}".format)
df_formatted["Required Inlet Temp (°F)"] = df_formatted["Required Inlet Temp (°F)"].map("{:.1f} °F".format)
df_formatted["Heat Loss (MMBtu/hr)"] = df_formatted["Heat Loss (MMBtu/hr)"].map("{:.2f}".format)

st.markdown(df_formatted.to_html(index=False, justify="center"), unsafe_allow_html=True)

# ---------------- Chart ----------------
fig, ax = plt.subplots()
ax.plot(df["Flow (bbl/min)"], df["Required Inlet Temp (°F)"], marker="o", color="#0E6251")
ax.set_title(
    f"Required Inlet Temp vs Flow\n"
    f"({pipe_type} | Nominal {nominal_choice} | OD {od_in:.2f} in | ID {id_in:.2f} in | "
    f"Target: {T_out_target} °F | Ambient: {T_amb} °F | Wind: {wind_mph} mph)",
    color="#0E6251"
)
ax.set_xlabel("Flow (bbl/min)")
ax.set_ylabel("Required Inlet Temp (°F)")
ax.grid(True)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
st.pyplot(fig)

# ---------------- Notes ----------------
with st.expander("Notes / Tips"):
    st.markdown(f"""
- **HDPE IPS ODs:** 4″ → 4.500, 6″ → 6.625, 8″ → 8.625, 10″ → 10.750, 12″ → 12.750, … up to 24″.
- **Layflat TPU wall** fixed at **0.15″**.
- Wall thermal conductivity: TPU = 0.116, HDPE = 0.26 Btu/hr·ft·°F.
- Outside convection: h ≈ 1.5 + 0.25 × (wind mph).
- UA per mile (current inputs): {UA_per_mile:,.0f} Btu/hr·°F·mile
- UA total: {UA_total:,.0f} Btu/hr·°F
""")

