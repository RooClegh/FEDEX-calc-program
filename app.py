import streamlit as st
import pandas as pd
import os
import math
import re

FILE_NAME = 'FEDEX_2026.csv'

@st.cache_data
def load_all_data():
    if not os.path.exists(FILE_NAME):
        return None, None, {}
    
    # 1. 원본 데이터 로드
    raw_df = pd.read_csv(FILE_NAME, header=None).fillna("")
    
    # 2. 국가별 지역 매핑 (파일 하단부에서 자동 추출)
    region_map = {}
    for i, row in raw_df.iterrows():
        row_list = [str(val).strip() for val in row.values if str(val).strip()]
        if not row_list: continue
        
        # 국가명 식별 (보통 행의 첫 번째가 국가명, 마지막 근처가 지역 알파벳)
        country_candidate = row_list[0]
        # 지역 코드로 보이는 알파벳(A~Z)이 있는지 확인
        possible_regions = [v for v in row_list if v in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
        if possible_regions and len(country_candidate) > 1:
            # 가장 마지막에 나타나는 알파벳을 해당 국가의 지역 코드로 인식
            region_map[country_candidate] = f"지역 {possible_regions[-1]}"

    # 3. IP/IE 섹션 분리
    ip_idx = -1
    ie_idx = -1
    for i, row in raw_df.iterrows():
        row_str = "".join([str(v) for v in row.values])
        if "Priority" in row_str and ip_idx == -1: ip_idx = i
        if "Economy" in row_str and ie_idx == -1: ie_idx = i

    # 컬럼 정의 (무게, 구분, 지역 A~X)
    cols = ["중량", "구분"] + [f"지역 {chr(65+i)}" for i in range(24) if chr(65+i) != 'L'] # L 제외 A-X
    
    def get_clean_df(start, end):
        df = raw_df.iloc[start:end, :].copy()
        # 실제 숫자가 시작되는 행 찾기 및 컬럼 정리
        df = df[df[0].astype(str).str.contains(r'\d|Envelope|Pak', na=False)]
        # 필요한 열만 슬라이싱 (보통 0~15열 내외)
        df = df.iloc[:, :len(cols)]
        df.columns = cols[:df.shape[1]]
        
        for c in df.columns[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.replace(' ', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    df_ip = get_clean_df(ip_idx + 2, ie_idx - 2)
    df_ie = get_clean_df(ie_idx + 2, len(raw_df))
    
    return df_ip, df_ie, region_map

def calculate_fare(df, weight, region_col):
    if df.empty or region_col not in df.columns: return None, None, weight
    
    target_w = math.ceil(weight * 2) / 2
    match = pd.DataFrame()
    
    # 고정 중량 매칭
    target_str = f"{target_w:.1f}" if target_w % 1 != 0 else f"{int(target_w)}"
    match = df[df['중량'].astype(str).str.contains(f"^{target_str}$", na=False)]
    
    # 범위형 매칭
    if match.empty:
        for idx, row in df.iterrows():
            w_label = str(row['중량'])
            nums = re.findall(r'\d+', w_label)
            if len(nums) >= 2 and float(nums[0]) <= target_w <= float(nums[1]):
                match = pd.DataFrame([row]); break
            elif '이상' in w_label and target_w >= float(re.findall(r'\d+', w_label)[0]):
                match = pd.DataFrame([row]); break

    if not match.empty:
        base = float(match[region_col].iloc[0])
        gubun = str(match['구분'].iloc[0])
        w_txt = str(match['중량'].iloc[0])
        
        # 단가 곱하기 규칙
        if any(x in w_txt or x in gubun for x in ['~', '-', '이상', 'kg당']):
            return base * target_w, gubun, target_w
        return base, gubun, target_w
    return None, None, target_w

# --- UI ---
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="wide")
st.title("✈️ FEDEX 항공 운임 계산기 (최신판)")

df_ip, df_ie, region_map = load_all_data()

if not df_ip is None:
    # 엑셀에서 추출된 모든 국가 리스트
    countries = sorted(list(region_map.keys()))
    
    with st.sidebar:
        st.header("⚙️ 설정")
        country = st.selectbox("출발 국가", countries, index=countries.index("일본") if "일본" in countries else 0)
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01)
        st.info(f"📍 {country} 적용 지역: {region_map[country]}")

    weight = st.number_input("화물 중량 (kg)", min_value=0.5, value=10.0, step=0.5)
    
    if st.button("운임 계산하기"):
        reg_col = region_map[country]
        ip_val, ip_gb, ip_w = calculate_fare(df_ip, weight, reg_col)
        ie_val, ie_gb, ie_w = calculate_fare(df_ie, weight, reg_col)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚀 IP (Priority)")
            if ip_val:
                total = ip_val * (1 + fuel_rate/100)
                st.metric("합계", f"{int(total):,.0f} 원")
                st.caption(f"기본: {int(ip_val):,.0f}원 ({ip_gb})")
            else: st.warning("데이터 없음")
            
        with col2:
            st.subheader("🐢 IE (Economy)")
            if ie_val:
                total = ie_val * (1 + fuel_rate/100)
                st.metric("합계", f"{int(total):,.0f} 원")
                st.caption(f"기본: {int(ie_val):,.0f}원 ({ie_gb})")
            else: st.info("IE 미지원 구간")

st.divider()
st.caption("© 2026 Dongmyeong Bearing AI TFT | 제작: 서주영 대리")