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

# [국가별 대표 존 매핑]
COUNTRY_ZONE_MAP = {
    "중국(남부)": "존 A", "홍콩": "존 A", "대만": "존 A",
    "일본": "존 B",
    "중국(기타)": "존 C", "태국": "존 C", "말레이시아": "존 C",
    "인도": "존 D", "캄보디아": "존 D", "몽골": "존 D",
    "미국": "존 F", "캐나다": "존 F", "호주": "존 F",
    "독일": "존 G", "영국": "존 G", "프랑스": "존 G",
    "러시아": "존 H", "우크라이나": "존 H", "루마니아": "존 H",
    "브라질": "존 I", "콜롬비아": "존 I", "아르헨티나": "존 I",
    "UAE": "존 J", "방글라데시": "존 J", "쿠웨이트": "존 J"
}

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

# 4. 요금표 데이터 로드 함수
@st.cache_data
def load_data():
    if not os.path.exists(FILE_NAME): return None
    # 원본 파일 로드
    raw_df = pd.read_csv(FILE_NAME, skiprows=3)
    # 컬럼 정리
    raw_df.columns = raw_df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    # 데이터 정리 (복사본 생성하여 안전하게 처리)
    clean_df = raw_df.copy()
    zone_cols = [c for c in clean_df.columns if '존' in c]
    for col in zone_cols:
        clean_df[col] = clean_df[col].astype(str).str.replace(',', '').str.strip()
        clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0).astype(int)
    
    if '중량(kg)' in clean_df.columns:
        clean_df['중량(kg)'] = clean_df['중량(kg)'].astype(str).str.replace(r'\s+', '', regex=True).str.strip()
    
    return clean_df

# --- UI 레이아웃 ---
st.set_page_config(page_title="항공 운임 예측 계산기", layout="centered", initial_sidebar_state="collapsed")

st.title("✈️ 항공 운임 예측 계산기")
st.caption("본 계산기는 FEDEX 운임표를 기반으로 작성되었으며, 실제 운임과 다를 수 있습니다.")
st.caption("🏢 도착지: 부산광역시 사상구 새벽로215번길 123 동명베아링")

# 데이터 로드 (캐싱 사용)
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
            country_list = sorted(list(COUNTRY_ZONE_MAP.keys()))
            try: c_idx = country_list.index(addr_info["country"])
            except: c_idx = 0
            country = st.selectbox("🌐 출발 국가", country_list, index=c_idx)
            zip_input = st.text_input("📍 출발지 ZIP CODE (공란일 경우 국가 기준 계산)", value=addr_info["zip"])
        with col2:
            weight_input = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            fuel_rate = st.number_input("⛽ 적용 유류할증료 (%)", value=current_fuel, step=0.01, 
                                        help="본 요율은 FEDEX 사이트의 유류할증료 내역을 불러와 적용되었습니다.")
        
        calc_btn = st.form_submit_button("운임 계산 실행")

    # 계산 로직 (원본 데이터 df를 직접 수정하지 않음)
    if calc_btn:
        if zip_input and country == "미국":
            target_zone = get_us_zone(zip_input)
            zone_info_msg = f"미국 ZIP CODE({zip_input}) 기반"
        else:
            target_zone = COUNTRY_ZONE_MAP[country]
            zone_info_msg = f"{country} 국가 기본"

        up_weight = math.ceil(weight_input * 2) / 2
        
        match_row = None
        is_range_price = False
        
        # 행을 순회하며 매칭되는 구간 찾기
        for i in range(len(df)):
            weight_val = str(df.loc[i, '중량(kg)'])
            
            # 1. 단일 중량 일치 확인
            if weight_val == str(int(up_weight)) or weight_val == str(up_weight):
                match_row = df.iloc[i]
                break
            
            # 2. 범위 중량 확인
            if '-' in weight_val:
                try:
                    start, end = map(float, weight_val.split('-'))
                    if start <= up_weight <= end:
                        match_row = df.iloc[i]
                        is_range_price = True
                        break
                except: continue

        if match_row is not None:
            # 원본 값을 가져와서 새 변수에 할당 (df[target_zone]을 직접 수정하지 않음!)
            raw_unit_price = int(match_row[target_zone])
            
            # 고중량 구간(21kg 이상 또는 범위 구간) 단가 계산
            if is_range_price or up_weight > 20:
                base_val = int(raw_unit_price * up_weight)
                calc_method_msg = f"중량 구간 단가(kg당 {raw_unit_price:,.0f}원) 적용"
            else:
                base_val = raw_unit_price
                calc_method_msg = "중량별 고정 운임 적용"
            
            fuel_val = int(base_val * (fuel_rate / 100))
            total_val = base_val + fuel_val
            
            st.balloons()
            st.success(f"### 결과: {selected_addr if selected_addr != '직접 입력' else country}")
            
            res1, res2 = st.columns(2)
            res1.write(f"기본 운임: **{base_val:,.0f}원**")
            res2.write(f"유류 할증료: **{fuel_val:,.0f}원**")
            
            st.markdown(f"## 총 합계: **{total_val:,.0f}원**")
            
            st.divider()
            st.caption(f"운임 기준: {zone_info_msg} / {calc_method_msg}")
            st.caption(f"유류할증료는 주마다 업데이트 되니, 오류 방지를 위해 사이트에서 재확인 해주세요. [FEDEX 공식 사이트](https://www.fedex.com/ko-kr/shipping/surcharges.html)")
        else:
            st.error(f"데이터를 찾을 수 없습니다.")

st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team")
st.caption("제작: AI TFT 서주영 대리")