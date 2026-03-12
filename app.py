import streamlit as st
import time
import os
import requests
import base64
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import InvalidArgumentException
import platform

@st.cache_resource
def load_model():
    print("AI 엔진(CLIP) 다운로드 및 로딩을 시작합니다... (최초 1회 소요)")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    return model, processor

# 앱 기본 설정
st.set_page_config(page_title="최고의 제품 디자인 레퍼런스 AI", layout="wide")
st.title("🏆 AI 제품 디자인 스타일 분류 및 스크랩 마스터")
st.write("세계 최고의 제품 디자인 전문가 AI입니다. 원하시는 제품을 검색하면 핀터레스트에서 레퍼런스를 자동으로 스크랩하고, 즉시 조형적 스타일로 정밀하게 분류해 드립니다.")

# 모델 로드 (앱 상단에 고정 표시)
model_load_state = st.empty()
with model_load_state.container():
    with st.spinner("🧠 딥러닝 기반 제품 디자인 조형 분석 엔진을 깨우는 중..."):
        model, processor = load_model()
    st.success("✅ AI 디자인 분석 엔진 준비 완료!")
    time.sleep(1)
model_load_state.empty()

# ==========================================
# 사용자 설정 영역
# ==========================================
st.subheader("1. 🎨 레퍼런스 탐색 및 디자인 분류 설정")

col1, col2 = st.columns(2)
with col1:
    keyword = st.text_input("수집할 제품 키워드 (예: Bluetooth speaker design)", "Bluetooth speaker design")
    target_count = st.number_input("수집할 레퍼런스 목표 개수", min_value=1, max_value=1000, value=50, step=10)
with col2:
    st.write("💡 AI 조형 분류 기준 (쉼표로 구분. AI는 영어를 훨씬 정확하게 인지합니다.)")
    categories_input = st.text_input(
        "어떤 디자인 언어로 레퍼런스를 분류할까요?", 
        "Braun style vintage, Apple minimalist, Cyberpunk industrial, Organic modern, Retro futuristic"
    )
    # [개선] 쉼표로 구분하되, 양끝 공백을 제거하고 빈 항목은 제외합니다.
    categories = [c.strip() for c in categories_input.replace('\n', ',').split(',') if c.strip()]

st.write("---")

# ==========================================
# 실행 영역
# ==========================================
if st.button("🚀 제품 디자인 레퍼런스 자동 탐색 및 AI 분류 시작", type="primary"):
    if len(categories) == 0:
        st.error("❌ 분류 기준을 1개 이상 입력해 주세요.")
    else:
        st.info(f"📍 총 {len(categories)}개의 분류 기준으로 AI 분석을 시작합니다: {', '.join(categories)}")
        # 저장할 폴더 자동 생성 (현재 폴더 아래)
        save_path = os.path.join(os.getcwd(), f"References_{keyword.replace(' ', '_')}")
        if not os.path.exists(save_path):
            os.makedirs(save_path)
            
        st.info("💡 단계를 시작합니다! 핀터레스트 로봇이 작동하는 동안 열린 크롬 창을 스스로 닫지 마세요.")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1단계: 핀터레스트 크롤링 및 다운로드
        status_text.write("🔍 [1/2 단계] 인터넷에서 고화질 레퍼런스 고속 수집 중...")
        
        driver = None
        try:
            options = webdriver.ChromeOptions()
            is_linux = platform.system() == "Linux"
            
            if is_linux:
                # 1. 서버(Linux) 환경용 설정
                options.add_argument("--headless=new") 
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.binary_location = "/usr/bin/chromium"
                try:
                    driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
                except Exception:
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            else:
                # 2. 로컬(Windows) 환경용 설정
                # 디버깅을 위해 로컬에서는 화면을 띄움 (원하시면 --headless 추가 가능)
                # options.add_argument("--headless") 
                bot_data_dir = os.path.join(os.getcwd(), 'bot_chrome_profile')
                options.add_argument(f"user-data-dir={bot_data_dir}")
                options.add_argument("--disable-session-crashed-bubble")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception as e:
            st.error(f"🚨 크롬 로드 실패: {e}")
            st.stop()
                
        try:
            # 브라우저 열고 이동
            time.sleep(1)
            driver.get(f"https://www.pinterest.com/search/pins/?q={keyword}")
            status_text.write("⏳ [알림] 봇이 핀터레스트에 접속했습니다. 15초 대기 중...")
            time.sleep(15) 
            
            seen_srcs = set()
            saved_files = [] 
            no_new_image_attempts = 0 
            
            with st.spinner("최고의 레퍼런스를 핀터레스트에서 추출 중입니다..."):
                while len(saved_files) < target_count:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3) 
                    
                    try:
                        imgs = driver.find_elements(By.TAG_NAME, "img")
                    except Exception:
                        st.error("⚠️ 로봇 작동 중 크롬 창이 의도치 않게 닫혔습니다!")
                        break
                        
                    new_found_this_turn = 0
                    for img in reversed(imgs): 
                        if len(saved_files) >= target_count: break
                        try:
                            width = img.size['width']
                            height = img.size['height']
                            src = img.get_attribute("src")
                            
                            if width > 120 and height > 120 and src and "pinimg.com" in src and "profile" not in src and src not in seen_srcs:
                                high_res_src = src.replace("/236x/", "/736x/")
                                try:
                                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
                                    img_data = requests.get(high_res_src, headers=headers).content
                                    file_name = f"ref_{len(saved_files)+1}.png"
                                    filepath = os.path.join(save_path, file_name)
                                    with open(filepath, 'wb') as handler:
                                        handler.write(img_data)
                                    seen_srcs.add(src)
                                    saved_files.append(filepath)
                                    new_found_this_turn += 1
                                    progress_bar.progress((len(saved_files) / target_count) * 0.5)
                                    status_text.write(f"📥 [1/2 단계] {len(saved_files)}/{target_count} 장 사진 다운로드 성공!")
                                except Exception: continue
                        except Exception: continue
                    
                    if new_found_this_turn == 0:
                        no_new_image_attempts += 1
                        if no_new_image_attempts >= 6: break
                    else:
                        no_new_image_attempts = 0
                            
            if driver:
                driver.quit()
            
            if len(saved_files) == 0:
                st.warning("수집된 이미지가 없습니다. 다시 시도해보세요.")
                st.stop()
                
            # 2단계: AI 분석
            status_text.write(f"🧠 [2/2 단계] 수집된 {len(saved_files)}장의 레퍼런스 분석 시작...")
            classified_images = {c: [] for c in categories}
            
            with st.spinner("AI 분석 중..."):
                for idx, filepath in enumerate(saved_files):
                    try:
                        pil_img = Image.open(filepath).convert("RGB")
                        prompt_templates = [f"A professional product photo of a {keyword} in {category} style" for category in categories]
                        inputs = processor(text=prompt_templates, images=pil_img, return_tensors="pt", padding=True)
                        with torch.no_grad():
                            outputs = model(**inputs)
                        probs = outputs.logits_per_image.softmax(dim=1)
                        best_category = categories[probs.argmax().item()]
                        classified_images[best_category].append(filepath)
                        progress_bar.progress(0.5 + ((idx + 1) / len(saved_files)) * 0.5)
                        status_text.write(f"🔄 [2/2 단계] {idx + 1}/{len(saved_files)} 분석 완료: **{best_category}**")
                    except Exception: pass
            
            st.success(f"🎉 환상적입니다! {len(saved_files)}장의 분석을 모두 마쳤습니다.")
            st.balloons()
            
            st.header("✨ AI 디자인 스타일 무드보드")
            for category in categories:
                img_list = classified_images[category]
                st.subheader(f"🎨 {category} 스타일 ({len(img_list)}장)")
                if len(img_list) > 0:
                    cols = st.columns(4)
                    for i, img_path in enumerate(img_list):
                        with cols[i % 4]:
                            with open(img_path, "rb") as img_file:
                                b64 = base64.b64encode(img_file.read()).decode()
                            st.markdown(f'''<a href="data:image/png;base64,{b64}" target="_blank"><img src="data:image/png;base64,{b64}" style="width:100%; border-radius:12px;"></a>''', unsafe_allow_html=True)
                else:
                    st.info("이 스타일로 분류된 레퍼런스 사진이 없습니다.")
                st.write("---")

        except Exception as e:
            if driver: driver.quit()
            st.error(f"실행 중 오류 발생: {e}")