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

# [자주 쓰는 주소 설정]
FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
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

# 4. 요금표 데이터 로드 함수 (일본 데이터 매칭 강화)
@st.cache_data
def load_data():
    if not os.path.exists(FILE_NAME): return None
    df = pd.read_csv(FILE_NAME, skiprows=3)
    
    # 컬럼명 및 데이터 내 숨겨진 줄바꿈/공백 완전 제거
    df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    zone_cols = [c for c in df.columns if '존' in c]
    for col in zone_cols:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    # 중량 데이터 정제 (일본 등 특정 행의 데이터 매칭 오류 방지)
    if '중량(kg)' in df.columns:
        df['중량(kg)'] = df['중량(kg)'].astype(str).str.replace(r'\s+', '', regex=True).str.strip()
    return df

# --- UI 레이아웃 ---
st.set_page_config(page_title="항공 운임 예측 계산기", layout="centered")

# 사이드바 (도착지 정보)
with st.sidebar:
    st.header("🏠 물품 도착지")
    st.info("부산광역시 사상구 새벽로215번길 123\n\n**동명베아링**")
    st.divider()
    st.caption("Assistant Manager: 서주영 (AI TFT)")

# 1, 2번 요청: 제목 및 부제목 설정
st.title("✈️ 항공 운임 예측 계산기")
st.caption("본 계산기는 FEDEX 운임표를 기반으로 작성되었으며, 실제 운임과 다를 수 있습니다.")

df = load_data()

if df is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    current_fuel = get_fedex_fuel_surcharge()

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("main_form"):
        col1, col2 = st.columns(2)
        with col1:
            country_list = ["미국", "일본", "독일", "중국(남부)"]
            try: c_idx = country_list.index(addr_info["country"])
            except: c_idx = 0
            country = st.selectbox("🌐 출발 국가", country_list, index=c_idx)
            zip_input = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with col2:
            weight_input = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            # 3번 요청: 물음표 마크 도움말 추가
            fuel_rate = st.number_input("⛽ 적용 유류할증료 (%)", value=current_fuel, step=0.01, 
                                        help="본 요율은 FEDEX 사이트의 유류할증료 내역을 불러와 적용되었습니다.")
        
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
            w_str = str(int(up_weight)) if up_weight % 1 == 0 else str(up_weight)
            
            # 정확한 중량 매칭
            match_row = df[df['중량(kg)'].str.fullmatch(w_str, na=False)]
            
            if not match_row.empty:
                base_val = match_row.iloc[0][target_zone]
                fuel_val = int(base_val * (fuel_rate / 100))
                total_val = base_val + fuel_val
                
                st.balloons()
                # 6번 요청: 결과에서 존 표기 삭제
                st.success(f"### 결과: {selected_addr if selected_addr != '직접 입력' else country}")
                
                # 4번 요청: 금액별 폰트 크기 및 굵기 차별화
                res1, res2 = st.columns(2)
                res1.write(f"기본 운임: **{base_val:,.0f}원**")
                res2.write(f"유류 할증료: **{fuel_val:,.0f}원**")
                
                st.markdown(f"## 총 합계: **{total_val:,.0f}원**")
                
                # 5번 요청: 하단 문구 변경 및 링크 추가
                st.divider()
                st.caption(f"유류할증료는 주마다 업데이트 되니, 오류 방지를 위해 사이트에서 재확인 해주세요. [FEDEX 공식 사이트](https://www.fedex.com/ko-kr/shipping/surcharges.html)")
            else:
                st.error(f"데이터를 찾을 수 없습니다. (입력 중량: {up_weight}kg)")

st.caption("© 2026 Dongmyeong Bearing AI Task Force Team")