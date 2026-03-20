import streamlit as st
import pandas as pd
import os

# 1. 파일 경로 설정 (이름을 fedex_2026.csv로 바꾸셨다고 가정합니다)
FILE_NAME = 'fedex_2026.csv' 

def load_data():
    if not os.path.exists(FILE_NAME):
        return None
    
    # 상단 3행 제외, 헤더는 4행(인덱스 3)부터
    df = pd.read_csv(FILE_NAME, skiprows=3)
    
    # 컬럼명 정리 (앞뒤 공백 제거 및 줄바꿈 처리)
    df.columns = df.columns.str.replace('\n', ' ').str.strip()
    
    # 요금 데이터 숫자 변환 (존 A ~ 존 J)
    zone_cols = [f'존 {c}' for c in 'ABCDEFGHIJ']
    for col in zone_cols:
        if col in df.columns:
            # 콤마 제거 후 숫자로 변환
            df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    return df

# --- 화면 구성 시작 ---
st.set_page_config(page_title="FedEx 운임 예측기", layout="wide")
st.title("✈️ FedEx 수입 운임 예측 시스템")

df = load_data()

if df is None:
    st.error(f"❌ '{FILE_NAME}' 파일을 찾을 수 없습니다. 파일명을 확인해 주세요.")
else:
    st.success("✅ 요금표 데이터를 성공적으로 로드했습니다.")
    
    # 3단계: 사용자 입력 UI 초안
    st.divider()
    with st.expander("🔍 데이터 미리보기 (확인용)"):
        st.dataframe(df.head(10))

    col1, col2, col3 = st.columns(3)
    
    with col1:
        country = st.selectbox("출발 국가", ["미국", "일본", "독일", "중국(남부)"])
        zip_code = st.text_input("📍 ZIP CODE (필수)", placeholder="우편번호를 입력하세요")
        
    with col2:
        service_type = st.selectbox("서비스 선택", df['서비스'].unique() if '서비스' in df.columns else ["IP"])
        weight = st.number_input("📦 예상 중량 (kg)", min_value=0.5, step=0.5)

    with col3:
        fuel_rate = st.number_input("⛽ 유류할증료 (%)", value=25.0, step=0.1)
        
    if st.button("운임 계산하기"):
        if not zip_code:
            st.warning("⚠️ 우편번호를 먼저 입력해 주세요!")
        else:
            st.info("계산 로직은 다음 단계에서 연결될 예정입니다.")