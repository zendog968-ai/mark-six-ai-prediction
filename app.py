import streamlit as st

from lotto_data import (
    REQUIRED_COLUMNS,
    generate_filtered_combinations,
    read_csv_with_validation,
    select_data_source,
    train_random_forest,
)


st.set_page_config(page_title="六合彩資料分析實驗室", page_icon="🎱", layout="wide")
st.title("六合彩數據分析與 AI 實驗室")
st.caption("系統僅供統計教育與實驗用途，無法可靠預測真實開獎結果。")

with st.sidebar:
    st.header("資料來源")
    uploaded_file = st.file_uploader(
        "上傳真實歷史開獎 CSV",
        type=["csv"],
        help="必要欄位：Draw、Date、N1、N2、N3、N4、N5、N6、Special。",
    )
    st.caption("有效 CSV 會自動取代模擬資料，用於特徵工程與模型訓練。")

validated_upload = None
if uploaded_file is not None:
    validation = read_csv_with_validation(uploaded_file)
    if validation.is_valid:
        validated_upload = validation.data
        st.sidebar.success(f"驗證通過：已載入 {len(validated_upload):,} 期真實資料。")
    else:
        st.sidebar.error("CSV 格式或資料驗證失敗。請修正後重新上傳。")
        for error in validation.errors:
            st.sidebar.error(error)

draws, source_label = select_data_source(validated_upload)
if validated_upload is None and uploaded_file is not None:
    st.error("上傳檔案未通過驗證，因此系統不會用它訓練模型；目前仍顯示模擬資料。")

st.info(f"目前資料來源：**{source_label}**；共 {len(draws):,} 期紀錄。")
overview_tab, model_tab, data_tab = st.tabs(["資料概覽", "模型實驗", "已載入資料"])

with overview_tab:
    st.subheader("資料品質與近期紀錄")
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("期數", f"{len(draws):,}")
    metric_b.metric("起始日期", draws["Date"].min().date().isoformat())
    metric_c.metric("最新日期", draws["Date"].max().date().isoformat())
    st.dataframe(draws.tail(20), width="stretch", hide_index=True)

with model_tab:
    st.subheader("特徵工程與 Random Forest 實驗")
    st.caption("每個候選號碼使用近 50 期頻率、近 10 期頻率與 Gap；有效上傳資料會在此直接取代模擬資料。")
    with st.spinner("正在依目前資料來源建立特徵與訓練模型…"):
        ranked_probabilities, training_error = train_random_forest(draws)
    if training_error:
        st.warning(training_error)
    else:
        ranking_table = [{"排名": index + 1, "號碼": number, "相對分數": round(float(score) * 100, 2)} for index, (number, score) in enumerate(ranked_probabilities[:15])]
        left, right = st.columns([1, 1.4])
        with left:
            st.dataframe(ranking_table, width="stretch", hide_index=True)
        with right:
            st.bar_chart({"相對分數": {str(row["號碼"]): row["相對分數"] for row in ranking_table}})
        st.markdown("#### 經奇偶過濾的實驗性組合")
        for index, combination in enumerate(generate_filtered_combinations(ranked_probabilities), start=1):
            odd_count = sum(number % 2 for number in combination)
            st.write(f"組合 {index:02d}：{' · '.join(f'{number:02d}' for number in combination)}　|　{odd_count} 單 / {6 - odd_count} 雙　|　總和 {sum(combination)}")

with data_tab:
    st.subheader("CSV 欄位規格")
    st.code(", ".join(REQUIRED_COLUMNS), language=None)
    st.dataframe(draws, width="stretch", hide_index=True)
