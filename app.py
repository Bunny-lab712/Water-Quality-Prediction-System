import streamlit as st
import pandas as pd
import numpy as np
import os
import random
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
import requests
import time
import plotly.graph_objects as go
from fpdf import FPDF
import tempfile
import base64
from twilio.rest import Client
from dotenv import load_dotenv

# Load the secret passwords from the .env file
load_dotenv()

# ==========================================
# SATELLITE WEATHER API (OPEN-METEO)
# ==========================================
def fetch_satellite_temperature(lat=18.4386, lon=79.1288):
    """Fetches live temperature data for Karimnagar using satellite weather data"""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url, timeout=5)
        data = response.json()
        return float(data['current_weather']['temperature'])
    except Exception as e:
        return 28.5 

# ==========================================
# STATIC IMAGES 
# ==========================================
IMG_SAFE = "https://cdn-icons-png.flaticon.com/512/190/190411.png"     
IMG_WARNING = "https://cdn-icons-png.flaticon.com/512/564/564619.png"  
IMG_DANGER = "https://cdn-icons-png.flaticon.com/512/190/190406.png"   

def get_image_html(img_url):
    return f'<img src="{img_url}" style="width: 140px; height: 140px; border: none; margin: 10px auto; display: block; object-fit: contain;">'

# ==========================================
# PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(page_title="Water Quality Prediction and Monitoring System", page_icon="💧", layout="wide")

st.markdown("""
    <style>
    .critical-alert { background-color: #ffcccc; padding: 20px; border-left: 5px solid #cc0000; border-radius: 5px; color: #cc0000; font-weight: bold; }
    .safe-alert { background-color: #ccffcc; padding: 20px; border-left: 5px solid #009900; border-radius: 5px; color: #006600; font-weight: bold; }
    .warning-alert { background-color: #ffffcc; padding: 20px; border-left: 5px solid #cccc00; border-radius: 5px; color: #888800; font-weight: bold; }
    
    @keyframes blink-warning { 0% { background-color: rgba(255, 204, 0, 0.05); border-color: #ffcc00; } 50% { background-color: rgba(255, 204, 0, 0.3); border-color: #ff9900; } 100% { background-color: rgba(255, 204, 0, 0.05); border-color: #ffcc00; } }
    @keyframes blink-danger { 0% { background-color: rgba(204, 0, 0, 0.05); border-color: #cc0000; } 50% { background-color: rgba(204, 0, 0, 0.25); border-color: #ff1a1a; } 100% { background-color: rgba(204, 0, 0, 0.05); border-color: #cc0000; } }

    .anim-safe { border: 2px solid #00cc00; background-color: rgba(0, 204, 0, 0.05); color: #006600; }
    .anim-warning { animation: blink-warning 1.5s infinite; border: 2px solid #ffcc00; color: #888800; }
    .anim-danger { animation: blink-danger 1s infinite; border: 2px solid #cc0000; color: #990000; }

    .diag-row { padding: 15px; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; font-size: 16px; }
    .avatar-card { padding: 30px; border-radius: 15px; text-align: center; height: 100%;}
    
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 18px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# WHATSAPP NOTIFICATION SYSTEM
# ==========================================
def send_whatsapp_alert(to_phone_number, alert_message):
    # Safely pull the passwords from the hidden .env file!
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=alert_message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to_phone_number}" 
        )
        return True
    except Exception as e:
        return str(e)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def create_gauge(value, title, min_val, max_val, safe_min, safe_max):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = value, title = {'text': title, 'font': {'size': 18}},
        gauge = {'axis': {'range': [min_val, max_val]}, 'bar': {'color': "black"},
                 'steps': [{'range': [min_val, safe_min], 'color': "#ffcccc"}, 
                           {'range': [safe_min, safe_max], 'color': "#ccffcc"}, 
                           {'range': [safe_max, max_val], 'color': "#ffcccc"}],
                 'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': value}}
    ))
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
    return fig

# ==========================================
# MACHINE LEARNING
# ==========================================
@st.cache_resource
def build_ml_models():
    file_name = "historical_water_data_v2.csv"
    if not os.path.exists(file_name):
        data = []
        for _ in range(500):
            turb, tds, temp = round(random.uniform(1.0, 30.0), 1), round(random.randint(100, 1500), 1), round(random.uniform(10.0, 45.0), 1)
            if tds < 600 and turb < 10 and 15.0 <= temp <= 32.0:
                qual, yld, days = 'Good', random.randint(85, 100), random.randint(115, 125)
            elif tds < 1000 and turb < 20 and 10.0 <= temp <= 38.0:
                qual, yld, days = 'Moderate', random.randint(65, 84), random.randint(126, 135)
            else:
                qual, yld, days = 'Poor', random.randint(30, 64), random.randint(136, 155)
            data.append([turb, tds, temp, qual, yld, days])
        pd.DataFrame(data, columns=['Turbidity', 'TDS', 'Temperature', 'Quality', 'Yield_Health_Pct', 'Growth_Days']).to_csv(file_name, index=False)
        
    df_train = pd.read_csv(file_name)
    X = df_train[['Turbidity', 'TDS', 'Temperature']]
    return (RandomForestClassifier(n_estimators=50, random_state=42).fit(X, df_train['Quality']),
            RandomForestRegressor(n_estimators=50, random_state=42).fit(X, df_train['Yield_Health_Pct']))

rf_classifier, rf_yield = build_ml_models()

def fetch_node_data():
    try:
        res = requests.get("https://script.google.com/macros/s/AKfycbx7XolVZUHhpJmNeUXRl4pAGONtX_kIDKt3eSckZozlODGyRSfFEibQqZWwAtmXKXB5ug/exec", timeout=10)
        df = pd.DataFrame(res.json())
        df.columns = df.columns.str.lower().str.replace(" ", "")
        return df
    except:
        return pd.DataFrame()

# ==========================================
# SIDEBAR 
# ==========================================
st.sidebar.title("Water Quality Prediction and Monitoring System")
st.sidebar.markdown("---")

app_mode = st.sidebar.radio("⚙️ System Mode:", ["📡 Live Field Data (ESP32)", "🎮 Simulator"])
st.sidebar.markdown("---")

st.sidebar.header("📱 WhatsApp Settings")
farmer_phone = st.sidebar.text_input("Enter WhatsApp Number (+91):", "+91")
enable_sms = st.sidebar.checkbox("Enable Auto-WhatsApp Alerts")

st.sidebar.markdown("---")
timer_placeholder = st.sidebar.empty() 

# ==========================================
# MAIN TITLE & DATA INGESTION
# ==========================================
st.title("💧 Water Quality Prediction and Monitoring System")

data_ready = False
if app_mode == "🎮 Simulator":
    st.info("💡 **Simulator Mode:** Slide values to see how the AI reacts across all domains simultaneously!")
    sim_col1, sim_col2, sim_col3 = st.columns(3)
    current_turb = sim_col1.slider("Mud/Dirt (NTU)", 0.0, 50.0, 3.2, 0.1)
    current_tds = sim_col2.slider("Salt Level (TDS)", 0.0, 3000.0, 220.0, 10.0)
    current_temp = sim_col3.slider("Karimnagar Temp (°C)", 5.0, 80.0, 26.0, 0.5)
    
    data_ready = True

elif "Live" in app_mode:
    df = fetch_node_data()
    if not df.empty:
        latest = df.iloc[-1]
        current_turb = float(latest.get('turbidity', 3.2))
        current_tds = float(latest.get('tds', 220))
        
        current_temp = fetch_satellite_temperature()
        st.success(f"🛰️ **Satellite Uplink Active:** Current ambient temperature is **{current_temp}°C**")
        
        data_ready = True
    else:
        st.warning("Connecting to ESP32 sensors... please wait.")
        time.sleep(3)
        st.rerun()

if data_ready:
    input_vector = np.array([[current_turb, current_tds, current_temp]])
    predicted_quality = rf_classifier.predict(input_vector)[0]
    base_score = rf_yield.predict(input_vector)[0]

    # --- INITIALIZE MESSAGE VARIABLES ---
    final_sms_agri = ""
    final_sms_drink = ""
    final_sms_ind = ""
    is_danger_agri = False
    is_danger_drink = False
    is_danger_ind = False

    tab1, tab2, tab3 = st.tabs(["🌾 Agriculture (రైతు మిత్ర)", "💧 Drinking Water (సురక్షిత జలం)", "🏭 Industrial Process (పరిశ్రమ మిత్ర)"])

    # ---------------------------------------------------------
    # TAB 1: AGRICULTURE
    # ---------------------------------------------------------
    with tab1:
        st.markdown("### Live Water Quality & AI Crop Yield Prediction")
        ui_remedies_agri, sms_lines_agri = [], []
        safe_tds_agri = 600
        
        if current_tds > safe_tds_agri:
            tds_status_a, tds_effect_a, tds_class_a, is_danger_agri = "TOO SALTY", "⚠️ Stunts crop growth.", "anim-danger", True
            ui_remedies_agri.append("🧂 **Too Salty:** Flush field with fresh water.")
            sms_lines_agri.append(f"❌ *TDS:* {current_tds} ppm\n*TE:* మంచి నీటితో కడగండి")
        else:
            tds_status_a, tds_effect_a, tds_class_a = "GOOD", "✅ Easy hydration.", "anim-safe"
            sms_lines_agri.append(f"✅ *TDS:* {current_tds} (Safe)")

        if current_turb > 10.0:
            turb_status_a, turb_effect_a, turb_class_a, is_danger_agri = "TOO MUDDY", "⚠️ Might block drip pipes.", "anim-warning", True
            ui_remedies_agri.append("🟤 **Too Muddy:** Clean pump filters.")
            sms_lines_agri.append(f"⚠️ *Mud:* {current_turb} NTU\n*TE:* పంపు ఫిల్టర్ శుభ్రం చేయండి")
        else:
            turb_status_a, turb_effect_a, turb_class_a = "CLEAR", "✅ Clean flow.", "anim-safe"
            sms_lines_agri.append(f"✅ *Mud:* {current_turb} (Clear)")

        if base_score > 80: 
            status_title_a, crop_class_a, health_msg_a, display_img_a = "Thriving", "anim-safe", "Crops are growing perfectly!", IMG_SAFE
        elif base_score > 60: 
            status_title_a, crop_class_a, health_msg_a, display_img_a = "Stressed", "anim-warning", "Crops are struggling.", IMG_WARNING
        else: 
            status_title_a, crop_class_a, health_msg_a, display_img_a = "In Danger", "anim-danger", "Crop failure risk!", IMG_DANGER

        diag_col1, avatar_col1 = st.columns([1.2, 1])
        with diag_col1:
            st.markdown(f"""
            <div class="diag-row {tds_class_a}"><div>🧂 Salt Level (TDS): {current_tds} ppm ({tds_status_a})</div><div style="font-size: 14px; font-weight: normal;">{tds_effect_a}</div></div>
            <div class="diag-row {turb_class_a}"><div>🟤 Dirt/Mud (NTU): {current_turb} ({turb_status_a})</div><div style="font-size: 14px; font-weight: normal;">{turb_effect_a}</div></div>
            <div class="diag-row anim-safe"><div>🌤️ Live Sat-Temp: {current_temp} °C</div><div style="font-size: 14px; font-weight: normal;">Optimal Growth Temp</div></div>
            """, unsafe_allow_html=True)
        with avatar_col1:
            st.markdown(f"""
            <div class="avatar-card {crop_class_a}">
                <h3 style='margin:0;'>Agriculture Status</h3>
                {get_image_html(display_img_a)}
                <h2 style='margin:0; font-size: 28px;'>{status_title_a}</h2>
                <p style='margin:0; font-weight:bold;'>{health_msg_a}</p>
                <p style='margin-top:5px;'>Predicted Yield: {base_score:.1f}%</p>
            </div>
            """, unsafe_allow_html=True)
        
        if is_danger_agri:
            final_sms_agri = f"🚨 *Water Quality Prediction and Monitoring System: AGRICULTURE ALERT* 🚨\n*Yield:* {base_score:.1f}%\n\n" + "\n\n".join([line for line in sms_lines_agri if "❌" in line or "⚠️" in line])
            for remedy in ui_remedies_agri: st.error(remedy)
        else:
            final_sms_agri = f"✅ *Water Quality Prediction and Monitoring System: AGRICULTURE NORMAL*\n*Yield:* {base_score:.1f}%\n\n" + "\n".join(sms_lines_agri) + "\n\n*TE:* సిస్టమ్ సురక్షితం."
            st.success("✅ **SYSTEM NORMAL:** All parameters within safe limits for crops.")
            
        st.subheader("📊 Agriculture Sensor Gauges")
        g1a, g2a = st.columns(2)
        with g1a: st.plotly_chart(create_gauge(current_turb, "Water Turbidity (NTU)", 0, 50, 0, 10), use_container_width=True)
        with g2a: st.plotly_chart(create_gauge(current_tds, "Salt Levels (TDS ppm)", 0, 1500, 0, safe_tds_agri), use_container_width=True)


    # ---------------------------------------------------------
    # TAB 2: DRINKING WATER
    # ---------------------------------------------------------
    with tab2:
        st.markdown("### Public Health & Potable Water Safety Monitor")
        ui_remedies_drink, sms_lines_drink = [], []
        safe_tds_drink = 300
        
        if current_tds > safe_tds_drink:
            tds_status_d, tds_effect_d, tds_class_d, is_danger_drink = "HARD WATER", "⚠️ Kidney stone risk.", "anim-danger", True
            ui_remedies_drink.append("🧂 **TDS High:** Route water through RO Membrane.")
            sms_lines_drink.append(f"❌ *TDS:* {current_tds} ppm\n*TE:* RO ఫిల్టర్ ఆన్ చేయండి")
        else:
            tds_status_d, tds_effect_d, tds_class_d = "POTABLE", "✅ Clean minerals.", "anim-safe"
            sms_lines_drink.append(f"✅ *TDS:* {current_tds} (Safe)")

        if current_turb > 2.0:
            turb_status_d, turb_effect_d, turb_class_d, is_danger_drink = "CLOUDY", "⚠️ High bacteria risk.", "anim-danger", True
            ui_remedies_drink.append("🟤 **Turbidity High:** Activate UV & Sand Filters.")
            sms_lines_drink.append(f"❌ *Turbidity:* {current_turb} NTU\n*TE:* ఫిల్టర్లు శుభ్రం చేయండి")
        else:
            turb_status_d, turb_effect_d, turb_class_d = "CLEAR", "✅ Visually pure.", "anim-safe"
            sms_lines_drink.append(f"✅ *Turbidity:* {current_turb} (Clear)")

        score_val_d = max(0, min(100, (100 - max(0, current_tds - 100)/10 - max(0, current_turb)*10)))
        
        if score_val_d > 80: 
            status_title_d, crop_class_d, health_msg_d, display_img_d = "Pure & Safe", "anim-safe", "Water is fully potable.", IMG_SAFE
        elif score_val_d > 50: 
            status_title_d, crop_class_d, health_msg_d, display_img_d = "Needs Filtration", "anim-warning", "Treat before drinking.", IMG_WARNING
        else: 
            status_title_d, crop_class_d, health_msg_d, display_img_d = "Contaminated", "anim-danger", "DO NOT DRINK!", IMG_DANGER

        diag_col2, avatar_col2 = st.columns([1.2, 1])
        with diag_col2:
            st.markdown(f"""
            <div class="diag-row {tds_class_d}"><div>🧂 Salt Level (TDS): {current_tds} ppm ({tds_status_d})</div><div style="font-size: 14px; font-weight: normal;">{tds_effect_d}</div></div>
            <div class="diag-row {turb_class_d}"><div>🟤 Dirt/Mud (NTU): {current_turb} ({turb_status_d})</div><div style="font-size: 14px; font-weight: normal;">{turb_effect_d}</div></div>
            <div class="diag-row anim-safe"><div>🌤️ Live Sat-Temp: {current_temp} °C</div><div style="font-size: 14px; font-weight: normal;">Ambient Normal</div></div>
            """, unsafe_allow_html=True)
        with avatar_col2:
            st.markdown(f"""
            <div class="avatar-card {crop_class_d}">
                <h3 style='margin:0;'>Drinking Water Status</h3>
                {get_image_html(display_img_d)}
                <h2 style='margin:0; font-size: 28px;'>{status_title_d}</h2>
                <p style='margin:0; font-weight:bold;'>{health_msg_d}</p>
                <p style='margin-top:5px;'>Potability Score: {score_val_d:.1f}%</p>
            </div>
            """, unsafe_allow_html=True)

        if is_danger_drink:
            final_sms_drink = f"🚨 *Water Quality Prediction and Monitoring System: DRINKING WATER ALERT* 🚨\n*Score:* {score_val_d:.1f}%\n\n" + "\n\n".join([line for line in sms_lines_drink if "❌" in line or "⚠️" in line])
            for remedy in ui_remedies_drink: st.error(remedy)
        else:
            final_sms_drink = f"✅ *Water Quality Prediction and Monitoring System: DRINKING WATER NORMAL*\n*Score:* {score_val_d:.1f}%\n\n" + "\n".join(sms_lines_drink)
            st.success("✅ **SYSTEM NORMAL:** Water is safe for human consumption.")
            
        st.subheader("📊 Drinking Water Gauges (Strict Limits)")
        g1d, g2d = st.columns(2)
        with g1d: st.plotly_chart(create_gauge(current_turb, "Water Turbidity (NTU)", 0, 10, 0, 2), use_container_width=True)
        with g2d: st.plotly_chart(create_gauge(current_tds, "Salt Levels (TDS ppm)", 0, 1500, 0, safe_tds_drink), use_container_width=True)


    # ---------------------------------------------------------
    # TAB 3: INDUSTRIAL PROCESS
    # ---------------------------------------------------------
    with tab3:
        st.markdown("### Effluent Compliance & Machinery Safety Dashboard")
        ui_remedies_ind, sms_lines_ind = [], []
        safe_tds_ind = 1500
        
        if current_tds > safe_tds_ind:
            tds_status_i, tds_effect_i, tds_class_i, is_danger_ind = "EXCEEDED LIMIT", "⚠️ Boiler breakdown risk.", "anim-danger", True
            ui_remedies_ind.append("🧂 **TDS Critical:** Open blowdown valves immediately.")
            sms_lines_ind.append(f"❌ *TDS:* {current_tds} ppm\n*TE:* బ్లోడౌన్ వాల్వ్ తెరవండి")
        else:
            tds_status_i, tds_effect_i, tds_class_i = "COMPLIANT", "✅ Normal operation.", "anim-safe"
            sms_lines_ind.append(f"✅ *TDS:* {current_tds} (Safe)")

        if current_temp > 45.0:
            temp_status_i, temp_effect_i, temp_class_i, is_danger_ind = "OVERHEATING", "⚠️ Equipment failure risk.", "anim-danger", True
            ui_remedies_ind.append("🌡️ **Temp Critical:** Increase cooling tower fan speed.")
            sms_lines_ind.append(f"❌ *Temp:* {current_temp} C\n*TE:* కూలింగ్ టవర్ ఆన్ చేయండి")
        else:
            temp_status_i, temp_effect_i, temp_class_i = "STABLE", "✅ Thermal compliance.", "anim-safe"
            sms_lines_ind.append(f"✅ *Temp:* {current_temp} (Stable)")

        score_val_i = (100.0 if not is_danger_ind else 40.0)
        
        if score_val_i == 100: 
            status_title_i, crop_class_i, health_msg_i, display_img_i = "Optimal Running", "anim-safe", "Factory running smoothly.", IMG_SAFE
        else: 
            status_title_i, crop_class_i, health_msg_i, display_img_i = "Equipment Warning", "anim-danger", "Check machinery immediately.", IMG_DANGER

        diag_col3, avatar_col3 = st.columns([1.2, 1])
        with diag_col3:
            st.markdown(f"""
            <div class="diag-row {tds_class_i}"><div>🧂 Salt Level (TDS): {current_tds} ppm ({tds_status_i})</div><div style="font-size: 14px; font-weight: normal;">{tds_effect_i}</div></div>
            <div class="diag-row anim-safe"><div>🟤 Dirt/Mud (NTU): {current_turb} (COMPLIANT)</div><div style="font-size: 14px; font-weight: normal;">✅ Safe for pipes</div></div>
            <div class="diag-row {temp_class_i}"><div>🌡️ Factory Area Temp (°C): {current_temp} ({temp_status_i})</div><div style="font-size: 14px; font-weight: normal;">{temp_effect_i}</div></div>
            """, unsafe_allow_html=True)
        with avatar_col3:
            st.markdown(f"""
            <div class="avatar-card {crop_class_i}">
                <h3 style='margin:0;'>Industrial Status</h3>
                {get_image_html(display_img_i)}
                <h2 style='margin:0; font-size: 28px;'>{status_title_i}</h2>
                <p style='margin:0; font-weight:bold;'>{health_msg_i}</p>
                <p style='margin-top:5px;'>Compliance Score: {score_val_i:.1f}%</p>
            </div>
            """, unsafe_allow_html=True)

        if is_danger_ind:
            final_sms_ind = f"🚨 *Water Quality Prediction and Monitoring System: INDUSTRIAL ALERT* 🚨\n*Score:* {score_val_i:.1f}%\n\n" + "\n\n".join([line for line in sms_lines_ind if "❌" in line or "⚠️" in line])
            for remedy in ui_remedies_ind: st.error(remedy)
        else:
            final_sms_ind = f"✅ *Water Quality Prediction and Monitoring System: INDUSTRIAL NORMAL*\n*Score:* {score_val_i:.1f}%\n\n" + "\n".join(sms_lines_ind)
            st.success("✅ **SYSTEM NORMAL:** All industrial parameters compliant.")
            
        st.subheader("📊 Industrial Gauges")
        g1i, g2i = st.columns(2)
        with g1i: st.plotly_chart(create_gauge(current_temp, "Facility Temp (°C)", 0, 100, 0, 45), use_container_width=True)
        with g2i: st.plotly_chart(create_gauge(current_tds, "Salt Levels (TDS ppm)", 0, 3000, 0, safe_tds_ind), use_container_width=True)

    # =========================================================
    # GLOBAL MANUAL DISPATCH PANEL (BELOW TABS)
    # =========================================================
    st.markdown("---")
    st.subheader("📤 Manual Alert Dispatch")
    st.write("Push the current live status report directly to the provided WhatsApp number.")
    
    colA, colB, colC = st.columns(3)
    
    with colA:
        if st.button("🌾 Send Agri Report", use_container_width=True):
            if farmer_phone and farmer_phone != "+91":
                send_whatsapp_alert(farmer_phone, final_sms_agri)
                st.toast("Agriculture Report Sent!", icon="✅")
            else:
                st.error("Enter a valid WhatsApp number!")
                
    with colB:
        if st.button("💧 Send Drinking Report", use_container_width=True):
            if farmer_phone and farmer_phone != "+91":
                send_whatsapp_alert(farmer_phone, final_sms_drink)
                st.toast("Drinking Water Report Sent!", icon="✅")
            else:
                st.error("Enter a valid WhatsApp number!")
                
    with colC:
        if st.button("🏭 Send Industrial Report", use_container_width=True):
            if farmer_phone and farmer_phone != "+91":
                send_whatsapp_alert(farmer_phone, final_sms_ind)
                st.toast("Industrial Report Sent!", icon="✅")
            else:
                st.error("Enter a valid WhatsApp number!")

    # =========================================================
    # GLOBAL AUTO-ALERT DISPATCHER (1 MINUTE INTERVALS)
    # =========================================================
    if enable_sms and farmer_phone and farmer_phone != "+91" and "Live" in app_mode:
        if is_danger_agri:
            send_whatsapp_alert(farmer_phone, final_sms_agri)
            time.sleep(1) 
        if is_danger_drink:
            send_whatsapp_alert(farmer_phone, final_sms_drink)
            time.sleep(1)
        if is_danger_ind:
            send_whatsapp_alert(farmer_phone, final_sms_ind)
            time.sleep(1)

    if "Live" in app_mode:
        for seconds in range(60, 0, -1):
            timer_placeholder.write(f"⏳ Next System Check in: {seconds}s")
            time.sleep(1)
        st.rerun()