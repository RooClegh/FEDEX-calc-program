import streamlit as st
import pandas as pd
import os
import math

# 1. 파일 및 설정
FILE_NAME = 'FEDEX_2026.csv'
COUNTRY_REGION_MAP = {
    "중국(남부)": "지역 A", "중국(기타)": "지역 C", "홍콩": "지역 A", "대만": "지역 A",
    "일본": "지역 B", "태국": "지역 C", "말레이시아": "지역 C", "베트남": "지역 C",
    "인도": "지역 D", "미국": "지역 F", "캐나다": "지역 F", "독일": "지역 G",
    "프랑스": "지역 G", "영국": "지역 G", "이탈리아": "지역 G", "호주": "지역 F"
}

FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
}

@st.cache_data
def load_all_data():
    if not os.path.exists(FILE_NAME): return None, None
    # 헤더 없이 원본 그대로 읽기
    raw = pd.read_csv(FILE_NAME, header=None).copy()
    
    # 컬럼명 강제 지정
    cols = ["중량(Kg)", "구분", "지역 A", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]

    # 💡 [핵심 수정] 행 번호를 더 안전하게 추출 (엑셀 줄번호 기준)
    # IP: 5행~38행 (Pandas index 4~37)
    df_ip = raw.iloc[4:38, 0:13].copy()
    df_ip.columns = cols
    
    # IE: 40행~67행 (Pandas index 39~66)
    df_ie = raw.iloc[39:67, 0:13].copy()
    df_ie.columns = cols

    def clean_data(df):
        for c in cols[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['중량(Kg)'] = df['중량(Kg)'].astype(str).str.replace(' ', '').str.strip()
        return df

    return clean_data(df_ip), clean_data(df_ie)

# --- UI 레이아웃 ---
st.set_page_config(page_title="FedEx 운임 비교기", layout="wide")
st.title("✈️ FedEx IP vs IE 운임 정밀 비교")

df_ip, df_ie = load_all_data()

if df_ip is None:
    st.error("파일을 찾을 수 없습니다.")
else:
    with st.sidebar:
        st.header("📋 입력 설정")
        selected_addr = st.selectbox("📌 자주 쓰는 주소", list(FAVORITE_ADDRESSES.keys()))
        addr = FAVORITE_ADDRESSES[selected_addr]
        
        country = st.selectbox("출발 국가", sorted(list(COUNTRY_REGION_MAP.keys())), 
                               index=sorted(list(COUNTRY_REGION_MAP.keys())).index(addr["country"]))
        weight = st.number_input("중량 (kg)", min_value=0.5, step=0.5, value=5.0)
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75)

    # 계산 로직
    region = COUNTRY_REGION_MAP[country]
    up_w = str(float(math.ceil(weight * 2) / 2)).replace('.0', '') if weight % 1 == 0 else str(float(math.ceil(weight * 2) / 2))

    # 데이터 매칭
    ip_row = df_ip[df_ip['중량(Kg)'].isin([up_w, f"{up_w}.0"])]
    ie_row = df_ie[df_ie['중량(Kg)'].isin([up_w, f"{up_w}.0"])]

    # --- 화면 표시 (여기서 컬럼이 나뉩니다) ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚀 International Priority (IP)")
        if not ip_row.empty:
            base = float(ip_row[region].iloc[0])
            total = base * (1 + fuel_rate/100)
            st.metric("IP 최종 합계", f"{int(total):,.0f}원")
            st.write(f"기본가: {int(base):,.0f}원")
        else:
            st.warning("IP 데이터를 찾을 수 없습니다.")

    with col2:
        st.subheader("🐢 International Economy (IE)")
        if not ie_row.empty:
            base_ie = float(ie_row[region].iloc[0])
            # 💡 만약 base_ie가 0이라면 요금이 없는 것
            if base_ie > 0:
                total_ie = base_ie * (1 + fuel_rate/100)
                st.metric("IE 최종 합계", f"{int(total_ie):,.0f}원")
                st.write(f"기본가: {int(base_ie):,.0f}원")
            else:
                st.info("해당 중량은 IE 요금이 0원(미지원)입니다.")
        else:
            st.warning("IE 데이터를 찾을 수 없습니다. (엑셀 행 위치 확인 필요)")

    # 하단 정보 및 푸터
    st.divider()
    st.caption("⚠️ 본 계산기는 운임표 기반 예측치이며, 실제 금액과 다를 수 있습니다.")
    st.caption(f"© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")