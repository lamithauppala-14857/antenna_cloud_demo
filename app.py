import streamlit as st
import skrf as rf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import tempfile

st.set_page_config(page_title="Advanced Antenna S-Parameter Analyzer", layout="wide")
st.title("Advanced Antenna S-Parameter Analyzer")

# Upload file
uploaded_file = st.file_uploader(
    "Upload S-parameter file (.s1p, .s2p, .s3p, .s4p, .csv)",
    type=["s1p","s2p","s3p","s4p","csv"]
)

if uploaded_file is not None:
    filename = uploaded_file.name.lower()

    # ----------------------------
    # CSV HANDLING
    # ----------------------------
    if filename.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        x_col = df.columns[0]
        y_cols = df.columns[1:]

        st.write(f"X-axis: **{x_col}**")
        st.write("Available S-parameters:", list(y_cols))

        # Option: linear or dB
        scale_option = st.radio("Select scale:", ["Linear", "dB"], index=1)

        # Multi-select for S-parameters
        selected_params = st.multiselect(
            "Select S-parameters to plot",
            y_cols,
            default=list(y_cols)
        )

        if selected_params:
            plot_df = df[selected_params].copy()
            if scale_option == "dB":
                plot_df = 20 * np.log10(plot_df)
            fig = px.line(
                df,
                x=x_col,
                y=selected_params,
                title=f"S-parameters (CSV Mode, {scale_option})"
            )
            fig.update_layout(
                xaxis_title=x_col,
                yaxis_title="|S| (dB)" if scale_option=="dB" else "|S| (linear)",
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)

        # Optional: convert CSV to .s2p for skrf compatibility
        convert_checkbox = st.checkbox("Convert CSV to dummy .s2p (for skrf plotting)")
        if convert_checkbox:
            mags = df.iloc[:,1:].values
            phases = np.zeros_like(mags)
            s_complex = mags * np.exp(1j*np.deg2rad(phases))
            freq_hz = df.iloc[:,0].values * 1e9  # treat first column as "frequency" in Hz

            # Create temp .s2p file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".s2p")
            with open(temp_file.name, "w") as f:
                f.write("# GHz S RI R 50\n")
                for i in range(len(freq_hz)):
                    # 2-port dummy example (adjust if more ports)
                    f.write(f"{freq_hz[i]/1e9:.6f} "
                            f"{s_complex[i,0].real:.6f} {s_complex[i,0].imag:.6f} "
                            f"{s_complex[i,1].real:.6f} {s_complex[i,1].imag:.6f} "
                            f"0 0 0 0\n")
            st.success(f"CSV converted to .s2p: {temp_file.name}")
            uploaded_file = temp_file.name  # allow skrf plotting below

    # ----------------------------
    # TOUCHSTONE HANDLING
    # ----------------------------
    try:
        net = rf.Network(uploaded_file)
        n_ports = net.nports
        st.write(f"Detected {n_ports}-port network")
        st.write(f"Frequency range: {net.f[0]/1e9:.2f} GHz – {net.f[-1]/1e9:.2f} GHz")

        # Frequency slider
        freq_min, freq_max = st.slider(
            "Select frequency range (GHz):",
            float(net.f[0]/1e9),
            float(net.f[-1]/1e9),
            (float(net.f[0]/1e9), float(net.f[-1]/1e9))
        )
        idx_min = np.argmin(np.abs(net.f/1e9 - freq_min))
        idx_max = np.argmin(np.abs(net.f/1e9 - freq_max)) + 1

        # Multi-select S-parameters
        options = [f"S{i+1}{j+1}" for i in range(n_ports) for j in range(n_ports)]
        selected_params = st.multiselect(
            "Select S-parameters to plot",
            options,
            default=[options[0]]
        )

        # Linear or dB
        scale_option = st.radio("Select scale:", ["Linear", "dB"], index=1, key="touchstone_scale")

        if selected_params:
            fig = go.Figure()
            for param in selected_params:
                i = int(param[1]) - 1
                j = int(param[2]) - 1
                y = np.abs(net.s[idx_min:idx_max,i,j])
                if scale_option=="dB":
                    y = 20*np.log10(y)
                fig.add_trace(go.Scatter(
                    x=net.f[idx_min:idx_max]/1e9,
                    y=y,
                    mode="lines",
                    name=param
                ))
            fig.update_layout(
                title=f"S-Parameters vs Frequency ({scale_option})",
                xaxis_title="Frequency (GHz)",
                yaxis_title="Magnitude |S| (dB)" if scale_option=="dB" else "Magnitude |S| (Linear)",
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error reading file with skrf: {e}")
