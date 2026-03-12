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
        
        # 1단계: 핀터레스트 크롤링 및 캔버스 추출 다운로드
        status_text.write("🔍 [1/2 단계] 인터넷에서 고화질 레퍼런스 고속 수집 중...")
        
        driver = None
        try:
            # [배포 대비 설정] 서버 환경에서도 작동하도록 화면 없이(headless) 실행 옵션을 추가합니다.
            options = webdriver.ChromeOptions()
            options.add_argument("--headless") # 화면 없이 실행 (서버용)
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            
            # 사용자 전용 프로필 설정
            bot_data_dir = os.path.join(os.getcwd(), 'bot_chrome_profile')
            options.add_argument(f"user-data-dir={bot_data_dir}")
            options.add_argument("--disable-session-crashed-bubble")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            try:
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            except Exception as e:
                st.error(f"🚨 예상치 못한 크롬 로드 실패: {e}")
                st.stop()
                
            # 브라우저 열고 이동
            time.sleep(1)
            driver.get(f"https://www.pinterest.com/search/pins/?q={keyword}")
            
            status_text.write("⏳ [알림] 봇이 핀터레스트에 접속했습니다. 만약 화면에 로그인 팝업이 뜬다면, 15초 안에 로그인을 완료해주세요!")
            time.sleep(15) # 사용자가 로그인할 수 있는 충분한 시간 제공 (이후로는 bot_chrome_profile에 유지됨)
            
            seen_srcs = set()
            saved_files = [] # 다운로드 된 사진들의 정확한 위치를 담을 리스트
            
            no_new_image_attempts = 0 # 무한 루프 방지용 카운터
            
            with st.spinner("최고의 레퍼런스를 핀터레스트에서 추출 중입니다..."):
                while len(saved_files) < target_count:
                    # 화면 스크롤
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3) # 이미지들이 화면에 표시될 때까지 충분히 대기
                    
                    try:
                        imgs = driver.find_elements(By.TAG_NAME, "img")
                    except Exception:
                        st.error("⚠️ 로봇 작동 중 크롬 창이 의도치 않게 닫혔습니다!")
                        break
                        
                    new_found_this_turn = 0
                    
                    # 방금 뜬 새사진들 위주로 탐색
                    for img in reversed(imgs): 
                        if len(saved_files) >= target_count: break
                        
                        try:
                            width = img.size['width']
                            height = img.size['height']
                            src = img.get_attribute("src")
                            
                            # 크기가 너무 작은 UI 아이콘/검색어 추천 칩(Chip)을 제외하고 진짜 핀터레스트 사진만 수집!
                            if width > 120 and height > 120 and src and "pinimg.com" in src and "profile" not in src and src not in seen_srcs:
                                # [개선된 수집 방법: URL 직접 다운로드] 
                                # 화면상의 'Portable', 'Wood' 같은 UI 버튼/텍스트를 피하기 위해, 브라우저 캡쳐가 아닌 
                                # 원본 이미지 파일의 URL을 직접 요청하여 깨끗한 사진만 받아옵니다.
                                
                                # 고화질 변환 (236x -> 736x)
                                high_res_src = src.replace("/236x/", "/736x/")
                                
                                try:
                                    headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                    }
                                    img_data = requests.get(high_res_src, headers=headers).content
                                    
                                    # 컴퓨터에 파일 쓰기
                                    file_name = f"ref_{len(saved_files)+1}.png"
                                    filepath = os.path.join(save_path, file_name)
                                    with open(filepath, 'wb') as handler:
                                        handler.write(img_data)
                                            
                                    seen_srcs.add(src)
                                    saved_files.append(filepath)
                                    new_found_this_turn += 1
                                    
                                    # 진행률 바 업데이트 (절반은 수집에 할당)
                                    progress_bar.progress((len(saved_files) / target_count) * 0.5)
                                    status_text.write(f"📥 [1/2 단계] {len(saved_files)}/{target_count} 장 사진 다운로드 성공!")
                                except Exception as download_err:
                                    continue
                        except Exception:
                            continue
                    
                    # 만약 화면을 내렸는데도 새로운 사진을 한 장도 못 찾았다면 카운트 증가
                    if new_found_this_turn == 0:
                        no_new_image_attempts += 1
                        if no_new_image_attempts >= 6: # 6번 연속 실패시
                            st.warning(f"⚠️ 핀터레스트 화면 제한으로 인해 더 이상 스크롤할 수 없어 {len(saved_files)}장까지만 수집했습니다.")
                            break
                    else:
                        no_new_image_attempts = 0 # 새 사진을 찾았으면 무한 로딩 카운트 리셋
                            
            if driver:
                driver.quit() # 브라우저 닫기
            
            # 수집된 사진이 없으면 중단
            if len(saved_files) == 0:
                st.warning("수집된 이미지가 없습니다. 크롬 창을 모두 닫은 후 다시 시도해보세요.")
                st.stop()
                
            # 2단계: AI 분석
            status_text.write(f"🧠 [2/2 단계] 수집된 {len(saved_files)}장의 레퍼런스에 대해 전문적인 AI 조형 분석을 시작합니다...")
            classified_images = {c: [] for c in categories}
            
            with st.spinner("AI가 각 제품 디자인의 썸네일을 보고 형태학적, 재질적 스타일을 철저하게 분류하고 있습니다..."):
                for idx, filepath in enumerate(saved_files):
                    try:
                        pil_img = Image.open(filepath).convert("RGB")
                        
                        # [개선된 분류 방법: 키워드 기반 템플릿 사용]
                        # AI에게 '스타일 명칭'만 주는 것이 아니라, "어떤 제품인지(keyword)"를 포함한 문장을 주어
                        # 이미지와의 유사성을 훨씬 정확하게 판단하게 합니다.
                        prompt_templates = [f"A professional product photo of a {keyword} in {category} style" for category in categories]
                        
                        # 모델 입력 및 계산
                        inputs = processor(text=prompt_templates, images=pil_img, return_tensors="pt", padding=True)
                        with torch.no_grad():
                            outputs = model(**inputs)
                            
                        # 확률 계산 및 분류
                        probs = outputs.logits_per_image.softmax(dim=1)
                        best_category = categories[probs.argmax().item()]
                        
                        classified_images[best_category].append(filepath)
                        
                        # 진행률 바 업데이트 (나머지 절반은 분석에 할당)
                        current_progress = 0.5 + ((idx + 1) / target_count) * 0.5
                        progress_bar.progress(current_progress)
                        status_text.write(f"🔄 [2/2 단계] {idx + 1}/{len(saved_files)} 분석 완료 | 최근 판독 결과: **{best_category}**")
                        
                    except Exception as e:
                        pass
            
            # 모든 작업 완료
            st.success(f"🎉 환상적입니다! {len(saved_files)}장의 제품 래퍼런스를 지정 폴더('{save_path}')에 다운로드하고, 즉시 AI 조형 분류까지 마쳤습니다.")
            st.balloons()
            
            # ==========================================
            # 결과 리포트 출력 영역
            # ==========================================
            st.header("✨ AI 디자인 스타일 무드보드 (결과 리포트)")
            st.write("👉 **이미지를 직접 마우스로 클릭하면 새로운 창에서 선명한 원본 크기로 꽉 차게 확대(Zoom)됩니다!**")
            
            for category in categories:
                img_list = classified_images[category]
                st.subheader(f"🎨 {category} 스타일 ({len(img_list)}장)")
                
                if len(img_list) > 0:
                    # 4칸씩 격자로 나열 (사진이 큼직하게 보이도록)
                    cols = st.columns(4)
                    
                    for i, img_path in enumerate(img_list):
                        with cols[i % 4]:
                            # 직접 클릭해서 탭으로 확대 가능한 직관적 HTML 이미지 생성
                            with open(img_path, "rb") as img_file:
                                b64 = base64.b64encode(img_file.read()).decode()
                            
                            html_str = f'''
                            <a href="data:image/png;base64,{b64}" target="_blank" title="🖱️ 클릭해서 원본 보기">
                                <img src="data:image/png;base64,{b64}" 
                                     style="width:100%; border-radius:12px; transition: transform 0.2s ease; box-shadow: 0 4px 6px rgba(0,0,0,0.1); cursor: zoom-in;" 
                                     onmouseover="this.style.transform='scale(1.05)'" 
                                     onmouseout="this.style.transform='scale(1)'">
                            </a>
                            '''
                            st.markdown(html_str, unsafe_allow_html=True)
                else:
                    st.info("이 스타일로 분류된 레퍼런스 사진이 없습니다.")
                    
                st.write("---")

        except Exception as e:
            if driver:
                driver.quit()
            st.error(f"실행 중 심각한 오류가 발생했습니다: {e}")