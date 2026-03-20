import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 1. 설정
FILE_NAME = 'fedex_2026.csv' 

COUNTRY_ZONE_MAP = {
    "중국(남부)": "존 A", "홍콩": "존 A", "대만": "존 A",
    "일본": "존 B", "중국(기타)": "존 C", "태국": "존 C", "말레이시아": "존 C",
    "인도": "존 D", "캄보디아": "존 D", "몽골": "존 D",
    "미국": "존 F", "캐나다": "존 F", "호주": "존 F",
    "독일": "존 G", "영국": "존 G", "프랑스": "존 G",
    "러시아": "존 H", "우크라이나": "존 H", "루마니아": "존 H",
    "브라질": "존 I", "콜롬비아": "존 I", "아르헨티나": "존 I",
    "UAE": "존 J", "방글라데시": "존 J", "쿠웨이트": "존 J"
}

FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
}

# 2. 유류할증료 로드
def get_fedex_fuel_surcharge():
    url = "https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        all_rates = re.findall(r'(\d+\.\d+)%', soup.get_text())
        if all_rates: return float(all_rates[0])
    except: pass
    return 41.75

def get_us_zone(zip_code):
    try:
        prefix = int(str(zip_code)[:3])
        western = list(range(800, 817)) + list(range(832, 839)) + list(range(840, 848)) + \
                  list(range(850, 866)) + list(range(889, 899)) + list(range(900, 962)) + \
                  list(range(970, 995))
        return "존 E" if prefix in western else "존 F"
    except: return "존 F"

@st.cache_data
def load_data():
    if not os.path.exists(FILE_NAME): return None
    # 로딩 시점에 아예 새로운 객체로 복사
    df = pd.read_csv(FILE_NAME, skiprows=3).copy()
    df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    zone_cols = [c for c in df.columns if '존' in c]
    for col in zone_cols:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if '중량(kg)' in df.columns:
        df['중량(kg)'] = df['중량(kg)'].astype(str).str.replace(r'\s+', '', regex=True).str.strip()
    return df

# --- UI 레이아웃 ---
st.set_page_config(page_title="항공 운임 예측 계산기", layout="centered")

st.title("✈️ 항공 운임 예측 계산기")
st.caption("🏢 도착지: 부산광역시 사상구 새벽로215번길 123 동명베아링")

df_master = load_data()

if df_master is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    if 'current_fuel_rate' not in st.session_state:
        st.session_state.current_fuel_rate = get_fedex_fuel_surcharge()

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("main_calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            country_list = sorted(list(COUNTRY_ZONE_MAP.keys()))
            try: def_idx = country_list.index(addr_info["country"])
            except: def_idx = 0
            country_in = st.selectbox("🌐 출발 국가", country_list, index=def_idx)
            zip_in = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with col2:
            weight_in = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=5.0)
            fuel_in = st.number_input("⛽ 적용 유류할증료 (%)", value=st.session_state.current_fuel_rate, step=0.01)
        
        btn = st.form_submit_button("운임 계산 실행")

    if btn:
        # 1. 기본 설정 확정
        target_zone = COUNTRY_ZONE_MAP[country_in]
        if zip_in and country_in == "미국":
            target_zone = get_us_zone(zip_in)
        
        up_w = math.ceil(weight_in * 2) / 2
        
        # 2. 계산용 변수 초기화 (데이터프레임과 연결 차단)
        found_base_price = 0.0
        calc_method = ""
        is_success = False

        # 💡 [필살기] 데이터프레임의 행을 '값'으로만 필터링하여 매칭
        # (A) 고정 중량 행 먼저 찾기
        fixed_match = df_master[df_master['중량(kg)'].isin([str(int(up_w)), str(up_w)])]
        
        if not fixed_match.empty:
            # 첫 번째 일치하는 행의 값을 숫자로 가져옴
            found_base_price = float(fixed_match.iloc[0][target_zone])
            calc_method = "고정 운임 적용"
            is_success = True
        else:
            # (B) 고정 중량이 없으면 범위 구간 찾기
            for i in range(len(df_master)):
                w_str = str(df_master.loc[i, '중량(kg)'])
                if '-' in w_str:
                    try:
                        start, end = map(float, w_str.split('-'))
                        if start <= up_w <= end:
                            unit_p = float(df_master.loc[i, target_zone])
                            found_base_price = unit_p * up_w
                            calc_method = f"단가 적용 (kg당 {unit_p:,.0f}원)"
                            is_success = True
                            break
                    except: continue

        # 3. 최종 결과 출력 (입력값 fuel_in 사용)
        if is_success:
            fuel_amt = found_base_price * (fuel_in / 100)
            total_amt = found_base_price + fuel_amt
            
            st.balloons()
            st.success(f"### 결과: {selected_addr} ({country_in})")
            
            c1, c2 = st.columns(2)
            c1.write(f"기본 운임: **{int(found_base_price):,.0f}원**")
            c2.write(f"유류 할증료 ({fuel_in}%): **{int(fuel_amt):,.0f}원**")
            st.markdown(f"## 총 합계: **{int(total_amt):,.0f}원**")
            st.divider()
            st.caption(f"산출 기준: {target_zone} / {calc_method}")
        else:
            st.error("요금표에서 중량을 찾을 수 없습니다.")

st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")