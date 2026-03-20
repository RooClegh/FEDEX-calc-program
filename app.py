import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 1. 고정 설정
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
    df = pd.read_csv(FILE_NAME, skiprows=3)
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

df = load_data()

if df is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    if 'current_fuel_rate' not in st.session_state:
        st.session_state.current_fuel_rate = get_fedex_fuel_surcharge()

    # 💡 자주 쓰는 주소를 폼 내부가 아닌 외부에서 먼저 정의
    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    # 💡 폼 제출 시 값을 명확히 가두기 위해 st.form 사용
    with st.form("calc_form"):
        c1, c2 = st.columns(2)
        with c1:
            country_list = sorted(list(COUNTRY_ZONE_MAP.keys()))
            try: def_idx = country_list.index(addr_info["country"])
            except: def_idx = 0
            country_input = st.selectbox("🌐 출발 국가", country_list, index=def_idx)
            zip_input = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with c2:
            weight_input = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            fuel_input = st.number_input("⛽ 적용 유류할증료 (%)", value=st.session_state.current_fuel_rate, step=0.01)
        
        # 버튼을 눌러야만 모든 값이 final_ 변수들에 담겨 계산됨
        submitted = st.form_submit_button("운임 계산 실행")

    if submitted:
        # 모든 값을 계산 시점에 고정
        f_country = country_input
        f_zip = zip_input
        f_weight = weight_input
        f_fuel = fuel_input
        
        target_zone = COUNTRY_ZONE_MAP[f_country]
        if f_zip and f_country == "미국":
            target_zone = get_us_zone(f_zip)
        
        up_weight = math.ceil(f_weight * 2) / 2
        
        final_base_price = 0
        method = ""
        match_found = False
        
        # 원본 데이터 df에서 값만 추출
        for i in range(len(df)):
            w_val = str(df.loc[i, '중량(kg)'])
            
            if w_val == str(int(up_weight)) or w_val == str(up_weight):
                final_base_price = float(df.loc[i, target_zone])
                method = "고정 운임 적용"
                match_found = True
                break
                
            if '-' in w_val:
                try:
                    s, e = map(float, w_val.split('-'))
                    if s <= up_weight <= e:
                        unit_p = float(df.loc[i, target_zone])
                        final_base_price = unit_p * up_weight
                        method = f"kg당 단가({unit_p:,.0f}원) 적용"
                        match_found = True
                        break
                except: continue

        if match_found:
            f_val = final_base_price * (f_fuel / 100)
            total = final_base_price + f_val
            
            st.balloons()
            st.success(f"### 결과: {selected_addr} ({f_country})")
            res_c1, res_c2 = st.columns(2)
            res_c1.write(f"기본 운임: **{int(final_base_price):,.0f}원**")
            res_c2.write(f"유류 할증료 ({f_fuel}%): **{int(f_val):,.0f}원**")
            st.markdown(f"## 총 합계: **{int(total):,.0f}원**")
            st.divider()
            st.caption(f"기준: {target_zone} / {method}")
        else:
            st.error("데이터를 찾을 수 없습니다.")

st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")