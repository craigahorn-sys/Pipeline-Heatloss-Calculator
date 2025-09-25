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
    pass  # run without logo if not found

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
    """Outside air film coefficient [Btu/hr-ft^2-F] using a simple linear model."""
    return 1.5 + 0.25 * float(wind_mph)

def compute_UA_per_mile(r_i_ft: float, r_o_ft: float, k_wall: float, h_out: float) -> float:
    """
    Returns UA per mile [Btu/hr-F-mile] for a bare cylindrical pipe/hose.
    r_i_ft, r_o_ft in feet; k_wall in Btu/hr-ft-F; h_out in Btu/hr-ft^2-F
    """
    perimeter = 2 * np.pi * r_o_ft                   # ft
    area_per_mile = perimeter * 5280.0               # ft^2 per mile
    # Wall + outside convection resistances (per mile)
    R_wall_per_mile = np.log(r_o_ft / r_i_ft) / (2 * np.pi * k_wall * 5280.0)
    R_out_per_mile = 1.0 / (h_out * area_per_mile)
    UA_per_mile = 1.0 / (R_wall_per_mile + R_out_per_mile)
    return UA_per_mile

def inlet_temp_curve(T_amb, wind_mph, length_miles, id_in, wall_in, k_wall, T_out_target,
                     flow_min=15, flow_max=60, flow_step=5):
    """
    Builds the required inlet temperature vs flow table for given geometry/conditions.
    id_in: inside diameter [in]; wall_in: wall thickness [in]; k_wall: wall thermal conductivity
    """
    cp = 1.0  # Btu/lb-F
    lb_per_bbl = 42.0 * 8.34  # 350.28 lb/bbl

    # Geometry in feet
    r_i = (id_in / 12.0) / 2.0
    r_o = r_i + (wall_in / 12.0)

    # Outside film
    h = convective_h(wind_mph)

    # UA per mile and total UA
    UA_per_mile = compute_UA_per_mile(r_i, r_o, k_wall, h)
    UA_total = UA_per_mile * float(length_miles)

    flows = np.arange(flow_min, flow_max + 1, flow_step, dtype=float)
    required_in = []
    for f in flows:
        m_dot = f * lb_per_bbl * 60.0            # lb/hr
        mcp = m_dot * cp                          # Btu/hr-F
        k = UA_total / mcp if mcp > 0 else 0.0
        T_in = T_amb + (T_out_target - T_amb) * np.exp(k)
        required_in.append(T_in)

    df = pd.DataFrame({
        "Flow (bbl/min)": flows.astype(int),
        "Required Inlet Temp (°F)": np.round(required_in, 1)
    })
    return df, UA_per_mile, UA_total

# ---------------- Sidebar Inputs ----------------
st.sidebar.header("Pipe Selection")

pipe_type = st.sidebar.selectbox("Pipe Type", ["Layflat TPU", "HDPE"])

# Outside Diameter input (used for both pipe types)
# For HDPE IPS examples: 10\" -> 10.75 OD, 12\" -> 12.75 OD
default_od = 12.30 if pipe_type == "Layflat TPU" else 12.75
od_in = st.sidebar.number_input(
    "Outside Diameter (in)",
    min_value=1.0, max_value=60.0, value=float(default_od), step=2.0,
    help="Enter OD in inches. For HDPE IPS: 10\"→10.75, 12\"→12.75 (enter actual OD)."
)

if pipe_type == "Layflat TPU":
    wall_in = 0.15  # fixed
    id_in = od_in - 2 * wall_in
    k_wall = 0.116  # TPU: Btu/hr-ft-F
else:
    dr_list = [7, 9, 11, 13.5, 17, 21, 26, 32.5]
    dr = st.sidebar.selectbox("HDPE DR Rating", dr_list, index=dr_list.index(17))
    wall_in = od_in / float(dr)  # inches
    id_in = od_in - 2 * wall_in
    k_wall = 0.26  # HDPE: Btu/hr-ft-F (≈0.45 W/m-K)

# Guard against invalid geometry
if id_in <= 0:
    st.sidebar.error("Calculated inside diameter ≤ 0. Check OD and DR/wall.")
st.sidebar.write(f"**Calculated Inside Diameter:** {id_in:.2f} in")
st.sidebar.caption("Geometry uses OD & wall to compute ID, then converts to feet for heat-loss math.")

st.sidebar.header("Conditions")
T_amb = st.sidebar.number_input("Ambient Temperature (°F)", value=-10.0, step=1.0)
wind_mph = st.sidebar.number_input("Wind Speed (mph)", value=20.0, step=1.0)
length_miles = st.sidebar.number_input("Line Length (miles)", value=9.5, step=0.1)
T_out_target = st.sidebar.number_input("Desired Outlet Temp (°F)", value=35.0, step=1.0)

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

# Pretty/centered table
df_formatted = df.copy()
df_formatted["Flow (bbl/min)"] = df_formatted["Flow (bbl/min)"].map("{:.0f}".format)
df_formatted["Required Inlet Temp (°F)"] = df_formatted["Required Inlet Temp (°F)"].map("{:.1f} °F".format)
st.markdown(df_formatted.to_html(index=False, justify="center"), unsafe_allow_html=True)

# ---------------- Chart ----------------
fig, ax = plt.subplots()
ax.plot(df["Flow (bbl/min)"], df["Required Inlet Temp (°F)"], marker="o", color="#0E6251")
ax.set_title(
    f"Required Inlet Temp vs Flow\n"
    f"({pipe_type} | OD {od_in:.2f} in | ID {id_in:.2f} in | "
    f"Target: {T_out_target} °F | Ambient: {T_amb} °F | Wind: {wind_mph} mph)",
    color="#0E6251"
)
ax.set_xlabel("Flow (bbl/min)")
ax.set_ylabel("Required Inlet Temp (°F)")
ax.grid(True)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
st.pyplot(fig)

# ---------------- Useful notes ----------------
with st.expander("Notes / Tips"):
    st.markdown("""
- **HDPE OD examples (IPS):** 10″ → **10.75** OD, 12″ → **12.75** OD. Enter **actual OD**.
- **Layflat TPU wall** fixed at **0.15″** here (adjustable if you want later).
- Wall thermal conductivity: **TPU ~0.116**, **HDPE ~0.26** Btu/hr·ft·°F.
- Outside convection: **h ≈ 1.5 + 0.25·(wind mph)** (simple exposed-cylinder model).
- UA per mile (current inputs): **{:,.0f} Btu/hr·°F·mile**; UA total: **{:,.0f} Btu/hr·°F**.
""".format(UA_per_mile, UA_total))


