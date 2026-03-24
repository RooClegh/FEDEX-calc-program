import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re

# 1. 파일 설정
FILE_NAME = 'FEDEX_2026.csv'

# 2. 국가별 지역(Region) 매핑 (엑셀 하단부 데이터 기반)
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

# 기능 함수들
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
def load_fedex_data():
    if not os.path.exists(FILE_NAME): return None, None
    
    # 원본 로드 (전체)
    raw_df = pd.read_csv(FILE_NAME, skiprows=3, header=None).copy()
    
    # 컬럼명 설정 (엑셀 4행 기준)
    cols = ["중량(Kg)", "구분", "지역 A", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]
    
    # 💡 IP 섹션 추출 (5행 ~ 38행 예상)
    df_ip = raw_df.iloc[1:35, 0:13].copy()
    df_ip.columns = cols
    
    # 💡 IE 섹션 추출 (40행 ~ 67행 확인됨)
    # 엑셀 인덱스 기준으로는 skiprows=3이므로 36행부터 63행 정도가 됩니다.
    df_ie = raw_df.iloc[36:64, 0:13].copy()
    df_ie.columns = cols
    
    # 데이터 정제 함수
    def clean_df(target_df):
        for c in cols[2:]: # 지역 컬럼들
            target_df[c] = target_df[c].astype(str).str.replace(',', '').str.strip()
            target_df[c] = pd.to_numeric(target_df[c], errors='coerce').fillna(0)
        target_df['중량(Kg)'] = target_df['중량(Kg)'].astype(str).str.replace(' ', '').str.strip()
        return target_df

    return clean_df(df_ip), clean_df(df_ie)

# --- UI 레이아웃 ---
st.set_page_config(page_title="FedEx 운임 비교기", layout="wide")

st.title("✈️ FedEx 실데이터 운임 비교 (IP vs IE)")
st.caption("🏢 도착지: 부산광역시 사상구 새벽로215번길 123 동명베아링")

df_ip, df_ie = load_fedex_data()

if df_ip is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    if 'current_fuel_rate' not in st.session_state:
        st.session_state.current_fuel_rate = get_fedex_fuel_surcharge()

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("compare_form"):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
            c_idx = country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0
            country_in = st.selectbox("🌐 출발 국가", country_list, index=c_idx)
            zip_in = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with c2:
            weight_in = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
        with c3:
            fuel_in = st.number_input("⛽ 유류할증료 (%)", value=st.session_state.current_fuel_rate, step=0.01)
        
        submitted = st.form_submit_button("운임 비교 결과 보기", use_container_width=True)

    if submitted:
        target_region = COUNTRY_REGION_MAP[country_in]
        if zip_in and country_in == "미국":
            target_region = get_us_zone(zip_in)
        
        up_w = math.ceil(weight_in * 2) / 2
        
        # 1. IP 가격 찾기
        ip_price = 0
        ip_match = df_ip[df_ip['중량(Kg)'] == str(up_w)]
        if not ip_match.empty:
            ip_price = float(ip_match.iloc[0][target_region])

        # 2. IE 가격 찾기 (40~67행 데이터 사용)
        ie_price = 0
        ie_match = df_ie[df_ie['중량(Kg)'] == str(up_w)]
        if not ie_match.empty:
            ie_price = float(ie_match.iloc[0][target_region])

        # --- 출력 ---
        st.divider()
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("🚀 International Priority (IP)")
            st.caption("배송 속도: 1~3 영업일 (긴급)")
            if ip_price > 0:
                ip_fuel = ip_price * (fuel_in / 100)
                st.metric("총 합계", f"{int(ip_price + ip_fuel):,.0f} 원", f"기본: {int(ip_price):,.0f}")
                st.write(f"유류할증료: {int(ip_fuel):,.0f}원")
            else:
                st.warning("IP 요금 데이터를 찾을 수 없습니다.")

        with col_right:
            st.subheader("🐢 International Economy (IE)")
            st.caption("배송 속도: 4~6 영업일 (경제적)")
            if ie_price > 0:
                ie_fuel = ie_price * (fuel_in / 100)
                st.metric("총 합계", f"{int(ie_price + ie_fuel):,.0f} 원", f"기본: {int(ie_price):,.0f}", delta_color="inverse")
                st.write(f"유류할증료: {int(ie_fuel):,.0f}원")
                
                # 금액 절감액 표시
                diff = (ip_price + ip_fuel) - (ie_price + ie_fuel)
                if diff > 0:
                    st.success(f"💡 IP 대비 **{int(diff):,.0f}원** 저렴합니다!")
            else:
                st.warning("IE 요금 데이터를 찾을 수 없습니다. (1kg 미만은 IE가 없을 수 있음)")

st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")