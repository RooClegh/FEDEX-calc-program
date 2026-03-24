import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 파일 및 설정
FILE_NAME = 'FEDEX_2026.csv'

# 국가별 지역 매핑 (일본: 지역 B, 미국: 지역 F 등)
COUNTRY_REGION_MAP = {
    "중국(남부)": "지역 A", "중국(기타)": "지역 C", "홍콩": "지역 A", "대만": "지역 A",
    "일본": "지역 B", "태국": "지역 C", "말레이시아": "지역 C", "베트남": "지역 C",
    "인도": "지역 D", "미국": "지역 F", "캐나다": "지역 F", "독일": "지역 G",
    "프랑스": "지역 G", "영국": "지역 G", "이탈리아": "지역 G", "호주": "지역 F"
}

# 자주 쓰는 주소 데이터
FAVORITE_ADDRESSES = {
    "직접 입력": {"country": "미국", "zip": ""},
    "TIMKEN": {"country": "미국", "zip": "44720"},
    "IKO": {"country": "일본", "zip": "1088586"}
}

def detect_country_by_zip(zip_code):
    """우편번호 자릿수로 국가 자동 인식"""
    zip_clean = re.sub(r'[^0-9]', '', str(zip_code))
    if len(zip_clean) == 7: return "일본"
    elif len(zip_clean) == 5: return "미국"
    return None

@st.cache_data
def load_and_split_data():
    """데이터 로드 및 IP/IE 섹션 분리"""
    if not os.path.exists(FILE_NAME): return None, None
    
    # 엑셀 데이터 로드 (첫 3행 건너뜀)
    raw_df = pd.read_csv(FILE_NAME, skiprows=3, header=None).copy()
    
    # 컬럼명 강제 표준화 (KeyError 방지)
    cols = ["중량(Kg)", "구분", "지역 A", "지역 B", "지역 C", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]
    
    # IP 데이터(상단)와 IE 데이터(하단) 슬라이싱
    df_ip = raw_df.iloc[1:36, 0:len(cols)].copy() 
    df_ie = raw_df.iloc[37:68, 0:len(cols)].copy() 
    
    def clean(df):
        df.columns = cols 
        for c in cols[2:]:
            # 금액 데이터 정제 (쉼표 제거 및 숫자 변환)
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        # 중량 데이터 숫자화 (매칭 정확도 향상)
        df['중량_num'] = pd.to_numeric(df['중량(Kg)'], errors='coerce')
        return df

    return clean(df_ip), clean(df_ie)

# --- UI 레이아웃 시작 ---
st.set_page_config(page_title="FEDEX 항공 운임 예측 계산기", layout="wide")

# 1. 제목 및 작은 안내 문구
st.title("✈️ FEDEX 항공 운임 예측 계산기")
st.caption("정보를 입력하신 후 하단의 [운임 계산하기] 버튼을 눌러주세요.")

df_ip, df_ie = load_and_split_data()

if df_ip is None:
    st.error(f"'{FILE_NAME}' 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
else:
    # 2. 자주 쓰는 주소 선택 (한 줄 전체 차지)
    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]
    
    # 3. 입력 폼 (버튼 클릭 시에만 계산)
    with st.form("calc_form"):
        # 첫 번째 줄: 우편번호 기반 국가 자동 인식
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            zip_input = st.text_input("우편번호 (ZIP CODE)", value=addr_info["zip"])
        with row1_col2:
            auto_c = detect_country_by_zip(zip_input)
            country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
            # 자동 인식된 국가가 있으면 우선 적용, 없으면 즐겨찾기 기준
            idx = country_list.index(auto_c) if auto_c in country_list else (country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0)
            country = st.selectbox("출발 국가", country_list, index=idx)

        # 두 번째 줄: 중량 및 할증료
        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            weight = st.number_input("화물 중량 (kg)", min_value=0.5, step=0.5, value=10.0)
        with row2_col2:
            fuel_rate = st.number_input("현재 유류할증료 (%)", value=41.75)

        # 세 번째 줄: 우편번호 하단에 버튼 배치
        submitted = st.form_submit_button("운임 계산하기")

    # 4. 계산 및 결과 출력
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
                st.caption("⏱️ 예상 소요: 1~3 영업일")
            else:
                st.warning(f"⚠️ {region} IP 데이터 없음")

        with res_col2:
            st.markdown("### 🐢 International Economy (IE)")
            if not ie_match.empty:
                base_ie = float(ie_match[region].iloc[0])
                if base_ie > 0:
                    total_ie = base_ie * (1 + fuel_rate/100)
                    diff = (total_ip - total_ie) if not ip_match.empty else 0
                    st.metric("IE 최종 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                    st.write(f"• 기본 운임: {int(base_ie):,.0f}원")
                    st.caption("⏱️ 예상 소요: 4~6 영업일")
                else:
                    st.info("ℹ️ 해당 구간 IE 서비스 미지원")
            else:
                st.warning(f"⚠️ {region} IE 데이터 없음")

# --- 하단 강조 섹션 (시인성 개선 버전) ---
    st.divider()
    
    # 1. 운임 주의사항: 배경은 연하게, 글자는 진한 주황색으로 강제 고정
    st.markdown("""
        <div style="background-color: #FAFAFA; padding: 15px; border-radius: 10px; border: 2px solid #FF6600;">
            <p style="color: #E65100 !important; font-weight: bold; margin: 0; font-size: 1.1rem;">⚠️ 운임 주의사항</p>
            <p style="color: #333333 !important; font-size: 0.95rem; margin: 8px 0 0 0; line-height: 1.5;">
                본 계산기는 운임표 기반 예측치이며 실제 청구 금액은 <span style="color: #E65100; font-weight: bold;">화물의 크기(부피 중량), 통관 수수료</span> 등에 따라 달라질 수 있습니다.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("") 

    # 2. 유류할증료 안내: 보라색 강조
    st.markdown("""
        <div style="margin-top: 15px; padding-left: 5px;">
            <p style="margin-bottom: 5px; font-weight: bold; color: #444;">📅 유류할증료 안내</p>
            <p style="font-size: 0.9rem; color: #666; margin-bottom: 10px;">유류할증료 정보는 주 단위로 변동되므로 정확한 확인이 필요합니다.</p>
            <a href="https://www.fedex.com/ko-kr/shipping/surcharges.html" target="_blank" 
               style="color: #660099 !important; font-weight: bold; text-decoration: underline; font-size: 1rem; background-color: #F3E5F5; padding: 5px 10px; border-radius: 5px;">
               🔗 [FedEx 유류할증료 상세 확인 (클릭)]
            </a>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")