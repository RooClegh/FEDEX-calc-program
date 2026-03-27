import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="wide")

# CSS: 디자인 커스텀 (제목 크기 대폭 확대 및 흰색 고정)
st.markdown("""
    <style>
    /* 제목: 크기를 4rem으로 키우고 흰색 고정 */
    .main-title { 
        color: #ffffff !important; 
        font-weight: bold; 
        font-size: 4rem; 
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    
    /* 도착지 정보: 흰색, 슬림 디자인 */
    .dest-info {
        background-color: transparent;
        color: #ffffff !important;
        padding: 0px 15px;
        border-left: 5px solid #FF6600;
        margin-bottom: 35px;
        font-size: 1.1rem;
    }
    
    /* 모든 라벨 및 텍스트 흰색 강제 */
    label, .stWrite, .stCaption, .setting-header, p {
        color: #ffffff !important;
        font-weight: bold !important;
    }

    /* 버튼 스타일: 입력창과 높이 통일 및 주황색 강조 */
    div.stButton > button:first-child {
        background-color: #FF6600 !important;
        color: white !important;
        height: 3.1rem;
        font-weight: bold;
        border: none;
        width: 100%;
        margin-top: 28px; /* 라벨 높이 정렬용 */
        font-size: 1.1rem;
    }
    
    /* 결과 메트릭 글자색 조정 */
    [data-testid="stMetricValue"] {
        color: #4D148C !important;
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

# --- 메인 화면 로직 ---
df_ip, df_ie, region_map = load_all_data()

# 제목 (크기 대폭 확대)
st.markdown('<h1 class="main-title">✈️ FEDEX 항공 운임 예측 계산기</h1>', unsafe_allow_html=True)
# 도착지 정보 (슬림 표기)
st.markdown('<div class="dest-info">도착지: 동명베아링 ｜ 부산광역시 사상구 새벽로215번길 123</div>', unsafe_allow_html=True)

if df_ip is None:
    st.error("데이터 파일을 찾을 수 없습니다. (FEDEX_2026.csv)")
else:
    # 1. 즐겨찾기 주소 선택 (단독 행)
    fav_options = {
        "직접 입력 (국가 선택)": {"country": "일본", "addr": ""},
        "TIMKEN (미국)": {"country": "미국", "addr": "4500 MOUNT PLEASANT ST NW NORTH CANTON, Ohio, UNITED STATES, 44720"},
        "IKO (일본)": {"country": "일본", "addr": "2-19-19 TAKANAWA MINARO-GU TOKYO JAPAN 108-8586"}
    }
    selected_fav = st.selectbox("⭐ 즐겨찾기 주소 선택", list(fav_options.keys()))
    fav_data = fav_options[selected_fav]

    st.divider()

    # 2. 출발 국가 / 화물 중량 (수평 배치)
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        countries = sorted(list(region_map.keys()))
        # 즐겨찾기 선택 시 국가 자동 연동 (TIMKEN=미국, IKO=일본)
        default_idx = countries.index(fav_data["country"]) if fav_data["country"] in countries else 0
        selected_country = st.selectbox("출발 국가", countries, index=default_idx)
        if fav_data["addr"]:
            st.caption(f"🏠 상세 주소: {fav_data['addr']}")
            
    with row1_col2:
        weight_input = st.number_input("화물 중량 (kg)", min_value=0.5, value=10.0, step=0.1)

    # 3. 유류할증료 / 계산 버튼 (수평 배치 및 높이 정렬)
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01)
        
    with row2_col2:
        # 버튼과 입력창 높이를 맞추기 위해 상단 마진이 포함된 CSS 적용됨
        calc_button = st.button("🚀 예측 운임 계산하기")

    # --- 계산 실행 및 결과 ---
    if calc_button:
        target_region = region_map.get(selected_country, "지역 A")
        # 계산 버튼 누를 때만 적용 지역 표시
        st.success(f"✅ 확인된 적용 요금 지역: {target_region}")
        
        ip_val, ip_gb, ip_w = calculate_fare(df_ip, weight_input, target_region)
        ie_val, ie_gb, ie_w = calculate_fare(df_ie, weight_input, target_region)
        
        st.divider()
        res_c1, res_c2 = st.columns(2)
        
        with res_c1:
            with st.container(border=True):
                st.markdown('<p style="color:#4D148C; font-size:1.3rem;">🚀 International Priority (IP)</p>', unsafe_allow_html=True)
                if ip_val:
                    total_ip = ip_val * (1 + fuel_rate/100)
                    st.metric("최종 예상 합계", f"{int(total_ip):,.0f} 원")
                    st.caption(f"청구 중량: {ip_w}kg | 기본 운임: {int(ip_val):,.0f}원")
                else: st.warning("데이터 없음")

        with res_c2:
            with st.container(border=True):
                st.markdown('<p style="color:#4D148C; font-size:1.3rem;">🐢 International Economy (IE)</p>', unsafe_allow_html=True)
                if ie_val:
                    total_ie = ie_val * (1 + fuel_rate/100)
                    diff = (total_ip - total_ie) if ip_val else 0
                    st.metric("최종 예상 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                    st.caption(f"청구 중량: {ie_w}kg | 기본 운임: {int(ie_val):,.0f}원")
                else: st.info("IE 미지원 구간")

st.divider()
st.caption("© 2026 Dongmyeong Bearing | 제작: AI TFT 서주영 대리")