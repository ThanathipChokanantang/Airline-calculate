import streamlit as st
from google import genai
from google.genai.errors import APIError
import pandas as pd
import io
import json
import re # *** นำเข้า Regular Expression ***

# --- 1. ข้อมูลคงที่ (Constants) ---
AIRCRAFT_DATA = {
    "A320neo": {"eco": 156, "bc": 8, "first": 0, "fuel_cost": 708, "range_km": 6300},
    "A321neo": {"eco": 162, "bc": 12, "first": 0, "fuel_cost": 840, "range_km": 7400},
    "A350-900": {"eco": 288, "bc": 40, "first": 0, "fuel_cost": 1950, "range_km": 15000},
    "A350-900ULR": {"eco": 133, "bc": 48, "first": 8, "fuel_cost": 2095, "range_km": 18000},
    "B787-8": {"eco": 261, "bc": 30, "first": 0, "fuel_cost": 1370, "range_km": 13500},
    "B787-9": {"eco": 297, "bc": 36, "first": 0, "fuel_cost": 1650, "range_km": 14000},
    "B777-300ER": {"eco": 315, "bc": 40, "first": 8, "fuel_cost": 2080, "range_km": 13650},
}

CONTINENTS = [
    "Africa", "Antarctica", "Asia", "Europe", "North America", "Oceania", "South America"
]

# --- 2. การตั้งค่าหน้าเว็บและ Sidebar ---
st.set_page_config(
    page_title="✈️ Airline Route Calculator (Gemini Powered)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar สำหรับ API Key
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Air_transport_icon_with_aeroplane.svg/1200px-Air_transport_icon_with_aeroplane.svg.png", width=100)
    st.title("⚙️ การตั้งค่า API")

    gemini_api_key = st.text_input(
        "**Google Gemini API Key**",
        key="gemini_api_key_input",
        type="password",
        help="API Key สำหรับเรียกใช้ Google Gemini."
    )

    if 'gemini_api_key' not in st.session_state or st.session_state.gemini_api_key != gemini_api_key:
        st.session_state.gemini_api_key = gemini_api_key

# --- 3. ฟังก์ชันจัดการ Gemini Client (ใช้ @st.cache_resource) ---

@st.cache_resource(show_spinner="กำลังตั้งค่า Gemini Client...")
def get_gemini_client(api_key: str):
    """สร้างและแคชออบเจกต์ Gemini Client"""
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการตั้งค่า Gemini Client: {e}")
        return None

def _get_active_client():
    """ดึง Client จาก cache resource"""
    return get_gemini_client(st.session_state.get('gemini_api_key', ''))

# ตรวจสอบ Client สถานะ
client = _get_active_client()
is_gemini_ready = client is not None and st.session_state.get('gemini_api_key', '')

# --- 4. ฟังก์ชันเรียกใช้ Gemini API ---

@st.cache_data(show_spinner="กำลังตรวจสอบความสอดคล้องของข้อมูล...")
def check_airport_consistency(icao_code: str, city_name: str, continent: str):
    client = _get_active_client()
    if client is None:
        return "API_ERROR: Gemini Client ไม่พร้อมใช้งาน"

    prompt = (
        f"ตรวจสอบความสอดคล้องของข้อมูลสนามบิน: ICAO Code: {icao_code}, City: {city_name}, Continent: {continent}. "
        "ถ้าข้อมูลสอดคล้อง (ตรงตามโลกจริง) ให้ตอบว่า 'PASS'. ถ้าไม่สอดคล้อง ให้ตอบว่า 'FAIL: [คำอธิบายว่าทำไมไม่ตรงกัน]'. "
    )
    
    # *** ลบ Mock Data สำหรับ Consistency Check ออก (ถ้ามี) ***
    
    # การเรียกใช้จริง:
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except APIError as e:
        return f"API_ERROR: ไม่สามารถเรียกใช้ Gemini ได้: {e}"
    except Exception as e:
         return f"FAIL: เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ: {e}"

@st.cache_data(show_spinner="กำลังคำนวณระยะทางบิน...")
def get_flight_distance(destination_icao: str):
    client = _get_active_client()
    if client is None:
        return 0

    destination_icao_upper = destination_icao.upper()

    prompt = (
        f"ค้นหาระยะทางบิน (Great Circle Distance) จากสนามบิน BKK (Suvarnabhumi, Bangkok, Thailand) "
        f"ไปยังสนามบินปลายทางที่มี ICAO code คือ {destination_icao_upper}. "
        "ให้แสดงผลเฉพาะ 'ระยะทางเป็นกิโลเมตร' เท่านั้น โดยเป็น **จำนวนเต็ม** และ **ไม่ใช่ค่าประมาณ**"
    )

    # *** ลบ Mock Response ทั้งหมดออก ***
    
    # การเรียกใช้จริง:
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        raw_text = response.text.strip()
        
        # *** การแก้ไข: ทำความสะอาดข้อความด้วย Regex ก่อนแปลงเป็นตัวเลข ***
        # 1. ค้นหาตัวเลขที่อยู่ติดกันทั้งหมดในข้อความ
        numbers = re.findall(r'\d+', raw_text)
        
        if numbers:
            # คืนค่าตัวเลขชุดแรกที่พบ (ควรเป็นระยะทาง)
            return int(numbers[0]) 
        else:
            # หากไม่พบตัวเลขเลย ให้คืนค่า 0
            return 0 
            
    except APIError as e:
        st.error(f"API_ERROR: ไม่สามารถคำนวณระยะทางได้: {e}")
        return 0
    except Exception as e:
        st.error(f"Error during distance calculation: {e}")
        return 0


# --------------------------------------------------------------------------------------
# ********** ฟังก์ชันที่ใช้ Step-by-Step Generation (ไม่เปลี่ยนแปลง) **********
# --------------------------------------------------------------------------------------

def generate_aircraft_data(client, aircraft_model, distance_km, destination_icao, destination_city):
    """
    ฟังก์ชันย่อย: ให้ Gemini คำนวณข้อมูล 11 คอลัมน์สำหรับเครื่องบินแต่ละรุ่นในรูปแบบ JSON
    """
    aircraft_info = AIRCRAFT_DATA.get(aircraft_model, {})
    
    # ถ้าพิสัยบินไม่พอ ให้ข้ามการเรียก API และคืนข้อมูล 0.0 ดาวทันที
    if distance_km > aircraft_info.get("range_km", 0):
        return [
            aircraft_model, aircraft_info.get("range_km", "N/A"), 
            f'{aircraft_info.get("eco", 0)}/{aircraft_info.get("bc", 0)}/{aircraft_info.get("first", 0)}',
            aircraft_info.get("fuel_cost", "N/A"), "N/A/N/A", "N/A/N/A", 0, "N/A", "N/A", 0.0,
            f"เครื่องบินรุ่นนี้ ({aircraft_model}) มีพิสัยการบินไม่เพียงพอ ({aircraft_info.get('range_km', 0)} กม.) ที่จะบินตรงในเส้นทางนี้ ({distance_km} กม.) จึงได้คะแนน 0.0 ดาว"
        ]

    prompt = f"""
    สำหรับเส้นทาง BKK ไป {destination_city} ({destination_icao}) ระยะทาง {distance_km} กม.
    วิเคราะห์และคำนวณข้อมูลสำหรับเครื่องบินรุ่น {aircraft_model} ({aircraft_info}).

    ข้อมูลที่ต้องส่งคืน **ต้อง** เป็นรายการ (List) ที่มี **11 องค์ประกอบ** เรียงตามลำดับนี้:
    1. ชื่อรุ่นเครื่องบิน (String)
    2. พิสัยการบิน (กิโลเมตร) (Integer)
    3. จำนวนที่นั่ง (eco/bc/first) (String)
    4. อัตราสิ้นเปลือง (usd/hr) (Integer)
    5. คาดการณ์ผู้โดยสารขาไปต่อสัปดาห์ (eco/bc/first) (String)
    6. คาดการณ์ผู้โดยสารขากลับต่อสัปดาห์ (eco/bc/first) (String)
    7. ความถี่เที่ยวบิน (ไป+กลับ) ต่อสัปดาห์ที่เหมาะสม (Integer)
    8. เวลา Departure จาก BKK ที่เหมาะสม (String, ในรูปแบบ XX:XXน., XX:XXน.,...)
    9. เวลา Departure จากปลายทางที่เหมาะสม (String, ในรูปแบบ XX:XXน., XX:XXน.,...)
    10. ความเหมาะสม (Float, เช่น 4.5, 3.0, ห้ามใช้ 0.0 ถ้าบินถึง)
    11. สรุปสาเหตุ (String, 50-100 คำ ภาษาไทย, ห้ามมีเครื่องหมายจุลภาค)
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        data_list = json.loads(response.text)
        
        if isinstance(data_list, list) and len(data_list) == 11:
            return data_list
        else:
            st.warning(f"Gemini response structure incorrect for {aircraft_model}: Length {len(data_list)}")
            return [aircraft_model] + ["N/A"] * 9 + [1.0] + [f"โครงสร้างข้อมูลที่ Gemini ส่งคืนไม่ถูกต้อง (ความยาว {len(data_list)})"]
            
    except Exception as e:
        st.error(f"Error generating data for {aircraft_model}: {e}")
        return [aircraft_model] + ["N/A"] * 9 + [1.0] + [f"เกิดข้อผิดพลาดในการเรียกใช้ API สำหรับเครื่องบินรุ่นนี้: {str(e)[:50]}"]


@st.cache_data(show_spinner="กำลังคาดการณ์ Demand และประเมินความเหมาะสมของเครื่องบิน...")
def get_aircraft_evaluation(distance_km: int, destination_icao: str, destination_city: str):
    """
    2.2 & 2.3: ประเมินเครื่องบินโดยการเรียก Gemini ซ้ำๆ สำหรับแต่ละรุ่น
    """
    client = _get_active_client()
    if client is None:
        return None
    
    all_data_rows = []
    
    aircraft_models = list(AIRCRAFT_DATA.keys())
    
    progress_bar = st.progress(0, text="กำลังประเมินเครื่องบิน 0/7 รุ่น...")

    for i, model in enumerate(aircraft_models):
        progress_bar.progress((i + 1) / len(aircraft_models), text=f"กำลังประเมินเครื่องบิน {i+1}/{len(aircraft_models)} รุ่น: {model}...")
        
        row = generate_aircraft_data(client, model, distance_km, destination_icao, destination_city)
        all_data_rows.append(row)
        
    progress_bar.empty()

    if not all_data_rows:
        return None

    df = pd.DataFrame(all_data_rows)
    csv_string = df.to_csv(header=False, index=False)
    return csv_string


# --------------------------------------------------------------------------------------
# ********** โค้ดส่วนหลักของ Streamlit App (ไม่เปลี่ยนแปลง) **********
# --------------------------------------------------------------------------------------

st.title("✈️ Airline Route Calculator (Gemini Powered)")
st.caption("โปรแกรมคำนวณข้อมูลสายการบินสำหรับเส้นทางบินใหม่ โดยใช้ข้อมูลจริงจาก Google Gemini")

if not is_gemini_ready:
    st.warning("🚨 กรุณาใส่ **Google Gemini API Key** ใน Sidebar เพื่อใช้งานโปรแกรม")



st.header("1. เลือกเส้นทางบินปลายทาง")
col1, col2, col3 = st.columns(3)

with col1:
    icao_code = st.text_input(
        "**ICAO Code ของสนามบินปลายทาง**",
        placeholder="เช่น HKT",
        max_chars=4,
        key="icao_input"
    ).upper()

with col2:
    city_name = st.text_input(
        "**ชื่อเมืองที่สนามบินตั้งอยู่ (ภาษาอังกฤษ)**",
        placeholder="เช่น Phuket",
        key="city_input"
    )

with col3:
    continent = st.selectbox(
        "**ทวีป**",
        options=[""] + CONTINENTS,
        key="continent_select"
    )

# กำหนด Session State เริ่มต้น
if 'data_consistent' not in st.session_state:
    st.session_state.data_consistent = False
if 'distance_km' not in st.session_state:
    st.session_state.distance_km = 0
if 'evaluation_df' not in st.session_state:
    st.session_state.evaluation_df = None

# ปุ่มตรวจสอบความสอดคล้อง
if st.button("🔎 ตรวจสอบข้อมูลสนามบิน", disabled=not is_gemini_ready or not (icao_code and city_name and continent)):
    
    st.session_state.distance_km = 0  
    st.session_state.evaluation_df = None 
    st.session_state.data_consistent = False
    
    if is_gemini_ready:
        with st.spinner("กำลังตรวจสอบข้อมูลกับ Gemini..."):
            consistency_result = check_airport_consistency(icao_code, city_name, continent)

        if consistency_result.startswith("PASS"):
            st.success("✅ ข้อมูลสนามบินสอดคล้อง! ดำเนินการขั้นตอนถัดไป")
            st.session_state.data_consistent = True
        elif consistency_result.startswith("FAIL"):
            st.session_state.data_consistent = False
            error_message = consistency_result.split("FAIL:")[1].strip() if "FAIL:" in consistency_result else consistency_result
            st.error(f"❌ ข้อมูลไม่สอดคล้อง: {error_message}")
        elif consistency_result.startswith("API_ERROR"):
            st.session_state.data_consistent = False
            st.error(consistency_result)
        else:
            st.warning(f"⚠️ ไม่สามารถตีความผลลัพธ์การตรวจสอบได้: {consistency_result}.")
            st.session_state.data_consistent = False



if st.session_state.data_consistent:
    st.header("2. การประเมินเส้นทางบินและรุ่นเครื่องบิน")

    # 2.1 ค้นหาระยะทางบิน
    if st.session_state.distance_km == 0:
        with st.spinner(f"กำลังค้นหาระยะทางบิน BKK ไป {icao_code}..."):
            distance = get_flight_distance(icao_code)
            st.session_state.distance_km = distance
    else:
        distance = st.session_state.distance_km

    if distance > 0:
        st.info(f"📏 **ระยะทางบิน (BKK -> {icao_code}):** **{distance:,} กิโลเมตร**")

        # 2.2 & 2.3 การประเมินเครื่องบินและการแสดงผล
        if st.session_state.evaluation_df is None:
            csv_result = get_aircraft_evaluation(distance, icao_code, city_name)
                
            if csv_result and not csv_result.startswith("API_ERROR"):
                try:
                    df = pd.read_csv(io.StringIO(csv_result), header=None)
                    
                    if df.shape[1] == 11:
                        df.columns = [
                            "ชื่อรุ่นเครื่องบิน", "พิสัยการบิน (กม.)", "จำนวนที่นั่ง (eco/bc/first)", 
                            "อัตราสิ้นเปลือง (USD/hr)", "คาดการณ์ผู้โดยสารขาไป (eco/bc/first)", 
                            "คาดการณ์ผู้โดยสารขากลับ (eco/bc/first)", "ความถี่เที่ยวบิน (ไป+กลับ)/สัปดาห์", 
                            "เวลา Departure จาก BKK", "เวลา Departure จากปลายทาง", 
                            "ความเหมาะสม (ดาว)", "สรุปสาเหตุ"
                        ]
                        st.session_state.evaluation_df = df
                    else:
                        st.error(f"❌ Gemini ส่งข้อมูลกลับมาไม่ครบตามรูปแบบ (คาด 11 คอลัมน์ ได้ {df.shape[1]} คอลัมน์). โปรดลองอีกครั้ง")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผลข้อมูลจาก Gemini: {e}")

        if st.session_state.evaluation_df is not None:
            st.subheader("ตารางสรุปการประเมินรุ่นเครื่องบิน")
            
            def format_star(score):
                try:
                    score = float(score)
                except (ValueError, TypeError):
                    return "N/A"
                    
                if score == 0.0:
                    return "🚫 0.0 ดาว (บินไม่ถึง)"
                full_stars = int(score)
                half_star = "½" if score - full_stars >= 0.25 and score - full_stars < 0.75 else ""
                stars = "★" * full_stars
                return f"{stars}{half_star} ({score:.1f})"
            
            display_df = st.session_state.evaluation_df.copy()
            display_df['ความเหมาะสม (ดาว) Format'] = display_df['ความเหมาะสม (ดาว)'].astype(str).apply(format_star)
            
            st.dataframe(
                display_df[[
                    "ชื่อรุ่นเครื่องบิน", "พิสัยการบิน (กม.)", "จำนวนที่นั่ง (eco/bc/first)", 
                    "อัตราสิ้นเปลือง (USD/hr)", "คาดการณ์ผู้โดยสารขาไป (eco/bc/first)", 
                    "คาดการณ์ผู้โดยสารขากลับ (eco/bc/first)", "ความถี่เที่ยวบิน (ไป+กลับ)/สัปดาห์", 
                    "เวลา Departure จาก BKK", "เวลา Departure จากปลายทาง", 
                    "ความเหมาะสม (ดาว) Format", "สรุปสาเหตุ"
                ]],
                height=350,
                use_container_width=True,
                column_config={
                    "สรุปสาเหตุ": st.column_config.Column(
                        "สรุปสาเหตุ (50-100 คำ)",
                        help="สรุปเหตุผลการให้คะแนนความเหมาะสม",
                        width="large",
                    ),
                    "ความเหมาะสม (ดาว) Format": st.column_config.Column(
                        "ความเหมาะสม (ดาว)",
                        help="คะแนนความเหมาะสม (5 ดาว = เหมาะสมมาก)",
                    ),
                    "พิสัยการบิน (กม.)": st.column_config.NumberColumn(
                        "พิสัยการบิน (กม.)",
                        format="%d",
                    ),
                },
                hide_index=True
            )

            # 2.4 สร้าง dropdown ให้ user เลือก
            st.subheader("3. เลือกรุ่นเครื่องบินที่ต้องการใช้")
            
            try:
                available_aircraft = st.session_state.evaluation_df[
                    st.session_state.evaluation_df['ความเหมาะสม (ดาว)'].astype(float) > 0.0
                ]["ชื่อรุ่นเครื่องบิน"].tolist()
            except (ValueError, TypeError):
                 available_aircraft = st.session_state.evaluation_df["ชื่อรุ่นเครื่องบิน"].tolist()
            
            if not available_aircraft:
                 st.error("🚨 ไม่มีรุ่นเครื่องบินใดในรายการที่สามารถบินในเส้นทางนี้ได้! (ทุกรุ่นได้ 0 ดาว หรือข้อมูลผิดพลาด)")
            else:
                aircraft_selection = st.selectbox(
                    "**เลือกรุ่นเครื่องบินสำหรับเส้นทางนี้**",
                    options=available_aircraft,
                    key="aircraft_select_final"
                )

                if aircraft_selection:
                    selected_data = st.session_state.evaluation_df[
                        st.session_state.evaluation_df["ชื่อรุ่นเครื่องบิน"] == aircraft_selection
                    ].iloc[0]

                    st.success(f"✅ คุณเลือกรุ่น **{aircraft_selection}** แล้ว!")
                    
                    selected_star = display_df[display_df["ชื่อรุ่นเครื่องบิน"] == aircraft_selection]['ความเหมาะสม (ดาว) Format'].iloc[0]
                    
                    st.markdown(f"""
                    * **ความเหมาะสม:** **{selected_star}**
                    * **พิสัยการบิน:** {selected_data['พิสัยการบิน (กม.)']} กม.
                    * **ความถี่ที่แนะนำ:** {selected_data['ความถี่เที่ยวบิน (ไป+กลับ)/สัปดาห์']} เที่ยวบินต่อสัปดาห์
                    * **เวลา Departure BKK:** {selected_data['เวลา Departure จาก BKK']}
                    * **สรุปสาเหตุ:** {selected_data['สรุปสาเหตุ']}
                    """)
        else:
            st.warning("⚠️ ไม่สามารถแสดงตารางประเมินได้เนื่องจากเกิดข้อผิดพลาดในการรับข้อมูลจาก Gemini.")
    else:
        st.error(f"❌ ไม่สามารถคำนวณระยะทางบินจริงจาก BKK ไป {icao_code} ได้ หรือระยะทางเป็น 0. โปรดตรวจสอบ ICAO Code และลองอีกครั้ง")