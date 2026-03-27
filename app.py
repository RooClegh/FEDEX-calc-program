import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="centered")

# CSS: 시스템 테마 대응 및 레이아웃
st.markdown("""
    <style>
    .main-title { font-weight: bold; font-size: 40px !important; text-align: center; margin-top: -30px; margin-bottom: 5px; }
    .dest-info { border-left: 5px solid #FF6600; padding: 5px 15px; margin-bottom: 35px; font-size: 1rem; text-align: center; width: fit-content; margin-left: auto; margin-right: auto; }
    label, p, .stCaption { font-weight: bold !important; }
    div.stButton > button:first-child { background-color: #FF6600 !important; color: white !important; height: 3.1rem; font-weight: bold; margin-top: 28px; width: 100%; border: none; }
    .footer-link { color: #FF6600 !important; text-decoration: underline; }
    </style>
    """, unsafe_allow_html=True)

FILE_NAME = 'FEDEX_2026.csv'

@st.cache_data
def load_all_data():
    if not os.path.exists(FILE_NAME): return None, None, {}
    # 한글 깨짐 방지를 위해 cp949 또는 utf-8-sig 시도
    try:
        raw_df = pd.read_csv(FILE_NAME, header=None, encoding='utf-8-sig').fillna("")
    except:
        raw_df = pd.read_csv(FILE_NAME, header=None, encoding='cp949').fillna("")
    
    # 1. 국가별 지역 코드 매핑 (IP, IE 각각 추출)
    region_map_ip = {}
    region_map_ie = {}
    
    for i, row in raw_df.iterrows():
        row_list = [str(val).strip() for val in row.values if str(val).strip()]
        if len(row_list) >= 3 and any(keyword in str(row[0]) for keyword in ["앤티가", "일본", "미국", "영국"]):
            country = row_list[0].split()[-1] # 한글 국가명 추출
            region_map_ip[country] = f"지역 {row[1]}"
            region_map_ie[country] = f"지역 {row[2]}" if row[2] else None

    # 일본 예외 처리 (서 대리님 요청 반영)
    if "일본" in region_map_ip:
        region_map_ip["일본"] = "지역 P"
        region_map_ie["일본"] = "지역 P"

    # 2. IP / IE 요금표 섹션 분리
    ip_start, ie_start = -1, -1
    for i, row in raw_df.iterrows():
        row_str = "".join([str(v) for v in row.values])
        if "Priority" in row_str and ip_start == -1: ip_start = i
        if "Economy" in row_str and ie_start == -1: ie_start = i

    cols = ["중량", "구분"] + [f"지역 {c}" for c in "ADEFGHIJKMNOPQRSTUVWXY"]
    
    def extract_section(start, end):
        df = raw_df.iloc[start:end, :].copy()
        # 요금 데이터가 있는 행만 필터링 (숫자나 Envelope, Pak 포함)
        df = df[df[0].astype(str).str.contains(r'\d|Envelope|Pak', na=False)]
        df = df.iloc[:, :len(cols)]
        df.columns = cols[:df.shape[1]]
        for c in df.columns[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.replace(' ', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    df_ip = extract_section(ip_start + 2, ie_start - 2)
    df_ie = extract_section(ie_start + 2, len(raw_df))
    
    return df_ip, df_ie, region_map_ip, region_map_ie

def calculate_fare(df, weight, region_col):
    if df.empty or not region_col or region_col not in df.columns: return None, weight
    
    # 0.5kg 단위 올림
    target_w = math.ceil(weight * 2) / 2
    
    # 1. 구간 요금 (0.5kg ~ 20.5kg) 찾기
    match = df[df['중량'].astype(str).str.strip() == (f"{target_w:.1f}" if target_w % 1 != 0 else f"{int(target_w)}")]
    
    # 2. 중량 요금 (21kg 이상 kg당 단가) 찾기
    if match.empty:
        for _, row in df.iterrows():
            w_label = str(row['중량'])
            # "21 - 44" 같은 범위나 "71 - 99" 같은 구간 확인
            nums = re.findall(r'\d+\.?\d*', w_label)
            if len(nums) >= 2 and float(nums[0]) <= weight <= float(nums[1]):
                match = pd.DataFrame([row]); break
            elif '이상' in w_label and weight >= float(nums[0]):
                match = pd.DataFrame([row]); break

    if not match.empty:
        base_val = float(match[region_col].iloc[0])
        w_text = str(match['중량'].iloc[0])
        # 중량당 단가인 경우 (단어에 '-'가 있거나 21kg 이상인 구간)
        if "-" in w_text or "이상" in w_text or weight >= 21:
            return base_val * weight, weight
        return base_val, target_w
    
    return None, weight

# --- 실행부 ---
df_ip, df_ie, reg_ip, reg_ie = load_all_data()

st.markdown('<p class="main-title">✈️ FEDEX 계산기</p>', unsafe_allow_html=True)
st.markdown('<div class="dest-info">도착지: 동명베아링 ｜ 부산광역시 사상구 새벽로215번길 123</div>', unsafe_allow_html=True)

if df_ip is None:
    st.error("파일을 읽을 수 없습니다.")
else:
    fav_options = {
        "직접 입력 (국가 선택)": "일본",
        "TIMKEN (미국)": "미국",
        "IKO (일본)": "일본"
    }
    selected_fav = st.selectbox("⭐ 즐겨찾기", list(fav_options.keys()))
    current_country = fav_options[selected_fav]

    c1, c2 = st.columns(2)
    with c1:
        countries = sorted(list(reg_ip.keys()))
        default_idx = countries.index(current_country) if current_country in countries else 0
        selected_country = st.selectbox("출발 국가", countries, index=default_idx)
    with c2:
        weight_input = st.number_input("화물 중량 (kg)", min_value=0.5, value=10.0, step=0.1)

    c3, c4 = st.columns(2)
    with c3:
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01, help="매주 업데이트되는 요율을 입력하세요.")
    with c4:
        calc_btn = st.button("🚀 예측 운임 계산하기")

    if calc_btn:
        target_ip_reg = reg_ip.get(selected_country)
        target_ie_reg = reg_ie.get(selected_country)
        
        st.info(f"📍 {selected_country} 적용 지역: [IP: {target_ip_reg} / IE: {target_ie_reg}]")
        
        ip_fare, _ = calculate_fare(df_ip, weight_input, target_ip_reg)
        ie_fare, _ = calculate_fare(df_ie, weight_input, target_ie_reg)
        
        st.divider()
        res1, res2 = st.columns(2)
        with res1:
            with st.container(border=True):
                st.write("🚀 Priority (IP)")
                if ip_fare:
                    total = ip_fare * (1 + fuel_rate/100)
                    st.metric("합계", f"{int(total):,.0f} 원")
                else: st.warning("요금 데이터 없음")
        with res2:
            with st.container(border=True):
                st.write("🐢 Economy (IE)")
                if ie_fare:
                    total = ie_fare * (1 + fuel_rate/100)
                    st.metric("합계", f"{int(total):,.0f} 원")
                else: st.warning("IE 서비스 미지원")

st.divider()
st.markdown('🔗 **유류할증료 확인:** <a href="https://www.fedex.com/ko-kr/shipping/surcharges.html" class="footer-link">FEDEX 사이트</a>', unsafe_allow_html=True)
st.caption("© 2026 Dongmyeong Bearing | 제작: AI TFT 서주영 대리")