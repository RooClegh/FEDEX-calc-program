import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 파일 설정
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
    if not os.path.exists(FILE_NAME):
        return None, None
    
    # 엑셀 전체 로드 (행 제한 없이)
    raw_df = pd.read_csv(FILE_NAME, header=None).copy()
    cols = ["중량(Kg)", "구분", "지역 A", "지역 B", "지역 C", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N"]
    
    # [수정] 키워드 기반 자동 구역 분리
    ip_start_idx = 0
    ie_start_idx = 0
    
    for i, row in raw_df.iterrows():
        row_str = str(row.values)
        if "International Priority" in row_str and ip_start_idx == 0:
            ip_start_idx = i + 1
        if "International Economy" in row_str:
            ie_start_idx = i + 1
            
    # IP 데이터: IP 시작부터 IE 시작 전까지
    df_ip = raw_df.iloc[ip_start_idx + 1:ie_start_idx - 2, 0:len(cols)].copy()
    # IE 데이터: IE 시작부터 끝까지
    df_ie = raw_df.iloc[ie_start_idx + 1:, 0:len(cols)].copy()
    
    def clean(df):
        if df.empty: return df
        df.columns = cols 
        for c in cols[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    return clean(df_ip), clean(df_ie)

def get_fedex_fare(df, weight, region):
    if df.empty: return None, None, weight
    
    target_w = math.ceil(weight * 2) / 2
    match = pd.DataFrame()
    
    # 고정 무게 매칭
    match = df[df['중량(Kg)'].astype(str).str.strip() == f"{target_w}"]
    
    # 범위형 무게 매칭
    if match.empty:
        for idx, row in df.iterrows():
            w_label = str(row['중량(Kg)'])
            nums = re.findall(r'\d+', w_label)
            if len(nums) >= 2:
                if float(nums[0]) <= target_w <= float(nums[1]):
                    match = pd.DataFrame([row])
                    break
            elif '이상' in w_label:
                num = re.findall(r'\d+', w_label)[0]
                if target_w >= float(num):
                    match = pd.DataFrame([row])
                    break

    if not match.empty:
        # 해당 지역(F 등)에 요금이 0인 경우도 체크
        base_unit_price = float(match[region].iloc[0])
        if base_unit_price == 0: return None, None, target_w
        
        gubun = str(match['구분'].iloc[0])
        w_text = str(match['중량(Kg)'].iloc[0])
        
        if 'kg당' in gubun or '~' in w_text or '-' in w_text or '이상' in w_text:
            return base_unit_price * target_w, gubun, target_w
        else:
            return base_unit_price, gubun, target_w
            
    return None, None, target_w

# --- UI 레이아웃 ---
st.set_page_config(page_title="FEDEX 항공 운임 예측 계산기", layout="wide")
st.title("✈️ FEDEX 항공 운임 예측 계산기")

df_ip, df_ie = load_and_split_data()

if df_ip is None:
    st.error(f"'{FILE_NAME}' 파일을 찾을 수 없습니다.")
else:
    selected_addr = st.selectbox("📌 자주 쓰는 주소 선택", list(FAVORITE_ADDRESSES.keys()))
    addr_info = FAVORITE_ADDRESSES[selected_addr]
    
    with st.form("calc_form"):
        col1, col2 = st.columns(2)
        with col1:
            zip_input = st.text_input("우편번호 (ZIP CODE)", value=addr_info["zip"])
            weight = st.number_input("화물 중량 (kg)", min_value=0.5, step=0.1, value=10.0)
        with col2:
            auto_c = detect_country_by_zip(zip_input)
            country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
            idx = country_list.index(auto_c) if auto_c in country_list else (country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0)
            country = st.selectbox("출발 국가", country_list, index=idx)
            fuel_rate = st.number_input("현재 유류할증료 (%)", value=41.75)
        submitted = st.form_submit_button("운임 계산하기")

    if submitted:
        # 엑셀 상의 지역 매핑 한 번 더 확인 (F=미국 등)
        region = COUNTRY_REGION_MAP[country]
        
        fare_ip, gubun_ip, final_w_ip = get_fedex_fare(df_ip, weight, region)
        fare_ie, gubun_ie, final_w_ie = get_fedex_fare(df_ie, weight, region)

        st.divider()
        res_c1, res_c2 = st.columns(2)

        with res_c1:
            st.markdown("### 🚀 International Priority (IP)")
            if fare_ip:
                total_ip = fare_ip * (1 + fuel_rate/100)
                st.metric("IP 최종 합계", f"{int(total_ip):,.0f} 원")
                st.caption(f"적용 무게: {final_w_ip}kg | 기본 운임: {int(fare_ip):,.0f}원")
            else: st.warning("IP 요금 정보 없음")

        with res_c2:
            st.markdown("### 🐢 International Economy (IE)")
            if fare_ie:
                total_ie = fare_ie * (1 + fuel_rate/100)
                diff = (total_ip - total_ie) if fare_ip else 0
                st.metric("IE 최종 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                st.caption(f"적용 무게: {final_w_ie}kg | 기본 운임: {int(fare_ie):,.0f}원")
            else: st.info("IE 요금 정보가 없거나 해당 구간 미지원입니다.")

    st.divider()
    st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")