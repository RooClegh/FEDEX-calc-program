import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정 (중앙 집중형으로 늘어짐 방지)
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="centered")

# CSS: 제목 크기(90px) 및 버튼/입력창 수평 정렬
st.markdown("""
    <style>
    /* 제목: 90px로 대폭 확대 및 중앙 정렬 */
    .main-title { 
        color: #ffffff !important; 
        font-weight: bold; 
        font-size: 70px !important; 
        text-align: center;
        margin-top: -30px;
        margin-bottom: 5px;
        line-height: 1.1;
    }
    
    /* 도착지 정보: 중앙 슬림 디자인 */
    .dest-info {
        color: #ffffff !important;
        border-left: 5px solid #FF6600;
        padding: 5px 15px;
        margin-bottom: 35px;
        font-size: 1.1rem;
        text-align: center;
        width: fit-content;
        margin-left: auto;
        margin-right: auto;
    }

    /* 모든 텍스트 및 라벨 흰색 고정 */
    label, .stWrite, .stCaption, p, .stMarkdown {
        color: #ffffff !important;
        font-weight: bold !important;
    }

    /* 버튼 높이를 유류할증료 입력창과 수평으로 일치 */
    div.stButton > button:first-child {
        background-color: #FF6600 !important;
        color: white !important;
        height: 3.1rem;
        font-weight: bold;
        border: none;
        width: 100%;
        margin-top: 28px; /* 입력창 라벨 높이만큼 여백 부여 */
        font-size: 1.1rem;
    }
    
    div.stButton > button:first-child:hover {
        background-color: #e65c00 !important;
    }

    /* 하단 링크 강조 */
    .footer-link {
        color: #FF6600 !important;
        text-decoration: underline;
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
        # 지역 정보 추출 (한 글자 대문자)
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

# --- 화면 구성 ---
df_ip, df_ie, region_map = load_all_data()

st.markdown('<p class="main-title">FEDEX 계산기</p>', unsafe_allow_html=True)
st.markdown('<div class="dest-info">도착지: 동명베아링 ｜ 부산광역시 사상구 새벽로215번길 123</div>', unsafe_allow_html=True)

if df_ip is None:
    st.error("데이터 파일을 찾을 수 없습니다. (FEDEX_2026.csv)")
else:
    # 1. 즐겨찾기 (단독 행)
    fav_options = {
        "직접 입력 (국가 선택)": {"country": "일본", "addr": ""},
        "TIMKEN (미국)": {"country": "미국", "addr": "4500 MOUNT PLEASANT ST NW NORTH CANTON, Ohio"},
        "IKO (일본)": {"country": "일본", "addr": "2-19-19 TAKANAWA MINARO-GU TOKYO"}
    }
    selected_fav = st.selectbox("⭐ 즐겨찾기 주소 선택", list(fav_options.keys()))
    fav_data = fav_options[selected_fav]

    # 2. 국가 및 중량 (중앙 집중형 2열)
    c1, c2 = st.columns(2)
    with c1:
        countries = sorted(list(region_map.keys()))
        # 엑셀 수정 반영: "미국"이 리스트에 있으면 해당 인덱스 선택
        try:
            default_idx = countries.index(fav_data["country"])
        except ValueError:
            default_idx = 0
            
        selected_country = st.selectbox("출발 국가", countries, index=default_idx)
    with c2:
        weight_input = st.number_input("화물 중량 (kg)", min_value=0.5, value=10.0, step=0.1)

    # 3. 유류할증료 및 계산 버튼 (수평 높이 일치)
    c3, c4 = st.columns(2)
    with c3:
        fuel_rate = st.number_input(
            "유류할증료 (%)", 
            value=41.75, 
            step=0.01, 
            help="주마다 변경되므로 FEDEX 사이트에서 확인 바랍니다."
        )
    with c4:
        calc_btn = st.button("🚀 예측 운임 계산하기")

    if fav_data["addr"]:
        st.caption(f"🏠 상세 주소: {fav_data['addr']}")

    # 결과 영역
    if calc_btn:
        target_region = region_map.get(selected_country, "지역 A")
        st.success(f"✅ {selected_country} ({target_region}) 요금 적용")
        
        ip_val, ip_w = calculate_fare(df_ip, weight_input, target_region)
        ie_val, ie_w = calculate_fare(df_ie, weight_input, target_region)
        
        st.divider()
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            with st.container(border=True):
                st.markdown('<p style="color:#4D148C; font-size:1.1rem;">🚀 Priority (IP)</p>', unsafe_allow_html=True)
                if ip_val:
                    total_ip = ip_val * (1 + fuel_rate/100)
                    st.metric("최종 예상액", f"{int(total_ip):,.0f} 원")
        with res_col2:
            with st.container(border=True):
                st.markdown('<p style="color:#4D148C; font-size:1.1rem;">🐢 Economy (IE)</p>', unsafe_allow_html=True)
                if ie_val:
                    total_ie = ie_val * (1 + fuel_rate/100)
                    st.metric("최종 예상액", f"{int(total_ie):,.0f} 원")

st.divider()
st.markdown('🔗 **유류할증료 확인:** <a href="https://www.fedex.com/ko-kr/shipping/surcharges.html" class="footer-link">FEDEX 사이트 바로가기</a>', unsafe_allow_html=True)
st.caption("© 2026 Dongmyeong Bearing | 제작: AI TFT 서주영 대리")