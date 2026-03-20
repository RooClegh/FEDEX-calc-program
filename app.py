import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 1. 파일 경로 및 설정
FILE_NAME = 'fedex_2026.csv' 

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

FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
}

# 2. [복구 완료] 실시간 유류할증료 추출 함수
def get_fedex_fuel_surcharge():
    url = "https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return 41.75 # 연결 실패 시 기본값
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # 페이지 내에서 '%' 기호가 붙은 숫자 패턴 탐색
        all_rates = re.findall(r'(\d+\.\d+)%', soup.get_text())
        if all_rates:
            return float(all_rates[0]) # 가장 첫 번째(최신) 요율 반환
    except Exception as e:
        print(f"유류할증료 로딩 오류: {e}")
    return 41.75 # 오류 발생 시 기본값

def get_us_zone(zip_code):
    try:
        prefix = int(str(zip_code)[:3])
        western = list(range(800, 817)) + list(range(832, 839)) + list(range(840, 848)) + \
                  list(range(850, 866)) + list(range(889, 899)) + list(range(900, 962)) + \
                  list(range(970, 995))
        return "존 E" if prefix in western else "존 F"
    except: return "존 F"

# 3. 데이터 로드 (캐싱 적용)
@st.cache_data
def load_and_clean_data():
    if not os.path.exists(FILE_NAME): return None
    df = pd.read_csv(FILE_NAME, skiprows=3)
    df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    zone_cols = [c for c in df.columns if '존' in c]
    for col in zone_cols:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)
    
    if '중량(kg)' in df.columns:
        df['중량(kg)'] = df['중량(kg)'].astype(str).str.replace(r'\s+', '', regex=True).str.strip()
    return df

# --- UI 레이아웃 ---
st.set_page_config(page_title="항공 운임 예측 계산기", layout="centered", initial_sidebar_state="collapsed")

st.title("✈️ 항공 운임 예측 계산기")
st.caption("본 계산기는 FEDEX 운임표를 기반으로 작성되었으며, 실제 운임과 다를 수 있습니다.")
st.caption("🏢 도착지: 부산광역시 사상구 새벽로215번길 123 동명베아링")

df_origin = load_and_clean_data()

if df_origin is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    # 폼 외부에서 유류할증료 한 번만 가져오기
    if 'fuel_rate_val' not in st.session_state:
        st.session_state.fuel_rate_val = get_fedex_fuel_surcharge()

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    with st.form("main_form"):
        col1, col2 = st.columns(2)
        with col1:
            country_list = sorted(list(COUNTRY_ZONE_MAP.keys()))
            try: c_idx = country_list.index(addr_info["country"])
            except: c_idx = 0
            country = st.selectbox("🌐 출발 국가", country_list, index=c_idx)
            zip_input = st.text_input("📍 출발지 ZIP CODE (공란일 경우 국가 기준)", value=addr_info["zip"])
        with col2:
            weight_input = st.number_input("📦 화물 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            # 가져온 실시간 요율을 기본값으로 설정
            fuel_rate = st.number_input("⛽ 적용 유류할증료 (%)", value=st.session_state.fuel_rate_val, step=0.01,
                                        help="FEDEX 사이트에서 실시간으로 불러온 최신 요율입니다.")
        
        calc_btn = st.form_submit_button("운임 계산 실행")

    if calc_btn:
        working_df = df_origin.copy()
        
        # 존 판별
        target_zone = COUNTRY_ZONE_MAP[country]
        if zip_input and country == "미국":
            target_zone = get_us_zone(zip_input)
            zone_msg = f"미국 ZIP({zip_input}) 기반"
        else:
            zone_msg = f"{country} 국가 기본"

        up_weight = math.ceil(weight_input * 2) / 2
        match_row = None
        is_range = False
        
        # 매칭 로직
        for i in range(len(working_df)):
            w_text = str(working_df.loc[i, '중량(kg)'])
            if w_text == str(int(up_weight)) or w_text == str(up_weight):
                match_row = working_df.iloc[i]
                is_range = False
                break
            if '-' in w_text:
                try:
                    s, e = map(float, w_text.split('-'))
                    if s <= up_weight <= e:
                        match_row = working_df.iloc[i]
                        is_range = True
                        break
                except: continue

        if match_row is not None:
            unit_price = float(match_row[target_zone])
            
            # [수정된 로직 적용]
            if is_range:
                base_val = unit_price * up_weight
                method_msg = f"kg당 단가({unit_price:,.0f}원) 적용"
            else:
                base_val = unit_price
                method_msg = "고정 운임 적용"
            
            # 유류할증료 계산 (기본 운임의 % 만큼 추가)
            fuel_val = base_val * (fuel_rate / 100)
            total_val = base_val + fuel_val
            
            st.balloons()
            st.success(f"### 결과: {selected_addr if selected_addr != '직접 입력' else country}")
            
            r1, r2 = st.columns(2)
            r1.write(f"기본 운임: **{int(base_val):,.0f}원**")
            r2.write(f"유류 할증료 ({fuel_rate}%): **{int(fuel_val):,.0f}원**")
            st.markdown(f"## 총 합계: **{int(total_val):,.0f}원**")
            
            st.divider()
            st.caption(f"운임 기준: {zone_msg} / {method_msg}")
            st.caption(f"유류할증료는 주마다 업데이트 되니 확인 바랍니다. [FEDEX 공식 사이트](https://www.fedex.com/ko-kr/shipping/surcharges.html)")
        else:
            st.error("데이터를 찾을 수 없습니다.")

st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")