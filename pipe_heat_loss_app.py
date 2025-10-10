import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import math

# ---------------- Page / Branding ----------------
st.set_page_config(page_title="Pipeline Heat Loss Calculator", page_icon="💧", layout="centered")

# Logo (place logo.png next to this script)
try:
    st.image("logo.png", width=150)
except Exception:
    pass  # continue without logo if not found

# ---------------- Brighter Dark Theme CSS ----------------
st.markdown("""
<style>
body, .stApp {
    background-color: #1B1B1B;
    color: #EAEAEA;
}
section[data-testid="stSidebar"] {
    background-color: #242424;
}
h1, h2, h3 {
    color: #4DB6AC !important;
}
table {
    border-collapse: collapse;
    width: 100%;
    background-color: #242424;
    color: #EAEAEA;
}
th, td {
    text-align: center !important;
    border: 1px solid #444;
    padding: 8px;
}
tr:nth-child(even) { background-color: #2E2E2E; }
th { background-color: #0E6251; color: white; }
label, .stNumberInput label, .stSelectbox label { color: #EAEAEA !important; }

/* ----- Print Mode (white background) ----- */
@media print {
    body, .stApp, section[data-testid="stSidebar"] {
        background: white !important;
        color: black !important;
    }
    table {
        background: white !important;
        color: black !important;
        border-color: #999 !important;
    }
    th {
        background-color: #ddd !important;
        color: black !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ---------------- Physics helpers ----------------
def convective_h(wind_mph: float) -> float:
    return 1.5 + 0.25 * float(wind_mph)

def compute_UA_per_mile(r_i_ft: float, r_o_ft: float, k_wall: float, h_out: float) -> float:
    perimeter = 2 * np.pi * r_o_ft
    area_per_mile = perimeter * 5280.0
    R_wall = np.log(r_o_ft / r_i_ft) / (2 * np.pi * k_wall * 5280.0)
    R_out = 1.0 / (h_out * area_per_mile)
    return 1.0 / (R_wall + R_out)

def UA_per_mile_nested(inner_nom_in: float, outer_nom_in: float, wall_in: float,
                       k_wall: float, h_out: float, k_eff_air: float) -> float:
    def r_ft(d_in): return (d_in / 12.0) / 2.0
    r_o_inner = r_ft(inner_nom_in)
    r_i_inner = r_ft(inner_nom_in - 2.0*wall_in)
    r_o_outer = r_ft(outer_nom_in)
    r_i_outer = r_ft(outer_nom_in - 2.0*wall_in)

    R_inner = math.log(r_o_inner / r_i_inner) / (2 * math.pi * k_wall * 5280.0)
    R_air   = math.log(r_i_outer / r_o_inner) / (2 * math.pi * k_eff_air * 5280.0)
    R_outer = math.log(r_o_outer / r_i_outer) / (2 * math.pi * k_wall * 5280.0)
    A_out   = 2 * math.pi * r_o_outer * 5280.0
    R_o     = 1.0 / (h_out * A_out)
    return 1.0 / (R_inner + R_air + R_outer + R_o)

def inlet_temp_curve(T_amb, wind_mph, length_miles, id_in, wall_in, k_wall,
                     T_out_target, T_source, eff_frac, fuel_price, btu_per_unit,
                     flow_min=15, flow_max=60, flow_step=5,
                     nested_cfg=None):
    cp = 1.0  # Btu/lb-F
    lb_per_bbl = 42.0 * 8.34  # 350.28 lb/bbl

    r_i = (id_in / 12.0) / 2.0
    r_o = r_i + (wall_in / 12.0)
    h = convective_h(wind_mph)

    if nested_cfg is not None:
        UA_pm = UA_per_mile_nested(
            inner_nom_in=nested_cfg["inner_nom_in"],
            outer_nom_in=nested_cfg["outer_nom_in"],
            wall_in=wall_in,
            k_wall=k_wall,
            h_out=h,
            k_eff_air=nested_cfg["k_eff_air"]
        )
        if nested_cfg.get("add_5pct", True):
            UA_pm *= 1.05
    else:
        UA_pm = compute_UA_per_mile(r_i, r_o, k_wall, h)

    UA_total = UA_pm * float(length_miles)

    flows = np.arange(flow_min, flow_max + 1, flow_step, dtype=float)
    required_in, losses, heater_duties, outlet_vals, fuel_costs = [], [], [], [], []

    for f in flows:
        m_dot = f * lb_per_bbl * 60.0
        mcp = m_dot * cp
        k = UA_total / mcp if mcp > 0 else 0.0

        T_in_required = T_amb + (T_out_target - T_amb) * np.exp(k)
        required_in.append(T_in_required)
        Q_loss = mcp * (T_in_required - T_out_target)
        losses.append(Q_loss / 1e6)

        if T_source < T_in_required:
            Q_heater = mcp * (T_in_required - T_source)
            heater_duties.append(Q_heater / 1e6)
            outlet_vals.append(T_out_target)
            fuel_cost = ((Q_heater * 24) / eff_frac) / btu_per_unit * fuel_price
        else:
            Q_heater = 0
            heater_duties.append(0)
            outlet_vals.append(T_amb + (T_source - T_amb) * np.exp(-k))
            fuel_cost = 0

        fuel_costs.append(fuel_cost)

    df = pd.DataFrame({
        "Flow (bbl/min)": flows.astype(int),
        "Source Temp (°F)": T_source,
        "Required Inlet Temp (°F)": np.round(required_in, 1),
        "Outlet Temp (°F)": np.round(outlet_vals, 1),
        "Heat Loss (MMBtu/hr)": np.round(losses, 2),
        "Heater Duty (MMBtu/hr)": np.round(heater_duties, 2),
        "Daily Fuel Cost ($)": np.round(fuel_costs, 0)
    })
    return df, UA_pm, UA_total

# ---------------- Sidebar Inputs ----------------
st.sidebar.header("Pipe Selection")
pipe_type = st.sidebar.selectbox("Pipe Type", ["Layflat TPU", "HDPE", "Nested TPU Layflat"])

nominal_options = [f"{i} in" for i in range(4, 26, 2)]
nominal_choice = st.sidebar.selectbox("Nominal Diameter", nominal_options, index=nominal_options.index("12 in"))
nom_d_in = float(nominal_choice.split()[0])
nested_cfg = None

if pipe_type == "Layflat TPU":
    od_in = nom_d_in
    wall_in = 0.15
    id_in = od_in - 2 * wall_in
    k_wall = 0.116
elif pipe_type == "Nested TPU Layflat":
    inner_nom, outer_nom = nom_d_in, nom_d_in + 4.0
    wall_in = 0.15
    id_in = inner_nom - 2 * wall_in
    od_in = outer_nom
    k_wall = 0.116
    nested_cfg = {"inner_nom_in": inner_nom, "outer_nom_in": outer_nom, "k_eff_air": 0.08, "add_5pct": True}
else:  # HDPE
    HDPE_OD_MAP = {"4 in": 4.500, "6 in": 6.625, "8 in": 8.625, "10 in": 10.750,
                   "12 in": 12.750, "14 in": 14.000, "16 in": 16.000, "18 in": 18.000,
                   "20 in": 20.000, "22 in": 22.000, "24 in": 24.000}
    od_in = HDPE_OD_MAP[nominal_choice]
    dr_list = [7, 9, 11, 13.5, 17, 21, 26, 32.5]
    dr = st.sidebar.selectbox("HDPE DR Rating", dr_list, index=dr_list.index(17))
    wall_in = od_in / float(dr)
    id_in = od_in - 2 * wall_in
    k_wall = 0.26

# Brightened sidebar text
st.sidebar.markdown(f"<p style='color:#FFFFFF; font-weight:600;'>Nominal Diameter: {nominal_choice}</p>", unsafe_allow_html=True)
st.sidebar.markdown(f"<p style='color:#FFFFFF; font-weight:600;'>Actual OD: {od_in:.3f} in | ID: {id_in:.3f} in</p>", unsafe_allow_html=True)

# --- Sidebar Inputs ---
st.sidebar.header("Conditions")
T_source = st.sidebar.number_input("Source Water Temperature (°F)", value=35.0, step=1.0)
T_amb = st.sidebar.number_input("Ambient Temperature (°F)", value=0.0, step=5.0)
wind_mph = st.sidebar.number_input("Wind Speed (mph)", value=5.0, step=1.0)
length_miles = st.sidebar.number_input("Line Length (miles)", value=5.0, step=0.25)
T_out_target = st.sidebar.number_input("Desired Outlet Temp (°F)", value=35.0, step=1.0)

st.sidebar.header("Flow Range")
flow_min = st.sidebar.number_input("Min Flow (bbl/min)", value=15, step=5)
flow_max = st.sidebar.number_input("Max Flow (bbl/min)", value=120, step=5)
flow_step = st.sidebar.number_input("Flow Step (bbl/min)", value=5, step=5)

st.sidebar.header("Fuel & Heater Settings")
efficiency = st.sidebar.number_input("Heater Efficiency (%)", min_value=10, max_value=100, value=75, step=5)
fuel_type = st.sidebar.selectbox("Fuel Type", ["Propane", "Diesel", "Natural Gas"])
fuel_price = st.sidebar.number_input("Fuel Cost ($/unit)", value=2.30, step=0.01)

fuel_btu = {"Propane": 91500, "Diesel": 138700, "Natural Gas": 103000}
btu_per_unit = fuel_btu[fuel_type]
eff_frac = efficiency / 100.0

# ---------------- Run Calculation ----------------
df, UA_per_mile, UA_total = inlet_temp_curve(
    T_amb=T_amb, wind_mph=wind_mph, length_miles=length_miles,
    id_in=id_in, wall_in=wall_in, k_wall=k_wall,
    T_out_target=T_out_target, T_source=T_source,
    eff_frac=eff_frac, fuel_price=fuel_price, btu_per_unit=btu_per_unit,
    flow_min=flow_min, flow_max=flow_max, flow_step=flow_step,
    nested_cfg=nested_cfg
)

# ---------------- Print Button ----------------
st.markdown("""
<script>
function printPage() {
  window.print();
}
</script>
""", unsafe_allow_html=True)

st.markdown("<center><button onclick='printPage()' style='background:#4DB6AC; color:white; border:none; padding:10px 25px; font-size:16px; border-radius:8px; cursor:pointer;'>🖨️ Print Results</button></center>", unsafe_allow_html=True)

# ---------------- Results Table ----------------
st.subheader(
    f"Results Table (Source: {T_source} °F | Target Outlet: {T_out_target} °F | Ambient: {T_amb} °F | Wind: {wind_mph} mph)"
)
df_fmt = df.copy()
for c in ["Flow (bbl/min)", "Source Temp (°F)", "Required Inlet Temp (°F)", "Outlet Temp (°F)", "Heat Loss (MMBtu/hr)", "Heater Duty (MMBtu/hr)"]:
    if "Temp" in c:
        df_fmt[c] = df_fmt[c].map("{:.1f} °F".format)
    elif "Flow" in c:
        df_fmt[c] = df_fmt[c].map("{:.0f}".format)
    else:
        df_fmt[c] = df_fmt[c].map("{:.2f}".format)
df_fmt["Daily Fuel Cost ($)"] = df_fmt["Daily Fuel Cost ($)"].map(lambda x: f"${x:,.0f}")
st.markdown(df_fmt.to_html(index=False, justify="center"), unsafe_allow_html=True)

# ---------------- Chart ----------------
fig, ax = plt.subplots()
ax.plot(df["Flow (bbl/min)"], df["Required Inlet Temp (°F)"], marker="o", color="#4DB6AC", label="Required Inlet")
ax.plot(df["Flow (bbl/min)"], df["Outlet Temp (°F)"], marker="s", linestyle="--", color="orange", label="Outlet")
ax.set_title(f"Temperature Profiles vs Flow\n{pipe_type} | Nominal {nominal_choice} | OD {od_in:.2f} in | ID {id_in:.2f} in", color="#4DB6AC")
ax.set_xlabel("Flow (bbl/min)")
ax.set_ylabel("Temperature (°F)")
ax.grid(True, color="#444")
ax.set_facecolor("#1B1B1B")
ax.tick_params(colors="#EAEAEA")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend()
st.pyplot(fig)

# ---------------- Notes ----------------
with st.expander("Notes / Tips"):
    st.markdown(f"""
- **HDPE IPS ODs:** 4″ → 4.500, 6″ → 6.625, … up to 24″.
- **Layflat TPU wall** = 0.15″, k = 0.116.
- **HDPE wall** from DR, k = 0.26.
- **Nested TPU Layflat:** inner + outer TPU with 4″ gap, k_eff_air = 0.08, +5% UA.
- UA per mile: {UA_per_mile:,.0f} Btu/hr·°F·mile  
- UA total: {UA_total:,.0f} Btu/hr·°F
""")
