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

# 4. 요금표 데이터 로드 함수 (헤더 정리 강화)
@st.cache_data
def load_data():
    if not os.path.exists(FILE_NAME): return None
    # 4행부터 데이터 시작 (skiprows=3)
    df = pd.read_csv(FILE_NAME, skiprows=3)
    
    # 컬럼명 정리: 앞뒤 공백 제거 및 줄바꿈 제거
    df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    # 요금 데이터 숫자 변환 (존 A ~ 존 J)
    zone_cols = [c for c in df.columns if '존' in c]
    for col in zone_cols:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    # 중량 컬럼을 문자열로 변환하고 깨끗하게 정리
    if '중량(kg)' in df.columns:
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

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("main_form"):
        col1, col2 = st.columns(2)
        with col1:
            country_list = ["미국", "일본", "독일", "중국(남부)"]
            # 선택된 주소의 국가가 리스트에 없을 경우를 대비한 안전장치
            try:
                c_idx = country_list.index(addr_info["country"])
            except:
                c_idx = 0
            country = st.selectbox("🌐 출발 국가", country_list, index=c_idx)
            zip_input = st.text_input("📍 출발지 ZIP CODE", value=addr_info["zip"])
        with col2:
            weight_input = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            fuel_rate = st.number_input("⛽ 적용 유류할증료 (%)", value=current_fuel, step=0.01)
        
        calc_btn = st.form_submit_button("운임 계산 실행")

    if calc_btn:
        if not zip_input:
            st.warning("⚠️ 우편번호를 입력해 주세요.")
        else:
            # 1. Zone 결정
            if country == "미국": target_zone = get_us_zone(zip_input)
            elif country == "일본": target_zone = "존 B"
            elif country == "독일": target_zone = "존 G"
            else: target_zone = "존 A"

            # 2. 중량 올림 처리
            up_weight = math.ceil(weight_input * 2) / 2
            
            # 💡 [해결 포인트] 숫자 매칭을 더 유연하게 수정
            # 1.0 -> "1", 1.5 -> "1.5" 모두 대응하도록 함
            if up_weight % 1 == 0:
                w_str = str(int(up_weight))
            else:
                w_str = str(up_weight)
            
            # 중량 컬럼에서 해당 숫자가 포함된 행을 찾음 (정확히 일치하거나 해당 숫자로 시작하는 행)
            match_row = df[df['중량(kg)'].apply(lambda x: x == w_str or x.startswith(w_str + " "))]
            
            # 만약 못 찾았다면, 데이터프레임의 인덱스를 숫자로 변환해서 다시 시도 (보험용)
            if match_row.empty:
                try:
                    df_temp = df.copy()
                    df_temp['weight_num'] = pd.to_numeric(df_temp['중량(kg)'], errors='coerce')
                    match_row = df_temp[df_temp['weight_num'] == up_weight]
                except:
                    pass

            if not match_row.empty:
                # 3. 요금 추출 (존 B 등 해당 열의 값)
                try:
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
                except KeyError:
                    st.error(f"요금표에서 '{target_zone}' 열을 찾을 수 없습니다. 엑셀의 컬럼명을 확인해주세요.")
            else:
                st.error(f"요금표에서 중량 {up_weight}kg에 해당하는 데이터를 찾을 수 없습니다. (현재 입력값: {w_str})")
                with st.expander("데이터 확인 (디버깅용)"):
                    st.write("표시 중량 컬럼 예시:", df['중량(kg)'].unique()[:10])

st.caption("© 2026 Dongmyeong Bearing AI Task Force Team")