import streamlit as st
import pandas as pd
import os
import math

# 1. 설정 및 매핑 데이터
FILE_NAME = 'FEDEX_2026.csv'

# 자주 쓰는 주소 설정 (TIMKEN, IKO)
FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
}

COUNTRY_REGION_MAP = {
    "중국(남부)": "지역 A", "중국(기타)": "지역 C", "홍콩": "지역 A", "대만": "지역 A",
    "일본": "지역 B", "태국": "지역 C", "말레이시아": "지역 C", "베트남": "지역 C",
    "인도": "지역 D", "미국": "지역 F", "캐나다": "지역 F", "독일": "지역 G",
    "프랑스": "지역 G", "영국": "지역 G", "이탈리아": "지역 G", "호주": "지역 F"
}

@st.cache_data
def load_and_split_data():
    if not os.path.exists(FILE_NAME): return None, None
    raw_df = pd.read_csv(FILE_NAME, skiprows=3, header=None).copy()
    cols = ["중량(Kg)", "구분", "지역 A", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]
    
    # 섹션 분리 (IP: 1-34행, IE: 36-63행 부근)
    df_ip = raw_df.iloc[1:35, 0:13].copy()
    df_ie = raw_df.iloc[36:64, 0:13].copy()
    
    def clean(df):
        df.columns = cols
        for c in cols[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['중량(Kg)'] = df['중량(Kg)'].astype(str).str.replace(' ', '').str.strip()
        return df

    return clean(df_ip), clean(df_ie)

def calculate_fare(df, weight, region):
    target_w = str(float(weight))
    if target_w.endswith('.0'): target_w = target_w.replace('.0', '')
    
    match = df[df['중량(Kg)'] == target_w]
    if not match.empty:
        return float(match.iloc[0][region]), "고정 운임"

    for i in range(len(df)):
        w_val = str(df.iloc[i]['중량(Kg)'])
        if '-' in w_val:
            try:
                start, end = map(float, w_val.split('-'))
                if start <= weight <= end:
                    unit_price = float(df.iloc[i][region])
                    return unit_price * weight, f"구간 단가 적용 (kg당 {unit_price:,.0f}원)"
            except: continue
    return 0, None

# --- UI 레이아웃 ---
st.set_page_config(page_title="동명베아링 항공운임 계산기", layout="wide")

st.title("✈️ FedEx 항공운임 비교 시스템")
st.info("📦 출발지 국가와 중량을 입력하면 IP와 IE 요금을 즉시 비교합니다.")

df_ip, df_ie = load_and_split_data()

if df_ip is None:
    st.error(f"파일({FILE_NAME})을 찾을 수 없습니다. 파일명을 확인해주세요.")
else:
    # 1. 입력부 (사이드바)
    with st.sidebar:
        st.header("📋 입력 정보")
        
        # 자주 쓰는 주소 선택 로직
        selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
        addr_info = FAVORITE_ADDRESSES[selected_addr]
        
        # 선택한 주소에 따라 기본값 자동 세팅
        country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
        c_idx = country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0
        
        country = st.selectbox("출발 국가 선택", country_list, index=c_idx)
        zip_code = st.text_input("출발지 ZIP CODE (미국 전용)", value=addr_info["zip"])
        weight = st.number_input("물건 중량 입력 (kg)", min_value=0.5, step=0.5, value=5.0)
        fuel_rate = st.number_input("현재 유류할증료 (%)", value=41.75, step=0.01)

    # 2. 계산 실행
    region = COUNTRY_REGION_MAP[country]
    # 미국 지역 판별 (동부/서부 구분 로직 필요 시 추가 가능)
    up_weight = math.ceil(weight * 2) / 2 
    
    ip_base, ip_note = calculate_fare(df_ip, up_weight, region)
    ie_base, ie_note = calculate_fare(df_ie, up_weight, region)

    # 3. 결과 출력
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🚀 빠른 배송 (IP)")
        if ip_base > 0:
            ip_fuel = ip_base * (fuel_rate / 100)
            st.metric("최종 합계(IP)", f"{int(ip_base + ip_fuel):,.0f} 원")
            st.write(f"• 기본 운임: {int(ip_base):,.0f}원 ({ip_note})")
            st.write(f"• 유류할증료: {int(ip_fuel):,.0f}원")
        else:
            st.warning("⚠️ IP 요금 데이터 없음")

    with col2:
        st.markdown("### 🐢 경제형 배송 (IE)")
        if ie_base > 0:
            ie_fuel = ie_base * (fuel_rate / 100)
            diff = (ip_base + (ip_base * fuel_rate/100)) - (ie_base + ie_fuel)
            st.metric("최종 합계(IE)", f"{int(ie_base + ie_fuel):,.0f} 원", delta=f"-{int(diff):,.0f}원", delta_color="normal")
            st.write(f"• 기본 운임: {int(ie_base):,.0f}원 ({ie_note})")
            st.write(f"• 유류할증료: {int(ie_fuel):,.0f}원")
        else:
            st.info("ℹ️ IE 서비스 미지원 구간")

    # 4. 하단 안내사항
    st.divider()
    st.warning("⚠️ **운임 주의사항**\n\n본 계산기는 운임표 기반 예측치이며, 실제 청구 금액은 화물의 크기(부피 중량), 통관 수수료 등에 따라 달라질 수 있습니다.")
    
    st.write("📅 **유류할증료 안내**")
    st.write("유류할증료 정보는 주 단위로 변동되므로 정확한 확인이 필요합니다.")
    st.markdown("[👉 FedEx 공식 유류할증료 확인하러 가기](https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html)")

# 5. 푸터
st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")