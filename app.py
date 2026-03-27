import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="centered")

# CSS: 대왕 제목 및 수평 정렬
st.markdown("""
    <style>
    .main-title { 
        color: #ffffff !important; 
        font-weight: bold; 
        font-size: 40px !important; 
        text-align: center;
        margin-top: -30px;
        margin-bottom: 5px;
    }
    .dest-info {
        color: #ffffff !important;
        border-left: 5px solid #FF6600;
        padding: 5px 15px;
        margin-bottom: 35px;
        font-size: 1rem;
        text-align: center;
        width: fit-content;
        margin-left: auto;
        margin-right: auto;
    }
    label, p, .stCaption { color: #ffffff !important; font-weight: bold !important; }
    div.stButton > button:first-child {
        background-color: #FF6600 !important;
        color: white !important;
        height: 3.1rem;
        font-weight: bold;
        margin-top: 28px;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

FILE_NAME = 'FEDEX_2026.csv'

@st.cache_data
def load_all_data():
    if not os.path.exists(FILE_NAME): return None, None, {}
    raw_df = pd.read_csv(FILE_NAME, header=None).fillna("")
    
    # --- 지역 맵 추출 로직 강화 ---
    region_map = {}
    for i, row in raw_df.iterrows():
        row_list = [str(val).strip() for val in row.values if str(val).strip()]
        if len(row_list) < 2: continue
        
        country_name = row_list[0]
        # 해당 행에서 '대문자 한 글자'인 지역 코드를 모두 찾음
        possible_regions = [v for v in row_list if len(v) == 1 and v.isalpha() and v.isupper()]
        
        if possible_regions and len(country_name) > 1:
            # 일본(Japan)의 경우 보통 P가 행에 포함되어 있음
            region_code = possible_regions[-1] 
            region_map[country_name] = f"지역 {region_code}"
    
    # 수동 보정 (만약 엑셀에서 못 읽어올 경우를 대비)
    if "일본" in region_map:
        region_map["일본"] = "지역 P"

    # IP/IE 섹션 구분
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

# 요금 계산 함수 (생략 없이 로직 유지)
def calculate_fare(df, weight, region_col):
    if df.empty or region_col not in df.columns: return None, weight
    target_w = math.ceil(weight * 2) / 2
    match = df[df['중량'].astype(str).str.strip() == (f"{target_w:.1f}" if target_w % 1 != 0 else f"{int(target_w)}")]
    
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
        if any(x in str(match['중량'].iloc[0]) or x in str(match['구분'].iloc[0]) for x in ['~', '-', '이상', 'kg당']):
            return base * target_w, target_w
        return base, target_w
    return None, target_w

# --- 화면 구현 ---
df_ip, df_ie, region_map = load_all_data()

st.markdown('<p class="main-title">FEDEX 계산기</p>', unsafe_allow_html=True)
st.markdown('<div class="dest-info">도착지: 동명베아링 ｜ 부산광역시 사상구 새벽로215번길 123</div>', unsafe_allow_html=True)

if df_ip is None:
    st.error("데이터 파일을 찾을 수 없습니다.")
else:
    fav_options = {
        "직접 입력 (국가 선택)": {"country": "일본"},
        "TIMKEN (미국)": {"country": "미국"},
        "IKO (일본)": {"country": "일본"}
    }
    selected_fav = st.selectbox("⭐ 즐겨찾기", list(fav_options.keys()))
    fav_data = fav_options[selected_fav]

    c1, c2 = st.columns(2)
    with c1:
        countries = sorted(list(region_map.keys()))
        default_idx = countries.index(fav_data["country"]) if fav_data["country"] in countries else 0
        selected_country = st.selectbox("출발 국가", countries, index=default_idx)
    with c2:
        weight_input = st.number_input("화물 중량 (kg)", min_value=0.5, value=10.0, step=0.1)

    c3, c4 = st.columns(2)
    with c3:
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01, help="FEDEX 사이트에서 확인")
    with c4:
        calc_btn = st.button("🚀 예측 운임 계산하기")

    if calc_btn:
        # 일본은 무조건 '지역 P' 열을 참조하도록 확정
        target_region = region_map.get(selected_country, "지역 A")
        st.success(f"✅ {selected_country} ({target_region}) 요금 적용")
        
        ip_val, ip_w = calculate_fare(df_ip, weight_input, target_region)
        ie_val, ie_w = calculate_fare(df_ie, weight_input, target_region)
        
        st.divider()
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            with st.container(border=True):
                st.write("🚀 Priority (IP)")
                if ip_val:
                    total_ip = ip_val * (1 + fuel_rate/100)
                    st.metric("최종 예상액", f"{int(total_ip):,.0f} 원")
        with res_col2:
            with st.container(border=True):
                st.write("🐢 Economy (IE)")
                if ie_val:
                    total_ie = ie_val * (1 + fuel_rate/100)
                    st.metric("최종 예상액", f"{int(total_ie):,.0f} 원")

st.divider()
st.caption("© 2026 Dongmyeong Bearing | 제작: AI TFT 서주영 대리")