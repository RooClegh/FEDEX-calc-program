import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re

# 1. 파일 설정
FILE_NAME = 'FEDEX_2026.csv'

# 2. [업데이트] 국가별 지역(Region) 매핑 (엑셀 하단 데이터 기준)
COUNTRY_REGION_MAP = {
    "중국(남부)": "지역 A", "중국(기타)": "지역 C", "홍콩": "지역 A", "대만": "지역 A",
    "일본": "지역 B", "태국": "지역 C", "말레이시아": "지역 C", "인도네시아": "지역 C",
    "인도": "지역 D", "미국": "지역 F", "캐나다": "지역 F", "멕시코": "지역 F",
    "독일": "지역 G", "프랑스": "지역 G", "영국": "지역 G", "이탈리아": "지역 G",
    "베트남": "지역 C", "싱가포르": "지역 A", "호주": "지역 F", "브라질": "지역 I",
    "러시아": "지역 H", "UAE": "지역 J", "필리핀": "지역 C"
}

FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
}

# 3. 유류할증료 추출 및 미국 존 판별
def get_fedex_fuel_surcharge():
    url = "https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        rates = re.findall(r'(\d+\.\d+)%', soup.get_text())
        if rates: return float(rates[0])
    except: pass
    return 41.75

def get_us_zone(zip_code):
    try:
        prefix = int(str(zip_code)[:3])
        western = list(range(800, 817)) + list(range(832, 839)) + list(range(840, 848)) + \
                  list(range(850, 866)) + list(range(889, 899)) + list(range(900, 962)) + \
                  list(range(970, 995))
        return "지역 E" if prefix in western else "지역 F"
    except: return "지역 F"

@st.cache_data
def load_and_clean_data():
    if not os.path.exists(FILE_NAME): return None
    # 새 엑셀 구조에 맞춰 4행(index 3)부터 읽기 시작
    df = pd.read_csv(FILE_NAME, skiprows=3).copy()
    df.columns = df.columns.str.strip()
    
    # 금액 컬럼 숫자 변환 (쉼표 제거)
    region_cols = [c for c in df.columns if '지역' in c]
    for col in region_cols:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 중량 컬럼 정리
    if '중량(Kg)' in df.columns:
        df['중량(Kg)'] = df['중량(Kg)'].astype(str).str.replace(' ', '').str.strip()
    return df

# --- UI 레이아웃 ---
st.set_page_config(page_title="2026 항공 운임 계산기", layout="centered")
st.title("✈️ 2026 항공 운임 계산기 (IP Import)")
st.caption("🏢 도착지: 부산광역시 사상구 새벽로215번길 123 동명베아링")

df_master = load_and_clean_data()

if df_master is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    if 'current_fuel_rate' not in st.session_state:
        st.session_state.current_fuel_rate = get_fedex_fuel_surcharge()

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
            c_idx = country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0
            country_in = st.selectbox("🌐 출발 국가", country_list, index=c_idx)
            zip_in = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with col2:
            weight_in = st.number_input("📦 화물 중량 (kg)", min_value=0.1, step=0.5, value=1.0)
            fuel_in = st.number_input("⛽ 유류할증료 (%)", value=st.session_state.current_fuel_rate, step=0.01, help="FedEx 실시간 요율")
        
        submitted = st.form_submit_button("운임 계산 실행")

    if submitted:
        # 1. 지역 결정
        target_region = COUNTRY_REGION_MAP[country_in]
        if zip_in and country_in == "미국":
            target_region = get_us_zone(zip_in)
        
        # 2. 중량 올림 처리 (0.5 단위)
        up_w = math.ceil(weight_in * 2) / 2
        
        # 3. 가격 매칭 로직
        base_price = 0
        service_type = ""
        
        # 중량별 서비스 구분
        if weight_in <= 0.5: # Envelope 우선 확인 가능성 고려
            env_row = df_master[df_master['중량(Kg)'] == 'Envelope']
            if not env_row.empty:
                base_price = float(env_row.iloc[0][target_region])
                service_type = "Envelope"
        
        if base_price == 0: # Pak 또는 IP 탐색
            # 0.5kg ~ 2.5kg는 Pak 요금 우선 확인
            if weight_in <= 2.5:
                pak_match = df_master[(df_master['중량(Kg)'] == str(up_w)) & (df_master['구분'] == 'Pak')]
                if not pak_match.empty:
                    base_price = float(pak_match.iloc[0][target_region])
                    service_type = "FedEx Pak"

            # 일반 IP 요금 탐색 (위에서 못 찾았을 경우)
            if base_price == 0:
                ip_match = df_master[df_master['중량(Kg)'] == str(up_w)]
                if not ip_match.empty:
                    base_price = float(ip_match.iloc[0][target_region])
                    service_type = "International Priority (IP)"

        # 4. 결과 출력
        if base_price > 0:
            fuel_amt = base_price * (fuel_in / 100)
            total = base_price + fuel_amt
            
            st.balloons()
            st.success(f"### 결과: {country_in} ({target_region})")
            c1, c2 = st.columns(2)
            c1.write(f"기본 운임 ({service_type}): **{int(base_price):,.0f}원**")
            c2.write(f"유류 할증료 ({fuel_in}%): **{int(fuel_amt):,.0f}원**")
            st.markdown(f"## 총 합계: **{int(total):,.0f}원**")
            st.divider()
            st.caption(f"📅 [FedEx 공식 유류할증료 확인](https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html)")
        else:
            st.error("해당 중량의 요금 데이터를 찾을 수 없습니다.")

st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")