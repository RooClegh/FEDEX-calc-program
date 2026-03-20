import streamlit as st
import pandas as pd
import os
import math
import requests
from bs4 import BeautifulSoup
import re

# 1. 설정 및 파일 경로
FILE_NAME = 'fedex_2026.csv'  # 파일명을 fedex_2026.csv로 변경했는지 확인해주세요!

# 2. 실시간 유류할증료 자동 추출 함수
def get_fedex_fuel_surcharge():
    url = "https://www.fedex.com/ko-kr/shipping/surcharges/fuel-surcharge.html"
    try:
        # FedEx 사이트에서 수입(ImportOne) 관련 유류할증료 섹션 추출
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            # '수입' 혹은 'Import' 키워드 근처의 % 숫자를 찾는 정규식
            # 보통 사이트에 24.50% 등으로 표기됨
            matches = re.findall(r'(\d+\.\d+)%', text)
            if matches:
                # 첫 번째 매칭되는 값을 반환 (보통 가장 최신/상단 값)
                return float(matches[0])
    except Exception as e:
        st.sidebar.warning(f"유류할증료 자동 로드 실패: {e}")
    return 25.0  # 실패 시 기본값

# 3. 미국 ZIP CODE 판별 함수 (서부 E / 기타 F)
def get_us_zone(zip_code):
    try:
        prefix = int(str(zip_code)[:3])
        # FedEx PDF 기준 미국 서부(Western) 우편번호 범위
        western_prefixes = list(range(800, 817)) + list(range(832, 839)) + \
                           list(range(840, 848)) + list(range(850, 866)) + \
                           list(range(889, 899)) + list(range(900, 962)) + \
                           list(range(970, 995))
        return "존 E" if prefix in western_prefixes else "존 F"
    except:
        return "존 F"

# 4. 데이터 로드 및 전처리 함수
@st.cache_data
def load_data():
    if not os.path.exists(FILE_NAME):
        return None
    
    # 상단 3행 제목 제외, 4행(index 3)을 헤더로 읽기
    df = pd.read_csv(FILE_NAME, skiprows=3)
    df.columns = df.columns.str.replace('\n', ' ').str.strip()
    
    # 요금 데이터 숫자 변환 (존 A ~ 존 J)
    zone_cols = [f'존 {c}' for c in 'ABCDEFGHIJ']
    for col in zone_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    df['중량(kg)'] = df['중량(kg)'].astype(str).str.strip()
    return df

# --- 화면 구성 ---
st.set_page_config(page_title="동명베아링 FedEx 운임계산기", layout="centered")

# 사이드바 정보
with st.sidebar:
    st.header("🏠 도착지 정보")
    st.info("부산광역시 사상구 새벽로215번길 123\n\n**동명베아링**")
    st.divider()
    st.caption("개발: AI TFT 서주영 대리")

st.title("✈️ FedEx 수입 운임 예측 시스템")
st.markdown("---")

df = load_data()

if df is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다. 파일명을 확인해 주세요.")
else:
    # 실시간 유류할증료 가져오기
    current_fuel_rate = get_fedex_fuel_surcharge()

    # 입력 구역
    with st.form("calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            country = st.selectbox("🌐 출발 국가", ["미국", "일본", "독일", "중국(남부)"])
            zip_code = st.text_input("📍 출발지 ZIP CODE (필수)", placeholder="예: 90210")
        with col2:
            weight = st.number_input("📦 예상 중량 (kg)", min_value=0.5, step=0.5, value=1.0)
            fuel_rate = st.number_input(f"⛽ 유류할증료 (%)", value=current_fuel_rate, step=0.1, help="FedEx 홈페이지에서 실시간으로 불러온 값입니다.")
        
        submitted = st.form_submit_button("💰 운임 계산하기")

    if submitted:
        if not zip_code:
            st.warning("⚠️ 정확한 구역 판별을 위해 우편번호를 입력해 주세요.")
        else:
            # 1. Zone 판별
            if country == "미국":
                target_zone = get_us_zone(zip_code)
            elif country == "일본":
                target_zone = "존 B"
            elif country == "독일":
                target_zone = "존 G"
            else:
                target_zone = "존 A"

            # 2. 중량 올림 처리 (0.5 단위)
            calc_weight = math.ceil(weight * 2) / 2
            weight_str = str(calc_weight) if calc_weight % 1 != 0 else str(int(calc_weight))
            
            # 3. 요금 조회
            # 서비스는 기본적으로 IP 특송화물을 기준으로 조회
            res = df[df['중량(kg)'].str.contains(f"^{weight_str}$", na=False, regex=True)]
            
            if not res.empty:
                base_price = res.iloc[0][target_zone]
                fuel_fee = int(base_price * (fuel_rate / 100))
                total_price = base_price + fuel_fee
                
                st.balloons()
                st.success(f"### {country} ({target_zone}) 수입 운임 결과")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("기본 운임", f"{base_price:,.0f}원")
                c2.metric("유류 할증료", f"{fuel_fee:,.0f}원")
                c3.metric("최종 예상 합계", f"{total_price:,.0f}원")
                
                # 추가 안내
                st.divider()
                st.warning("**⚠️ 추가 수수료 주의사항**\n\n"
                           "* **원격지 수수료:** 건당 최소 **35,600원** (도서산간/외곽지역 발생 시)\n"
                           "* 본 결과는 2026년 요금표 기반 추정치이며 실제 청구액과 다를 수 있습니다.")
            else:
                st.error(f"중량 {calc_weight}kg에 대한 데이터를 찾을 수 없습니다. 요금표의 범위를 확인하세요.")

st.caption("© 2026 동명베아링 AI Task Force Team")