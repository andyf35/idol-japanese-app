import streamlit as st
import pandas as pd
from janome.tokenizer import Tokenizer
import pykakasi
import os
import requests
from bs4 import BeautifulSoup
import random
from gtts import gTTS
from io import BytesIO

st.set_page_config(page_title="💌 專屬偶像日文學習台", layout="wide")

@st.cache_resource
def load_tools():
    t = Tokenizer()
    kks = pykakasi.kakasi()
    return t, kks

t, kks = load_tools()

# --- 修復 1：防止高等級覆蓋基礎等級 ---
@st.cache_data
def load_jlpt_dict():
    merged_dict = {}
    levels = ["N5", "N4", "N3", "N2", "N1"]
    
    for level in levels:
        file_name = f"{level}.csv"
        if os.path.exists(file_name):
            try:
                df = pd.read_csv(file_name, header=None)
                words = df.iloc[:, 0].dropna().astype(str).tolist()
                for w in words:
                    if w not in ["單字", "word", "vocab", "vocabulary"]:
                        if w not in merged_dict:
                            merged_dict[w] = level
            except Exception as e:
                st.error(f"讀取 {file_name} 發生錯誤：{e}")
                
    if not merged_dict:
        return {"私": "N5", "可愛い": "N4", "公演": "N3", "感謝": "N2", "唯一": "N1"}
        
    return merged_dict

jlpt_dict = load_jlpt_dict()

@st.cache_data
def load_grammar_dict():
    return {
        "につきまして": "N3文法 (關於...)", "をもちまして": "N2文法 (以...為界/到此為止)",
        "させていただきます": "謙讓語 (請允許我們...)", "誠に": "敬語副詞 (非常地)",
        "ご了承": "尊敬語 (諒解)", "申し上げます": "謙讓語 (說/表達)",
        "予定しております": "謙讓語 (預計)", "ご案内": "謙讓/尊敬語 (通知/引導)",
        "お手数ですが": "慣用句 (雖然麻煩您...)", "よろしくお願い申し上げます": "慣用句 (懇請您多多指教)"
    }

grammar_dict = load_grammar_dict()

VOCAB_FILE = "my_vocab.csv"
def init_vocab_file():
    if not os.path.exists(VOCAB_FILE):
        df = pd.DataFrame(columns=["單字", "假名", "羅馬拼音", "意思 (自填)", "詞性", "JLPT等級"])
        df.to_csv(VOCAB_FILE, index=False, encoding="utf-8-sig")

init_vocab_file()

st.title("💌 專屬偶像日文學習台 (究極完全版 🚀)")

tab1, tab2, tab3 = st.tabs(["💌 智慧解析器", "📢 官方公告抓取", "🗂️ 閃卡與發音室"])

# ==========================================
# 分頁 1：智慧解析器
# ==========================================
with tab1:
    email_text = st.text_area("貼上秋山由奈/八木愛月的信件：", height=200)

    if st.button("✨ 開始解析"):
        if email_text.strip() == "":
            st.warning("請先貼上內容喔！")
        else:
            st.divider()
            
            st.subheader("📖 假名與羅馬拼音對照版 (上下分層流)")
            
            # 1. 顯示乾淨的原文字幕區塊
            st.markdown("**【原文內容】**")
            st.markdown(f"<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; font-size: 1.1rem; line-height: 1.8;'>{email_text}</div>", unsafe_allow_html=True)
            
            # 2. 處理平假名與羅馬拼音轉換
            safe_text = email_text.replace("今日は", "今日|は")
            result = kks.convert(safe_text)
            
            hira_line = ""
            romaji_line = ""
            for item in result:
                hira_line += item['hira']
                romaji_line += item['hepburn'] + " "
                
            hira_line = hira_line.replace("|", "")
            
            # 3. 顯示平假名讀音
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**【平假名對照】**")
            st.info(hira_line)
            
            # 4. 顯示羅馬拼音 (方便 Talk 會直接唸)
            st.markdown("**【羅馬拼音 (Talk會直讀)】**")
            st.success(romaji_line)
            
            st.divider()

            st.subheader("🔍 單字解析列表 (附羅馬拼音)")
            with st.spinner("正在比對 8000 字題庫並標示羅馬拼音..."):
                tokens = t.tokenize(email_text)
                vocab_list = []
                
                for token in tokens:
                    pos = token.part_of_speech.split(',')[0]
                    if pos in ['名詞', '動詞', '形容詞', '副詞']:
                        base_form = token.base_form 
                        
                        # --- 修復 2：直接將「原形」轉成假名與羅馬拼音 ---
                        hira_reading = "".join([i['hira'] for i in kks.convert(base_form)])
                        romaji_reading = "".join([i['hepburn'] for i in kks.convert(base_form)])
                        jlpt_level = jlpt_dict.get(base_form, "不在考綱內")
                        
                        vocab_list.append({
                            "單字 (原形)": base_form,
                            "假名": hira_reading,
                            "羅馬拼音": romaji_reading,
                            "詞性": pos,
                            "JLPT等級": jlpt_level
                        })
                
                df_vocab = pd.DataFrame(vocab_list).drop_duplicates(subset=["單字 (原形)"]).reset_index(drop=True)
                df_vocab = df_vocab.sort_values(by="JLPT等級", ascending=True).reset_index(drop=True)
                
                df_vocab.insert(3, "意思 (自填)", "")
                
                st.dataframe(df_vocab, use_container_width=True)
                st.session_state['current_vocab'] = df_vocab

    if 'current_vocab' in st.session_state:
        st.divider()
        st.subheader("💾 存入專屬單字本")
        df_to_save = st.session_state['current_vocab'].copy()
        df_to_save.insert(0, "加入單字本", False) 
        
        edited_df = st.data_editor(df_to_save, hide_index=True, column_config={"加入單字本": st.column_config.CheckboxColumn(required=True)}, use_container_width=True)
        
        if st.button("儲存勾選的單字"):
            selected_words = edited_df[edited_df["加入單字本"] == True]
            if not selected_words.empty:
                save_df = pd.DataFrame({
                    "單字": selected_words["單字 (原形)"], "假名": selected_words["假名"],
                    "羅馬拼音": selected_words["羅馬拼音"], "意思 (自填)": selected_words["意思 (自填)"],
                    "詞性": selected_words["詞性"], "JLPT等級": selected_words["JLPT等級"]
                })
                save_df.to_csv(VOCAB_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")
                st.success(f"成功加入單字本！")

# ==========================================
# 分頁 2：官方公告抓取 
# ==========================================
with tab2:
    if st.button("🌐 抓取 AKB48 最新公告"):
        with st.spinner("正在前往抓取資料..."):
            try:
                url = "https://ameblo.jp/akihabara48/"
                response = requests.get(url)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, "html.parser")
                articles = soup.find_all("h2")
                
                news_list = []
                for h2 in articles:
                    a_tag = h2.find("a")
                    if a_tag and a_tag.text:
                        title = a_tag.text.strip()
                        link = a_tag["href"]
                        if "http" not in link: link = "https://ameblo.jp" + link
                        if len(title) > 5: news_list.append({"公告標題": title, "連結": link})
                
                if news_list:
                    st.dataframe(pd.DataFrame(news_list), column_config={"連結": st.column_config.LinkColumn("點擊閱讀原文")}, hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"抓取失敗：{e}")

# ==========================================
# 分頁 3：閃卡與發音室
# ==========================================
with tab3:
    st.markdown("利用羅馬拼音與 AI 發音，即使不會五十音也能輕鬆開口！")
    df_saved = pd.read_csv(VOCAB_FILE)
    
    if df_saved.empty:
        st.info("你的單字本目前是空的喔！快去「智慧解析器」存幾個單字吧！")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📇 語音閃卡測驗")
            if 'flashcard_idx' not in st.session_state:
                st.session_state['flashcard_idx'] = 0
            if 'show_answer' not in st.session_state:
                st.session_state['show_answer'] = False
                
            def next_card():
                st.session_state['flashcard_idx'] = random.randint(0, len(df_saved)-1)
                st.session_state['show_answer'] = False
                
            st.button("🎲 隨機抽一張", on_click=next_card)
            current_word = df_saved.iloc[st.session_state['flashcard_idx']]
            
            st.markdown(
                f"""
                <div style='background-color: #f0f2f6; border-radius: 10px; padding: 40px; text-align: center; margin-top: 10px; margin-bottom: 10px;'>
                    <h1 style='font-size: 3rem; margin: 0;'>{current_word['單字']}</h1>
                </div>
                """, unsafe_allow_html=True
            )
            
            if st.button("🔊 聽發音 (AI 朗讀)"):
                try:
                    tts = gTTS(current_word['單字'], lang='ja')
                    fp = BytesIO()
                    tts.write_to_fp(fp)
                    st.audio(fp, format="audio/mp3", autoplay=True)
                except Exception as e:
                    st.error("發音伺服器暫時無回應，請稍後再試。")
            
            if st.button("🔄 翻開看羅馬拼音與意思"):
                st.session_state['show_answer'] = True
                
            if st.session_state['show_answer']:
                st.success(f"""
                **意思 (自填)：** {current_word['意思 (自填)']}  
                **羅馬拼音：** `{current_word['羅馬拼音']}`  
                **平假名：** {current_word['假名']}  
                **JLPT等級：** {current_word['JLPT等級']}
                """)
                
        with col2:
            st.subheader("💬 羅馬拼音對照小抄")
            st.write("Talk 會時可以直接看著羅馬拼音唸出來：")
            st.dataframe(df_saved[['單字', '羅馬拼音', '意思 (自填)']], height=300, use_container_width=True)
