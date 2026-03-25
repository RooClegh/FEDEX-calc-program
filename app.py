import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 파일 및 설정
FILE_NAME = 'FEDEX_2026.csv'

# [필독] 엑셀의 국가-지역 매핑에 맞춰 수정이 필요할 수 있습니다.
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
    
    # IP/IE 데이터 범위를 넉넉하게 잡습니다.
    df_ip = raw_df.iloc[1:70, 0:len(cols)].copy() 
    df_ie = raw_df.iloc[72:150, 0:len(cols)].copy() 
    
    def clean(df):
        df.columns = cols 
        for c in cols[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    return clean(df_ip), clean(df_ie)

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
            weight = st.number_input("화물 중량 (kg)", min_value=0.5, step=0.5, value=10.0)
        with col2:
            auto_c = detect_country_by_zip(zip_input)
            country_list = sorted(list(COUNTRY_REGION_MAP.keys()))
            idx = country_list.index(auto_c) if auto_c in country_list else (country_list.index(addr_info["country"]) if addr_info["country"] in country_list else 0)
            country = st.selectbox("출발 국가", country_list, index=idx)
            fuel_rate = st.number_input("현재 유류할증료 (%)", value=41.75)
        submitted = st.form_submit_button("운임 계산하기")

    if submitted:
        region = COUNTRY_REGION_MAP[country]
        up_weight = math.ceil(weight * 2) / 2 # 0.5 단위 올림
        
        # [핵심 로직] 서 대리님 3가지 규칙 적용 함수
        def calculate_final_fare(df, target_weight, reg):
            match = pd.DataFrame()
            # 1. 고정 중량 매칭 시도 (예: 10.0, 16.0)
            target_str = f"{target_weight:.1f}" if target_weight % 1 != 0 else f"{int(target_weight)}"
            match = df[df['중량(Kg)'].astype(str) == target_str]
            
            # 2. 범위형 매칭 시도 (예: 45-70)
            if match.empty:
                for idx, row in df.iterrows():
                    w_val = str(row['중량(Kg)'])
                    if '~' in w_val or '-' in w_val:
                        nums = re.findall(r'\d+', w_val)
                        if len(nums) == 2 and int(nums[0]) <= target_weight <= int(nums[1]):
                            match = df.loc[[idx]]
                            break
                    elif '이상' in w_val:
                        num = re.findall(r'\d+', w_val)[0]
                        if target_weight >= int(num):
                            match = df.loc[[idx]]
                            break

            if not match.empty:
                base_price = float(match[reg].iloc[0])
                gubun = str(match['구분'].iloc[0])
                w_label = str(match['중량(Kg)'].iloc[0])
                
                # 규칙 반영: 'kg당' 글자가 있거나 범위형(~)이면 무게를 곱함
                if 'kg당' in gubun or '~' in w_label or '-' in w_label or '이상' in w_label:
                    final_base = base_price * target_weight
                    calc_type = "단가 × 중량"
                else:
                    final_base = base_price
                    calc_type = "고정가"
                
                return final_base, gubun, calc_type
            return None, None, None

        fare_ip, gubun_ip, type_ip = calculate_final_fare(df_ip, up_weight, region)
        fare_ie, gubun_ie, type_ie = calculate_final_fare(df_ie, up_weight, region)

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🚀 International Priority (IP)")
            if fare_ip:
                total_ip = fare_ip * (1 + fuel_rate/100)
                st.metric("IP 최종 합계", f"{int(total_ip):,.0f} 원")
                st.caption(f"기본: {int(fare_ip):,.0f}원 | 방식: {type_ip}({gubun_ip})")
            else: st.warning(f"⚠️ {region} {up_weight}kg IP 데이터 없음")

        with c2:
            st.markdown("### 🐢 International Economy (IE)")
            if fare_ie:
                total_ie = fare_ie * (1 + fuel_rate/100)
                diff = (total_ip - total_ie) if fare_ip else 0
                st.metric("IE 최종 합계", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                st.caption(f"기본: {int(fare_ie):,.0f}원 | 방식: {type_ie}({gubun_ie})")
            else: st.warning(f"⚠️ {region} {up_weight}kg IE 데이터 없음")

    # --- 하단 강조 섹션 ---
    st.divider()
    st.markdown('<p style="color:#FF6600; font-weight:bold; margin-bottom:0px;">⚠️ 운임 주의사항</p>', unsafe_allow_html=True)
    st.markdown('<p style="color:#FF6600; font-size:0.9rem;">본 계산기는 예측치이며 실제 청구 금액은 부피 중량 등에 따라 달라질 수 있습니다.</p>', unsafe_allow_html=True)
    st.write("📅 유류할증료 안내")
    st.markdown('<a href="https://www.fedex.com/ko-kr/shipping/surcharges.html" target="_blank" style="color:#660099; font-weight:bold; text-decoration:none;">🔗 [FedEx 유류할증료 상세 확인 (클릭)]</a>', unsafe_allow_html=True)
    st.caption("© 2026 Dongmyeong Bearing AI Task Force Team | 제작: AI TFT 서주영 대리")