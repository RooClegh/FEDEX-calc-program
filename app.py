import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 1. 고정 설정 및 데이터 매핑
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

# 2. 기능 함수 (유류할증료 추출 및 존 판별)
def get_fedex_fuel_surcharge():
    url = "https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        all_rates = re.findall(r'(\d+\.\d+)%', soup.get_text())
        if all_rates: return float(all_rates[0])
    except: pass
    return 41.75 # 실패 시 기본값

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
    df = pd.read_csv(FILE_NAME, skiprows=3).copy()
    df.columns = df.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    zone_cols = [c for c in df.columns if '존' in c]
    for col in zone_cols:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if '중량(kg)' in df.columns:
        df['중량(kg)'] = df['중량(kg)'].astype(str).str.replace(r'\s+', '', regex=True).str.strip()
    return df

# --- UI 레이아웃 시작 ---
st.set_page_config(page_title="항공 운임 예측 계산기", layout="centered")

st.title("✈️ 항공 운임 예측 계산기")
st.caption("🏢 도착지: 부산광역시 사상구 새벽로215번길 123 동명베아링")

df_master = load_data()

if df_master is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
else:
    # 세션에 유류할증료 초기화
    if 'current_fuel_rate' not in st.session_state:
        st.session_state.current_fuel_rate = get_fedex_fuel_surcharge()

    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]

    # 입력 폼 구간
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
            # 2번 요구사항: 물음표 마크(?)와 도움말 텍스트 삽입
            fuel_in = st.number_input(
                "⛽ 적용 유류할증료 (%)", 
                value=st.session_state.current_fuel_rate, 
                step=0.01,
                help="수출입 항공 화물에 적용되는 할증료입니다. FedEx 사이트에서 매주 업데이트되는 요율을 실시간으로 가져옵니다."
            )
        
        btn = st.form_submit_button("운임 계산 실행")

    # 계산 결과 출력 구간
    if btn:
        target_zone = COUNTRY_ZONE_MAP[country_in]
        if zip_in and country_in == "미_국": # 미국 판별
            target_zone = get_us_zone(zip_in)
        
        up_w = math.ceil(weight_in * 2) / 2
        
        found_base_price = 0.0
        calc_method = ""
        is_success = False

        # 우선순위 매칭 로직
        fixed_match = df_master[df_master['중량(kg)'].isin([str(int(up_w)), str(up_w)])]
        
        if not fixed_match.empty:
            found_base_price = float(fixed_match.iloc[0][target_zone])
            calc_method = "중량별 고정 운임 적용"
            is_success = True
        else:
            for i in range(len(df_master)):
                w_str = str(df_master.loc[i, '중량(kg)'])
                if '-' in w_str:
                    try:
                        start, end = map(float, w_str.split('-'))
                        if start <= up_w <= end:
                            unit_p = float(df_master.loc[i, target_zone])
                            found_base_price = unit_p * up_w
                            calc_method = f"중량 구간 단가(kg당 {unit_p:,.0f}원) 적용"
                            is_success = True
                            break
                    except: continue

        if is_success:
            fuel_amt = found_base_price * (fuel_in / 100)
            total_amt = found_base_price + fuel_amt
            
            st.balloons()
            st.success(f"### 결과: {selected_addr if selected_addr != '직접 입력' else country_in}")
            
            c1, c2 = st.columns(2)
            c1.write(f"기본 운임: **{int(found_base_price):,.0f}원**")
            c2.write(f"유류 할증료 ({fuel_in}%): **{int(fuel_amt):,.0f}원**")
            st.markdown(f"## 총 합계: **{int(total_amt):,.0f}원**")
            
            # 1번 요구사항: 하단 상세 안내 및 사이트 링크 복구
            st.divider()
            st.info(f"💡 산출 기준: {target_zone} / {calc_method}")
            st.caption("⚠️ 본 계산기는 운임표 기반 예측치이며, 실제 청구 금액은 화물의 크기(부피 중량), 통관 수수료 등에 따라 달라질 수 있습니다.")
            st.caption(f"📅 유류할증료 정보는 주 단위로 변동되므로 정확한 확인이 필요합니다. [FedEx 공식 유류할증료 확인하기](https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html)")
        else:
            st.error("요금표에서 입력하신 중량(kg)에 해당하는 데이터를 찾을 수 없습니다.")

# 푸터 (Footer)
st.markdown("---")
st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")