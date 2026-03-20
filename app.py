import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 1. 설정 및 파일 경로
FILE_NAME = 'fedex_2026.csv' 

# 💡 [자주 쓰는 주소 설정] 업체별 국가와 ZIP CODE를 등록했습니다.
FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"},
    "독일 FAG 지사": {"country": "독일", "zip": "97421"},
    "중국 심천 창고": {"country": "중국(남부)", "zip": "518000"}
}

# 2. 실시간 유류할증료 추출 함수
def get_fedex_fuel_surcharge():
    url = "https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return 41.75
        soup = BeautifulSoup(response.text, 'html.parser')
        today = datetime.now()
        rows = soup.find_all('tr')
        for row in rows:
            row_text = row.get_text()
            if '월' in row_text and '%' in row_text:
                date_match = re.findall(r'(\d+)월\s*(\d+)일', row_text)
                percent_match = re.search(r'(\d+\.\d+)%', row_text)
                if date_match and percent_match:
                    month, day = map(int, date_match[0])
                    row_date = datetime(today.year, month, day)
                    if abs((today - row_date).days) <= 7:
                        return float(percent_match.group(1))
        all_rates = re.findall(r'(\d+\.\d+)%', soup.get_text())
        if all_rates: return float(all_rates[0])
    except: pass
    return 41.75

# 3. 미국 ZIP CODE 구역 판별 함수
def get_us_zone(zip_code):
    try:
        prefix = int(str(zip_code)[:3])
        western_prefixes = list(range(800, 817)) + list(range(832, 839)) + \
                           list(range(840, 848)) + list(range(850, 866)) + \
                           list(range(889, 899)) + list(range(900, 962)) + \
                           list(range(970, 995))
        return "존 E" if prefix in western_prefixes else "존 F"
    except: return "존 F"

# 4. 요금표 데이터 로드 함수
@st.cache_data
def load_data():
    if not os.path.exists(FILE_NAME): return None
    df = pd.read_csv(FILE_NAME, skiprows=3)
    df.columns = df.columns.str.replace('\n', ' ').str.strip()
    zone_cols = [f'존 {c}' for c in 'ABCDEFGHIJ']
    for col in zone_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    df['중량(kg)'] = df['중량(kg)'].astype(str).str.strip()
    return df

# --- UI 레이아웃 ---
st.set_page_config(page_title="동명베아링 FedEx 운임계산기", layout="centered")

with st.sidebar:
    st.header("🏠 물품 도착지")
    st.info("부산광역시 사상구 새벽로215번길 123\n\n**동명베아링**")
    st.divider()
    st.caption("Assistant Manager: 서주영 (AI TFT)")

st.title("✈️ FedEx 수입 항공운임 계산기")

df = load_data()

if df is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    current_fuel = get_fedex_fuel_surcharge()

    # 상단에서 업체 선택 시 아래 입력값이 자동으로 바뀝니다.
    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("main_form"):
        col1, col2 = st.columns(2)
        with col1:
            country_list = ["미국", "일본", "독일", "중국(남부)"]
            country = st.selectbox("🌐 출발 국가", country_list, 
                                  index=country_list.index(addr_info["country"]))
            zip_input = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with col2:
            weight_input = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            fuel_rate = st.number_input("⛽ 적용 유류할증료 (%)", value=current_fuel, step=0.01)
        
        calc_btn = st.form_submit_button("운임 계산 실행")

    if calc_btn:
        if not zip_input:
            st.warning("⚠️ 우편번호를 입력해 주세요.")
        else:
            if country == "미국": target_zone = get_us_zone(zip_input)
            elif country == "일본": target_zone = "존 B"
            elif country == "독일": target_zone = "존 G"
            else: target_zone = "존 A"

            up_weight = math.ceil(weight_input * 2) / 2
            w_str = str(up_weight) if up_weight % 1 != 0 else str(int(up_weight))
            
            match_row = df[df['중량(kg)'].str.fullmatch(w_str, na=False)]
            
            if not match_row.empty:
                base_val = match_row.iloc[0][target_zone]
                fuel_val = int(base_val * (fuel_rate / 100))
                total_val = base_val + fuel_val
                
                st.balloons()
                st.success(f"### 결과: {selected_addr if selected_addr != '직접 입력' else country} ({target_zone})")
                
                res1, res2, res3 = st.columns(3)
                res1.metric("기본 운임", f"{base_val:,.0f}원")
                res2.metric("유류 할증료", f"{fuel_val:,.0f}원")
                res3.metric("총 합계", f"{total_val:,.0f}원")
                
                st.divider()
                st.info(f"💡 원격지(ODA) 수수료 발생 여부를 확인하세요.")
            else:
                st.error(f"데이터를 찾을 수 없습니다.")

st.caption("© 2026 Dongmyeong Bearing AI Task Force Team")