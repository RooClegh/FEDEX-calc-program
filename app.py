import streamlit as st
import pandas as pd
import os
import math
import re

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

def detect_country_by_zip(zip_code):
    zip_clean = re.sub(r'[^0-9]', '', str(zip_code))
    if len(zip_clean) == 7: return "일본"
    elif len(zip_clean) == 5: return "미국"
    return None

@st.cache_data
def load_and_split_data():
    if not os.path.exists(FILE_NAME): return None, None
    raw_df = pd.read_csv(FILE_NAME, skiprows=3, header=None).copy()
    cols = ["중량(Kg)", "구분", "지역 A", "지역 B", "지역 C", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]
    df_ip = raw_df.iloc[1:36, 0:len(cols)].copy() 
    df_ie = raw_df.iloc[37:68, 0:len(cols)].copy() 
    def clean(df):
        df.columns = cols 
        for c in cols[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['중량_num'] = pd.to_numeric(df['중량(Kg)'], errors='coerce')
        return df
    return clean(df_ip), clean(df_ie)

# --- UI 레이아웃 ---
st.set_page_config(page_title="FEDEX 항공 운임 예측 계산기", layout="wide")
st.title("✈️ FEDEX 항공 운임 예측 계산기")
st.caption("정보를 입력하신 후 하단의 [운임 계산하기] 버튼을 눌러주세요.")

df_ip, df_ie = load_and_split_data()

if df_ip is None:
    st.error(f"'{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]
    
    with st.form("calc_form"):
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            zip_code = st.text_input("우편번호 (ZIP CODE)", value=addr_info["zip"])
        with row1_col2:
            auto_country = detect_country_by_zip(zip_code)
            country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
            default_c_idx = country_list.index(auto_country) if auto_country in country_list else (country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0)
            country = st.selectbox("출발 국가", country_list, index=default_c_idx)

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            weight = st.number_input("화물 중량 (kg)", min_value=0.5, step=0.5, value=10.0)
        with row2_col2:
            fuel_rate = st.number_input("유류할증료 (%)", value=41.75)

        submitted = st.form_submit_button("운임 계산하기")

    if submitted:
        region = COUNTRY_REGION_MAP[country]
        up_weight = math.ceil(weight * 2) / 2 
        ip_match = df_ip[df_ip['중량_num'] == float(up_weight)]
        ie_match = df_ie[df_ie['중량_num'] == float(up_weight)]

        st.divider()
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.markdown("### 🚀 International Priority (IP)")
            if not ip_match.empty:
                base_ip = float(ip_match[region].iloc[0])
                total_ip = base_ip * (1 + fuel_rate/100)
                st.metric("IP 최종 합계", f"{int(total_ip):,.0f} 원")
                st.write(f"• 기본 운임: {int(base_ip):,.0f}원")
            else: st.warning(f"⚠️ {region} IP 데이터 없음")

        with res_col2:
            st.markdown("### 🐢 International Economy (IE)")
            if not ie_match.empty:
                base_ie = float(ie_match[region].iloc[0])
                if base_ie > 0:
                    total_ie = base_ie * (1 + fuel_rate/100)
                    diff = (total_ip - total_ie) if not ip_match.empty else 0
                    st.metric("IE 최종 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                    st.write(f"• 기본 운임: {int(base_ie):,.0f}원")
                else: st.info("ℹ️ 해당 구간 IE 미지원")
            else: st.warning(f"⚠️ {region} IE 데이터 없음")

    # --- 하단 강조 섹션 수정 ---
    st.divider()
    
    # 2. 운임 주의사항: 연한 주황색 (FedEx Orange 느낌)
    st.write(f":orange[**⚠️ 운임 주의사항**]")
    st.write(":orange[본 계산기는 운임표 기반 예측치이며 실제 청구 금액은 화물의 크기(부피 중량), 통관 수수료 등에 따라 달라질 수 있습니다.]")
    
    st.write("") # 간격

    # 1. 유류할증료 상세 확인: 보라색 작은 글씨
    st.write("📅 유류할증료 안내")
    st.write("유류할증료 정보는 주 단위로 변동되므로 정확한 확인이 필요합니다.")
    st.write(f":violet[**🔗 [FedEx 유류할증료 상세 확인 (클릭)](https://www.fedex.com/ko-kr/shipping/surcharges.html)**]")

    st.markdown("---")
    st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")