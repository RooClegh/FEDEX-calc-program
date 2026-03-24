import streamlit as st
import pandas as pd
import os
import math

# 1. 설정 및 매핑
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
def load_and_split_data():
    if not os.path.exists(FILE_NAME): return None, None
    raw_df = pd.read_csv(FILE_NAME, skiprows=3, header=None).copy()
    
    cols = ["중량(Kg)", "구분", "지역 A", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]
    
    # 행 인덱스를 더 넉넉하게 잡아서 누락 방지
    df_ip = raw_df.iloc[1:36, 0:13].copy() 
    df_ie = raw_df.iloc[37:68, 0:13].copy() 
    
    def clean(df):
        df.columns = cols
        # 지역 금액 컬럼 숫자화
        for c in cols[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        # 중량 컬럼을 '숫자형'으로 변환 (매칭 정확도 향상)
        df['중량_num'] = pd.to_numeric(df['중량(Kg)'], errors='coerce')
        return df

    return clean(df_ip), clean(df_ie)

# --- UI 레이아웃 ---
st.set_page_config(page_title="동명베아링 항공운임 계산기", layout="wide")
st.title("✈️ FedEx IP vs IE 운임 비교")

df_ip, df_ie = load_and_split_data()

if df_ip is None:
    st.error("파일을 찾을 수 없습니다.")
else:
    with st.sidebar:
        st.header("📋 입력 정보")
        selected_addr = st.selectbox("📌 자주 쓰는 주소", list(FAVORITE_ADDRESSES.keys()))
        addr_info = FAVORITE_ADDRESSES[selected_addr]
        
        country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
        c_idx = country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0
        country = st.selectbox("출발 국가", country_list, index=c_idx)
        weight = st.number_input("중량 (kg)", min_value=0.5, step=0.5, value=10.0) # 기본값 10kg 설정
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75)

    # 계산 로직
    region = COUNTRY_REGION_MAP[country]
    up_weight = math.ceil(weight * 2) / 2 
    
    # 숫자형(float)으로 정확하게 행 찾기
    ip_match = df_ip[df_ip['중량_num'] == float(up_weight)]
    ie_match = df_ie[df_ie['중량_num'] == float(up_weight)]

    # 결과 출력
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚀 빠른 배송 (IP)")
        if not ip_match.empty:
            base_ip = float(ip_match[region].iloc[0])
            total_ip = base_ip * (1 + fuel_rate/100)
            st.metric("IP 최종 합계", f"{int(total_ip):,.0f} 원")
            st.write(f"• 기본 운임: {int(base_ip):,.0f}원")
        else:
            st.warning("⚠️ IP 데이터를 찾을 수 없습니다.")

    with col2:
        st.subheader("🐢 경제형 배송 (IE)")
        if not ie_match.empty:
            base_ie = float(ie_match[region].iloc[0])
            if base_ie > 0:
                total_ie = base_ie * (1 + fuel_rate/100)
                # IP 대비 절감액 계산
                diff = total_ip - total_ie if not ip_match.empty else 0
                st.metric("IE 최종 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                st.write(f"• 기본 운임: {int(base_ie):,.0f}원")
            else:
                st.info("ℹ️ 해당 구간 IE 미지원")
        else:
            st.warning("⚠️ IE 데이터를 찾을 수 없습니다.")

    # 하단 공지 및 푸터
    st.divider()
    st.warning("⚠️ **운임 주의사항**\n\n본 계산기는 운임표 기반 예측치이며, 실제 청구 금액은 부피 중량 등에 따라 달라질 수 있습니다.")
    st.caption("📅 유류할증료는 주 단위로 변동되므로 [FedEx 공식 사이트]에서 확인 바랍니다.")
    st.markdown("---")
    st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")