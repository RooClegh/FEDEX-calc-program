import streamlit as st
import pandas as pd
import os
import math
import re

# 1. 페이지 설정
st.set_page_config(page_title="동명베아링 FEDEX 계산기", layout="wide")

# CSS: 디자인 커스텀
st.markdown("""
    <style>
    /* 제목 스타일: 크기를 대폭 키우고 흰색으로 설정 */
    .main-title { 
        color: #ffffff; 
        font-weight: bold; 
        font-size: 3rem; 
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        margin-bottom: 5px;
    }
    
    /* 도착지 정보 섹션 */
    .dest-info {
        background-color: #4D148C;
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        border-left: 8px solid #FF6600;
    }
    
    /* 설정 헤더 (흰색) */
    .setting-header {
        color: #ffffff;
        font-weight: bold;
        font-size: 1.3rem;
        margin-top: 10px;
        margin-bottom: 15px;
    }

    /* 버튼 스타일 (주황색) */
    div.stButton > button:first-child {
        background-color: #FF6600;
        color: white;
        height: 3.5em;
        font-weight: bold;
        border: none;
        width: 100%;
        font-size: 1.1rem;
    }
    div.stButton > button:first-child:hover {
        background-color: #e65c00;
        border: none;
    }

    /* 다크모드/라이트모드 대응을 위한 텍스트 가독성 설정 */
    .stWrite, .stCaption {
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

FILE_NAME = 'FEDEX_2026.csv'

@st.cache_data
def load_all_data():
    if not os.path.exists(FILE_NAME): return None, None, {}
    raw_df = pd.read_csv(FILE_NAME, header=None).fillna("")
    
    region_map = {}
    for i, row in raw_df.iterrows():
        row_list = [str(val).strip() for val in row.values if str(val).strip()]
        if len(row_list) < 2: continue
        country_name = row_list[0]
        possible_regions = [v for v in row_list if len(v) == 1 and v.isalpha() and v.isupper()]
        if possible_regions and len(country_name) > 1:
            region_map[country_name] = f"지역 {possible_regions[-1]}"

    ip_idx, ie_idx = -1, -1
    for i, row in raw_df.iterrows():
        row_str = "".join([str(v) for v in row.values])
        if "Priority" in row_str and ip_idx == -1: ip_idx = i
        if "Economy" in row_str and ie_idx == -1: ie_idx = i

    cols = ["중량", "구분", "지역 A", "지역 D", "지역 E", "지역 F", "지역 G", "지역 H", "지역 I", "지역 J", "지역 K", "지역 M", "지역 N", "지역 O", "지역 P", "지역 Q", "지역 R", "지역 S", "지역 T", "지역 U", "지역 V", "지역 W", "지역 X", "지역 Y"]
    
    def extract_section(start, end):
        df = raw_df.iloc[start:end, :].copy()
        df = df[df[0].astype(str).str.contains(r'\d|Envelope|Pak', na=False)]
        df = df.iloc[:, :len(cols)]
        df.columns = cols[:df.shape[1]]
        for c in df.columns[2:]:
            df[c] = df[c].astype(str).str.replace(',', '').str.replace(' ', '').str.strip()
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    df_ip = extract_section(ip_idx + 2, ie_idx - 2)
    df_ie = extract_section(ie_idx + 2, len(raw_df))
    return df_ip, df_ie, region_map

def calculate_fare(df, weight, region_col):
    if df.empty or region_col not in df.columns: return None, None, weight
    target_w = math.ceil(weight * 2) / 2
    match = pd.DataFrame()
    target_str = f"{target_w:.1f}" if target_w % 1 != 0 else f"{int(target_w)}"
    match = df[df['중량'].astype(str).str.strip() == target_str]
    
    if match.empty:
        for _, row in df.iterrows():
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
        if any(x in w_txt or x in gubun for x in ['~', '-', '이상', 'kg당']):
            return base * target_w, gubun, target_w
        return base, gubun, target_w
    return None, None, target_w

# --- 데이터 로드 ---
df_ip, df_ie, region_map = load_all_data()

# 1. 제목 (크기 확대 & 흰색)
st.markdown('<p class="main-title">✈️ FEDEX 항공 운임 예측 계산기</p>', unsafe_allow_html=True)

# 2. 도착지 고정 정보 (동명베아링)
st.markdown(f"""
    <div class="dest-info">
        <span style="font-size:1.1rem; opacity:0.9;">📦 수신처(도착지) 고정</span><br>
        <span style="font-size:1.5rem; font-weight:bold;">동명베아링</span><br>
        <span style="font-size:1rem;">부산광역시 사상구 새벽로215번길 123 (전화: 051-XXX-XXXX)</span>
    </div>
    """, unsafe_allow_html=True)

if df_ip is None:
    st.error("데이터 파일을 찾을 수 없습니다. (FEDEX_2026.csv)")
else:
    # 3. 즐겨찾기 설정
    fav_options = {
        "직접 입력 (국가 선택)": {"country": "일본", "addr": ""},
        "TIMKEN (미국)": {"country": "미국", "addr": "4500 MOUNT PLEASANT ST NW NORTH CANTON, Ohio, UNITED STATES, 44720"},
        "IKO (일본)": {"country": "일본", "addr": "2-19-19 TAKANAWA MINARO-GU TOKYO JAPAN 108-8586"}
    }
    
    # 4. 입력 섹션
    st.markdown('<p class="setting-header">📋 발송 정보 설정 (입력 시 자동 계산 준비)</p>', unsafe_allow_html=True)
    
    # 한 카드 형태의 레이아웃 구성
    c1, c2, c3 = st.columns([1.5, 1, 1])
    
    with c1:
        selected_fav = st.selectbox("⭐ 즐겨찾기 주소 선택", list(fav_options.keys()))
        fav_data = fav_options[selected_fav]
        
        countries = sorted(list(region_map.keys()))
        default_country = fav_data["country"]
        default_idx = countries.index(default_country) if default_country in countries else 0
        selected_country = st.selectbox("출발 국가", countries, index=default_idx)
        
    with c2:
        weight_input = st.number_input("화물 실중량 (kg)", min_value=0.5, value=10.0, step=0.1)
        target_region = region_map.get(selected_country, "지역 A")
        st.info(f"📍 적용 요금 지역: **{target_region}**")
        
    with c3:
        fuel_rate = st.number_input("유류할증료 (%)", value=41.75, step=0.01)
        if fav_data["addr"]:
            st.caption(f"🏠 발송지 주소: {fav_data['addr']}")

    # 운임 계산 버튼
    if st.button("🚀 예측 운임 계산하기"):
        ip_val, ip_gb, ip_w = calculate_fare(df_ip, weight_input, target_region)
        ie_val, ie_gb, ie_w = calculate_fare(df_ie, weight_input, target_region)
        
        st.divider()
        res_col1, res_col2 = st.columns(2)
        
        with res_col1:
            with st.container(border=True):
                st.markdown('<p style="color:#4D148C; font-weight:bold; font-size:1.3rem;">🚀 Priority (IP)</p>', unsafe_allow_html=True)
                if ip_val:
                    total_ip = ip_val * (1 + fuel_rate/100)
                    st.metric("최종 예상액", f"{int(total_ip):,.0f} 원")
                    st.caption(f"청구 중량: {ip_w}kg | 기본 운임: {int(ip_val):,.0f}원")
                else: st.warning("데이터 없음")

        with res_col2:
            with st.container(border=True):
                st.markdown('<p style="color:#4D148C; font-weight:bold; font-size:1.3rem;">🐢 Economy (IE)</p>', unsafe_allow_html=True)
                if ie_val:
                    total_ie = ie_val * (1 + fuel_rate/100)
                    diff = (total_ip - total_ie) if ip_val else 0
                    st.metric("최종 예상액", f"{int(total_ie):,.0f} 원", delta=f"-{int(diff):,.0f}원" if diff > 0 else None)
                    st.caption(f"청구 중량: {ie_w}kg | 기본 운임: {int(ie_val):,.0f}원")
                else: st.info("IE 미지원 구간")

# 5. 푸터 및 주의사항
st.divider()
st.markdown('<p style="color:#FF6600; font-weight:bold;">⚠️ 필독 주의사항</p>', unsafe_allow_html=True)
st.markdown('<p style="font-size:0.9rem; opacity:0.8;">본 시스템은 동명베아링 내부 참조용입니다. 실제 FedEx 인보이스 금액은 부피 중량(CBM) 적용 여부 및 현지 부대 비용에 따라 차이가 발생할 수 있습니다.</p>', unsafe_allow_html=True)
st.caption("© 2026 Dongmyeong Bearing | 제작: 서주영 대리")