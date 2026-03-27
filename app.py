import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정 (중앙 집중형 레이아웃을 위해 레이아웃 설정을 뺍니다)
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="centered")

# CSS: 컴팩트 모드 및 텍스트 최적화
st.markdown("""
    <style>
    /* 전체 배경 및 폰트 설정 */
    .stApp { background-color: #1E1E1E; } /* 어두운 배경으로 가독성 상향 */
    
    /* 제목: 크고 흰색, 상단 여백 최소화 */
    .main-title { 
        color: #ffffff !important; 
        font-weight: bold; 
        font-size: 3.5rem; 
        margin-top: -50px;
        margin-bottom: 5px;
    }
    
    /* 도착지 정보: 작고 깔끔하게 */
    .dest-info {
        color: #cccccc !important;
        border-left: 3px solid #FF6600;
        padding-left: 10px;
        margin-bottom: 30px;
        font-size: 0.95rem;
    }

    /* 입력창 간격 조절: 칸 사이의 위아래 간격을 줄임 */
    .stSelectbox, .stNumberInput {
        margin-bottom: -10px !important;
    }

    /* 라벨 텍스트 크기 조절 */
    label p {
        font-size: 0.9rem !important;
        color: #ffffff !important;
    }

    /* 버튼 스타일: 컴팩트한 높이 */
    div.stButton > button:first-child {
        background-color: #FF6600 !important;
        color: white !important;
        height: 2.8rem;
        font-weight: bold;
        border: none;
        width: 100%;
        margin-top: 24px;
    }
    
    /* 결과 박스 투명도 조절 */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

FILE_NAME = 'FEDEX_2026.csv'

@st.cache_data
def load_all_data():
    if not os.path.exists(FILE_NAME): return None, None, {}
    raw_df = pd.read_csv(FILE_NAME, header=None).fillna("")
    region_map = {}
    for i, row in raw_df.iterrows():
        row_list = [str(val).strip() for val in row.values if str(val).strip()]
        if len(row_list) < 2: continue
        country_name = row_list[0]
        possible_regions = [v for v in row_list if len(v) == 1 and v.isalpha() and v.isupper()]
        if possible_regions and len(country_name) > 1:
            region_map[country_name] = f"지역 {possible_regions[-1]}"

    ip_idx, ie_idx = -1, -1
    for i, row in raw_df.iterrows():
        row_str = "".join([str(v) for v in row.values])
        if "Priority" in row_str and ip_idx == -1: ip_idx = i
        if "Economy" in row_str and ie_idx == -1: ie_idx = i

    cols = ["중량", "구분"] + [f"지역 {c}" for c in "ADEFGHIJKMNOPQRSTUVWXY"]
    
    def extract_section(start, end):
        df = raw_df.iloc[start:end, :].copy()
        df = df[df[0].astype(str).str.contains(r'\d|Envelope|Pak', na=False)]
        df = df.iloc[:, :len(cols)]
        df.columns = cols[:df.shape[1]]
        for c in df.columns[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.replace(' ', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    df_ip = extract_section(ip_idx + 2, ie_idx - 2)
    df_ie = extract_section(ie_idx + 2, len(raw_df))
    return df_ip, df_ie, region_map

def calculate_fare(df, weight, region_col):
    if df.empty or region_col not in df.columns: return None, None, weight
    target_w = math.ceil(weight * 2) / 2
    match = pd.DataFrame()
    target_str = f"{target_w:.1f}" if target_w % 1 != 0 else f"{int(target_w)}"
    match = df[df['중량'].astype(str).str.strip() == target_str]
    
    if match.empty:
        for _, row in df.iterrows():
            w_label = str(row['중량'])
            nums = re.findall(r'\d+', w_label)
            if len(nums) >= 2 and float(nums[0]) <= target_w <= float(nums[1]):
                match = pd.DataFrame([row]); break
            elif '이상' in w_label and target_w >= float(re.findall(r'\d+', w_label)[0]):
                match = pd.DataFrame([row]); break

    if not match.empty:
        base = float(match[region_col].iloc[0])
        gubun = str(match['구분'].iloc[0])
        w_txt = str(match['중량'].iloc[0])
        if any(x in w_txt or x in gubun for x in ['~', '-', '이상', 'kg당']):
            return base * target_w, gubun, target_w
        return base, gubun, target_w
    return None, None, target_w

# --- 화면 구성 ---
df_ip, df_ie, region_map = load_all_data()

st.markdown('<h1 class="main-title">✈️ FEDEX 계산기</h1>', unsafe_allow_html=True)
st.markdown('<div class="dest-info">도착지: 동명베아링 ｜ 부산 사상구 새벽로215번길 123</div>', unsafe_allow_html=True)

if df_ip is None:
    st.error("데이터 없음")
else:
    # 1. 즐겨찾기 (단독 행)
    fav_options = {
        "직접 입력 (국가 선택)": {"country": "일본", "addr": ""},
        "TIMKEN (미국)": {"country": "미국", "addr": "4500 MOUNT PLEASANT ST NW NORTH CANTON, Ohio"},
        "IKO (일본)": {"country": "일본", "addr": "2-19-19 TAKANAWA MINARO-GU TOKYO"}
    }
    selected_fav = st.selectbox("⭐ 즐겨찾기", list(fav_options.keys()))
    fav_data = fav_options[selected_fav]

    # 2. 국가 및 중량 (컴팩트하게 2열)
    c1, c2 = st.columns(2)
    with c1:
        countries = sorted(list(region_map.keys()))
        default_idx = countries.index(fav_data["country"]) if fav_data["country"] in countries else 0
        selected_country = st.selectbox("출발 국가", countries, index=default_idx)
    with c2:
        weight_input = st.number_input("화물 중량 (kg)", min_value=0.5, value=10.0, step=0.5)

    # 3. 할증료 및 버튼 (컴팩트하게 2열)
    c3, c4 = st.columns(2)
    with c3:
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01)
    with c4:
        calc_btn = st.button("🚀 운임 계산")

    # 결과 출력
    if calc_btn:
        target_region = region_map.get(selected_country, "지역 A")
        st.info(f"📍 {selected_country} - {target_region} 적용")
        
        ip_val, _, ip_w = calculate_fare(df_ip, weight_input, target_region)
        ie_val, _, ie_w = calculate_fare(df_ie, weight_input, target_region)
        
        res_c1, res_c2 = st.columns(2)
        with res_c1:
            total_ip = ip_val * (1 + fuel_rate/100) if ip_val else 0
            st.metric("Priority (IP)", f"{int(total_ip):,.0f}원")
        with res_c2:
            total_ie = ie_val * (1 + fuel_rate/100) if ie_val else 0
            st.metric("Economy (IE)", f"{int(total_ie):,.0f}원")

st.markdown('<hr style="border:0.5px solid #333;">', unsafe_allow_html=True)
st.caption("© 2026 Dongmyeong Bearing | AI TFT 서주영")