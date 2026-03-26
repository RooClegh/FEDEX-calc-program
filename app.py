import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정 및 디자인 CSS 적용
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="wide")

# 스타일 정의: 보라색(#4D148C), 주황색(#FF6600)
st.markdown("""
    <style>
    .main-title { color: #4D148C; font-weight: bold; font-size: 2.2rem; margin-bottom: 5px; }
    .sub-title { color: #FF6600; font-weight: bold; font-size: 1.1rem; margin-bottom: 25px; }
    .purple-text { color: #4D148C; font-weight: bold; }
    .orange-text { color: #FF6600; font-weight: bold; }
    
    /* 입력 구역 카드 스타일 */
    .input-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    
    /* 버튼 커스텀 */
    div.stButton > button:first-child {
        background-color: #4D148C;
        color: white;
        height: 3em;
        font-weight: bold;
        border: none;
        width: 100%;
    }
    div.stButton > button:first-child:hover {
        background-color: #FF6600;
        color: white;
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

    cols = ["중량", "구분", "지역 A", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N", "지역 O", "지역 P", "지역 Q", "지역 R", "지역 S", "지역 T", "지역 U", "지역 V", "지역 W", "지역 X", "지역 Y"]
    
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

st.markdown('<p class="main-title">✈️ FEDEX 항공 운임 예측 계산기</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">동명베아링 AI Task Force Team (TFT) 전용 프로그램</p>', unsafe_allow_html=True)

if df_ip is None:
    st.error("데이터 파일(FEDEX_2026.csv)을 읽어올 수 없습니다.")
else:
    countries = sorted(list(region_map.keys()))
    
    # [입력 통합 카드 섹션]
    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    st.markdown('<p class="purple-text" style="font-size:1.2rem; margin-bottom:15px;">📋 운임 계산 설정</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 1, 1])
    
    with col1:
        default_idx = countries.index("일본") if "일본" in countries else 0
        selected_country = st.selectbox("출발 국가 선택", countries, index=default_idx)
        target_region = region_map[selected_country]
        st.write(f"📍 적용 지역: **{target_region}**")
        
    with col2:
        weight_input = st.number_input("화물 실중량 (kg)", min_value=0.5, value=10.0, step=0.1)
        
    with col3:
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01)
        
    calc_button = st.button("🚀 운임 계산하기")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- 계산 결과 출력 ---
    if calc_button:
        ip_val, ip_gb, ip_w = calculate_fare(df_ip, weight_input, target_region)
        ie_val, ie_gb, ie_w = calculate_fare(df_ie, weight_input, target_region)
        
        st.divider()
        res_col1, res_col2 = st.columns(2)
        
        with res_col1:
            st.markdown('<p class="purple-text" style="font-size:1.3rem;">🚀 International Priority (IP)</p>', unsafe_allow_html=True)
            if ip_val:
                total_ip = ip_val * (1 + fuel_rate/100)
                st.metric("예상 합계", f"{int(total_ip):,.0f} 원")
                st.caption(f"청구 중량: {ip_w}kg | 기본 운임: {int(ip_val):,.0f}원 ({ip_gb})")
            else: st.warning("IP 데이터 없음")

        with res_col2:
            st.markdown('<p class="purple-text" style="font-size:1.3rem;">🐢 International Economy (IE)</p>', unsafe_allow_html=True)
            if ie_val:
                total_ie = ie_val * (1 + fuel_rate/100)
                diff = (total_ip - total_ie) if ip_val else 0
                st.metric("예상 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                st.caption(f"청구 중량: {ie_w}kg | 기본 운임: {int(ie_val):,.0f}원 ({ie_gb})")
            else: st.info("IE 미지원 또는 데이터 없음")

# 푸터 및 주의사항
st.divider()
st.markdown('<p class="orange-text">⚠️ 운임 주의사항</p>', unsafe_allow_html=True)
st.markdown('<p class="orange-text" style="font-size:0.95rem; font-weight:normal;">본 계산기는 입력하신 무게를 바탕으로 한 예측치이며, 실제 청구 금액은 화물의 부피 중량(CBM) 및 현지 사정에 따라 달라질 수 있습니다.</p>', unsafe_allow_html=True)

st.write("📅 실시간 유류할증료 확인")
st.markdown('<a href="https://www.fedex.com/ko-kr/shipping/surcharges.html" target="_blank" style="color:#4D148C; font-weight:bold; text-decoration:none;">🔗 [FedEx 공식 홈페이지 바로가기]</a>', unsafe_allow_html=True)
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: 서주영 대리")