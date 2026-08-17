import streamlit as st

from lotto_data import (
    DEFAULT_REAL_HISTORY_PATH,
    REQUIRED_COLUMNS,
    filter_history,
    generate_filtered_combinations,
    read_csv_with_validation,
    rolling_backtest,
    select_data_source,
    train_fusion_model,
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
    st.caption("有效 CSV 會優先取代專案內真實歷史資料，用於特徵工程、模型訓練與回測。")
    st.caption(f"預設真實資料檔：`{DEFAULT_REAL_HISTORY_PATH.name}`")

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

draws, source_label = select_data_source(validated_upload, DEFAULT_REAL_HISTORY_PATH)
if validated_upload is None and uploaded_file is not None:
    st.error("上傳檔案未通過驗證，因此系統不會用它訓練模型；目前會使用專案內真實歷史資料（如不可用才回退模擬資料）。")

st.info(f"目前資料來源：**{source_label}**；共 {len(draws):,} 期紀錄。")
overview_tab, model_tab, backtest_tab, data_tab = st.tabs(["資料概覽", "模型實驗", "模型回測", "歷史資料預覽"])

with overview_tab:
    st.subheader("資料品質與近期紀錄")
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("期數", f"{len(draws):,}")
    metric_b.metric("起始日期", draws["Date"].min().date().isoformat())
    metric_c.metric("最新日期", draws["Date"].max().date().isoformat())
    st.dataframe(draws.tail(20), width="stretch", hide_index=True)

with model_tab:
    st.subheader("特徵工程與融合模型實驗")
    st.caption("每個候選號碼使用近 50 期頻率、近 10 期頻率、Gap 與 K-Means 群組代號；Random Forest 與 XGBoost 的相對分數以等權平均融合。")
    with st.spinner("正在依目前資料來源建立特徵與訓練模型…"):
        ranked_probabilities, model_details, training_error = train_fusion_model(draws)
    if training_error:
        st.warning(training_error)
    else:
        st.success("目前模型：Random Forest + XGBoost 融合模型；已加入 K-Means 特徵。")
        ranking_table = [
            {
                "排名": index + 1,
                "號碼": int(row.number),
                "融合分數": round(float(row.fused_score) * 100, 2),
                "RF 分數": round(float(row.random_forest_score) * 100, 2),
                "XGBoost 分數": round(float(row.xgboost_score) * 100, 2),
                "K-Means 群組": int(row.kmeans_cluster),
            }
            for index, row in enumerate(model_details.head(15).itertuples(index=False))
        ]
        left, right = st.columns([1, 1.4])
        with left:
            st.dataframe(ranking_table, width="stretch", hide_index=True)
        with right:
            st.bar_chart({"融合分數": {str(row["號碼"]): row["融合分數"] for row in ranking_table}})
        st.markdown("#### 經奇偶過濾的實驗性組合")
        for index, combination in enumerate(generate_filtered_combinations(ranked_probabilities), start=1):
            odd_count = sum(number % 2 for number in combination)
            st.write(f"組合 {index:02d}：{' · '.join(f'{number:02d}' for number in combination)}　|　{odd_count} 單 / {6 - odd_count} 雙　|　總和 {sum(combination)}")

with backtest_tab:
    st.subheader("模型回測（滾動樣本外評估）")
    st.caption("每個測試期只使用其之前可見的歷史資料重新訓練融合模型，再以該期實際 6 個正選計算命中數；隨機基準為每期 100 次均勻盲猜的平均命中數。")
    control_a, control_b = st.columns(2)
    with control_a:
        max_training = max(51, min(500, len(draws) - 1))
        default_training = min(200, max_training)
        training_window = st.slider("最少訓練期數", min_value=51, max_value=max_training, value=default_training, step=10)
    with control_b:
        max_test_periods = max(1, min(50, len(draws) - training_window))
        test_periods = st.slider("回測期數", min_value=1, max_value=max_test_periods, value=min(20, max_test_periods), step=1)
    if st.button("執行模型回測", type="primary"):
        with st.spinner("正在逐期重訓並比較 AI 與隨機基準…"):
            backtest, backtest_error = rolling_backtest(draws, training_window=training_window, test_periods=test_periods)
        if backtest_error:
            st.error(backtest_error)
        else:
            st.session_state["backtest_results"] = backtest
            st.session_state["backtest_source"] = source_label

    backtest = st.session_state.get("backtest_results")
    if backtest is not None and st.session_state.get("backtest_source") == source_label:
        average_ai = backtest["AI Top-6 命中"].mean()
        average_random = backtest["隨機平均命中"].mean()
        metric_a, metric_b, metric_c = st.columns(3)
        metric_a.metric("AI 平均命中", f"{average_ai:.3f}")
        metric_b.metric("隨機平均命中", f"{average_random:.3f}")
        metric_c.metric("差異（AI − 隨機）", f"{average_ai - average_random:+.3f}")
        st.bar_chart(backtest.set_index("期數")[["AI Top-6 命中", "隨機平均命中"]])
        st.caption("平均命中差異只描述此歷史樣本與本次設定；公平攪珠下，單次或有限樣本優勢可能只是隨機波動。")
        st.dataframe(backtest, width="stretch", hide_index=True)

with data_tab:
    st.subheader("歷史資料互動篩選")
    start_date = draws["Date"].min().date()
    end_date = draws["Date"].max().date()
    date_range = st.date_input("日期區間", value=(start_date, end_date), min_value=start_date, max_value=end_date)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        selected_start, selected_end = date_range
    else:
        selected_start = selected_end = date_range
    selected_numbers = st.multiselect("包含任一指定號碼（正選或特別號）", options=list(range(1, 50)), format_func=lambda number: f"{number:02d}")
    filtered_history = filter_history(draws, selected_start, selected_end, selected_numbers)
    st.caption(f"篩選結果：{len(filtered_history):,} 期紀錄。")
    st.dataframe(filtered_history, width="stretch", hide_index=True)
    st.markdown("#### CSV 欄位規格")
    st.code(", ".join(REQUIRED_COLUMNS), language=None)
