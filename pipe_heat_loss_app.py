st.sidebar.header("Pipe Selection")

pipe_type = st.sidebar.selectbox("Pipe Type", ["Layflat TPU", "HDPE"])

# Nominal diameters up to 24 in
nominal_options = ["4 in", "6 in", "8 in", "10 in", "12 in", 
                   "14 in", "16 in", "18 in", "20 in", "22 in", "24 in"]

nominal_choice = st.sidebar.selectbox("Nominal Diameter", nominal_options, index=nominal_options.index("12 in"))

if pipe_type == "Layflat TPU":
    od_in = float(nominal_choice.split()[0])  # OD ≈ nominal
    wall_in = 0.15
    id_in = od_in - 2 * wall_in
    k_wall = 0.116  # TPU thermal conductivity
else:
    # HDPE IPS OD map
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
    k_wall = 0.26  # HDPE thermal conductivity

st.sidebar.write(f"**Nominal Diameter:** {nominal_choice}")
st.sidebar.write(f"**Actual OD:** {od_in:.3f} in | **ID:** {id_in:.3f} in")

