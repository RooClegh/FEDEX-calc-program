import streamlit as st
import pandas as pd

# CSV 파일 경로 (파일이 app.py와 같은 폴더에 있어야 합니다)
file_path = '2026 FEDEX.csv'

def load_data():
    # 1. 상단 3행을 제외하고 읽어오기 (4행이 컬럼명이 됩니다)
    df = pd.read_csv(file_path, skiprows=3)
    
    # 2. 금액 데이터 전처리 (콤마 제거 및 숫자로 변환)
    # 존 A부터 존 J까지의 열을 선택합니다.
    zone_columns = ['존 A', '존 B', '존 C', '존 D', '존 E', '존 F', '존 G', '존 H', '존 I', '존 J']
    
    for col in zone_columns:
        # 데이터에 콤마(,)가 문자열로 섞여 있을 경우 제거하고 숫자로 변환
        df[col] = df[col].astype(str).str.replace(',', '').replace('nan', '0')
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
    return df

# 데이터 불러오기 실행
try:
    df = load_data()
    st.success("✅ 데이터를 성공적으로 불러왔습니다!")
    
    # 데이터가 잘 들어왔는지 화면에 표로 확인
    st.write("### 📊 불러온 데이터 미리보기 (상위 10개)")
    st.dataframe(df.head(10))

except Exception as e:
    st.error(f"❌ 데이터를 불러오는 중 오류가 발생했습니다: {e}")