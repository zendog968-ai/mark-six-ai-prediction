import streamlit as st

import altair as alt

from lotto_data import (
    DEFAULT_REAL_HISTORY_PATH,
    REQUIRED_COLUMNS,
    filter_history,
    generate_filtered_combinations,
    read_csv_with_validation,
    rolling_backtest,
    select_special_number,
    select_data_source,
    train_fusion_model,
)
from prediction_tracking import (
    DEFAULT_PREDICTION_HISTORY_PATH,
    build_hit_rate_table,
    hit_rate_metrics,
    load_prediction_history,
)
from blind_test_tracking import (
    DEFAULT_BLIND_TEST_HISTORY_PATH,
    blind_test_metrics,
    build_blind_test_table,
    load_blind_test_history,
)
from brier_dashboard import (
    BASELINE_KEY,
    CONFIG_LABELS,
    DEFAULT_BRIER_TRACKING_PATH,
    build_brier_by_draw,
    brier_coverage_summary,
    cumulative_brier,
    load_brier_tracking,
    load_multiscale_preview,
    run_four_configuration_inference,
)
from weight_monitor import (
    DEFAULT_WEIGHT_HISTORY_PATH,
    build_weight_monitor_state,
    load_weight_adjustment_history,
)
from long_window_research import (
    build_long_window_research_state,
    canonical_family_name,
    family_display_name,
    filter_long_window_research,
    localize_long_window_research,
    research_copy,
)
from ui_preferences import (
    language_code_from_label,
    language_label_from_code,
    load_window_research_language,
    save_window_research_language,
)
from smtp_notifications import build_daily_status_snapshot, render_daily_status_body, render_daily_status_html


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
overview_tab, model_tab, backtest_tab, hit_rate_tab, blind_test_tab, inference_tab, weight_tab, data_tab, window_research_tab, email_preview_tab = st.tabs(
    ["資料概覽", "模型實驗", "模型回測", "命中率與回測分析", "三配置盲測追蹤", "Brier 統計檢定", "權重演變與凍結", "歷史資料預覽", "5／10期窗口研究", "HTML 每日報告預覽"]
)

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
            if index == 1:
                special_number = select_special_number(ranked_probabilities, combination)
                st.write(
                    f"6+1 推薦組合：{' · '.join(f'{number:02d}' for number in combination)} "
                    f"+ [特別號碼：{special_number:02d}]　|　{odd_count} 單 / {6 - odd_count} 雙　|　總和 {sum(combination)}"
                )
            else:
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

with hit_rate_tab:
    st.subheader("命中率與回測分析")
    st.caption("每次模型對下一期產生的 5 組實驗性組合會保存至版本控制紀錄；只有在該目標期有實際六個正選結果後，才會計入命中率指標。✅ 代表該組合與實際正選的交集。")
    prediction_records = load_prediction_history(DEFAULT_PREDICTION_HISTORY_PATH)
    hit_table, history_validation = build_hit_rate_table(draws, prediction_records)
    if history_validation is not None:
        st.error("無法比對預測紀錄，因目前資料來源未通過驗證。")
        for error in history_validation.errors:
            st.error(error)
    elif hit_table.empty:
        st.info("目前沒有已保存的預測紀錄。下一次日常更新建立下一期組合時，系統會自動開始追蹤。")
    else:
        metrics = hit_rate_metrics(hit_table)
        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        metric_a.metric("已結算期數", metrics["settled_draws"])
        metric_b.metric("待攪珠紀錄", metrics["pending_draws"])
        metric_c.metric("平均每期最高命中", f"{metrics['average_best_hits']:.2f}")
        metric_d.metric("命中 3 個字或以上", metrics["draws_with_3_plus"])
        st.caption(f"已結算期的五組合計平均命中數：{metrics['average_total_hits']:.2f}。這些數字只用作歷史追蹤與模型參數調整，不代表未來中獎率。")

        def highlight_hit_cell(value):
            return "background-color: #dcfce7; color: #166534; font-weight: 600; white-space: pre-line;" if "✅" in str(value) else "white-space: pre-line;"

        def highlight_status(value):
            if value == "已結算":
                return "background-color: #ecfdf5; color: #166534; font-weight: 600;"
            return "background-color: #fffbeb; color: #92400e; font-weight: 600;"

        display_columns = [
            "期數",
            "目標日期",
            "實際日期",
            "狀態",
            "實際開獎號碼",
            "特別號",
            "AI 預測 5 組組合",
            "命中號碼",
            "單期最高命中",
            "五組合計命中",
            "每組命中數",
        ]
        styled_table = (
            hit_table.loc[:, display_columns]
            .style.map(highlight_hit_cell, subset=["命中號碼"])
            .map(highlight_status, subset=["狀態"])
        )
        st.dataframe(styled_table, width="stretch", hide_index=True, height=min(720, 120 + 58 * len(hit_table)))

with blind_test_tab:
    st.subheader("三配置盲測追蹤")
    st.caption("每期會在上一期結果更新後，預先鎖定融合基準、50% frequency_50 變體與熱門 6 三種候選。鎖定紀錄包含雜湊；同一期不會被重跑覆寫，只有實際正選結果出現後才結算。")
    blind_records = load_blind_test_history(DEFAULT_BLIND_TEST_HISTORY_PATH)
    blind_table, blind_validation = build_blind_test_table(draws, blind_records)
    if blind_validation is not None:
        st.error("無法比對盲測紀錄，因目前資料來源未通過驗證。")
        for error in blind_validation.errors:
            st.error(error)
    elif blind_table.empty:
        st.info("尚未建立盲測紀錄。下一次日常更新建立下一個未結算期的候選後，系統會自動開始鎖定。")
    else:
        blind_metrics = blind_test_metrics(blind_table)
        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        metric_a.metric("已鎖定目標期", blind_metrics["locked_records"])
        metric_b.metric("已結算目標期", blind_metrics["settled_records"])
        metric_c.metric("已結算配置", blind_metrics["settled_variants"])
        metric_d.metric("已結算配置平均命中", f"{blind_metrics['average_hits']:.2f}")
        st.caption(f"命中 3 個字或以上的已結算配置：{blind_metrics['three_plus']}。盲測樣本累積不足時不可推論模型優勢。")

        def highlight_blind_hits(value):
            return "background-color: #dcfce7; color: #166534; font-weight: 600;" if "✅" in str(value) else ""

        def highlight_blind_status(value):
            return "background-color: #ecfdf5; color: #166534; font-weight: 600;" if value == "已結算" else "background-color: #fffbeb; color: #92400e; font-weight: 600;"

        styled_blind_table = (
            blind_table.style
            .map(highlight_blind_hits, subset=["命中號碼"])
            .map(highlight_blind_status, subset=["狀態"])
        )
        st.dataframe(styled_blind_table, width="stretch", hide_index=True, height=min(680, 120 + 46 * len(blind_table)))

with inference_tab:
    st.subheader("四配置 Brier 統計檢定儀表板")
    st.caption("此頁只使用開獎前鎖定的完整 49 號機率向量與其後的實際六個正選。舊有三配置紀錄只保存了 Top-6 號碼，不能被追溯轉換為機率或 Brier 分數。")
    brier_records = load_brier_tracking(DEFAULT_BRIER_TRACKING_PATH)
    brier_frame, brier_warnings = build_brier_by_draw(brier_records, draws)
    multiscale_preview = load_multiscale_preview()
    coverage = brier_coverage_summary(brier_frame, len(blind_records), multiscale_preview, len(brier_records))
    coverage_a, coverage_b, coverage_c = st.columns(3)
    coverage_a.metric("共同已結算完整機率期數", len(brier_frame))
    coverage_b.metric("正式顯著性門檻", "100 期")
    coverage_c.metric("第四配置狀態", "研究預覽" if multiscale_preview is not None else "尚未鎖定")
    st.dataframe(coverage, width="stretch", hide_index=True)

    if multiscale_preview is not None:
        top6 = multiscale_preview.get("top_6_numbers", [])
        target = multiscale_preview.get("target", {})
        st.info(
            f"研究預覽：目標期 {target.get('draw', '—')}，Top-6 為 "
            f"{' · '.join(f'{int(number):02d}' for number in sorted(top6)) if top6 else '—'}。"
            "此紀錄尚未加入正式四配置盲測，故不會計入 Brier 或檢定。"
        )

    if brier_warnings:
        with st.expander("資料完整性提示"):
            for warning in brier_warnings:
                st.warning(warning)

    if brier_frame.empty:
        st.info("目前尚無共同已結算的四配置完整機率紀錄，因此沒有可視覺化的長期 Brier 走勢或可執行的檢定。當未來每期在開獎前鎖定四組完整機率並在結果寫入後結算，此頁會自動開始累積。")
    else:
        if len(brier_frame) == 1:
            visible_periods = 1
            st.caption("目前只有 1 期共同已結算完整機率紀錄，因此顯示全部可用資料。")
        else:
            visible_periods = st.slider("顯示最近共同已結算期數", min_value=1, max_value=len(brier_frame), value=len(brier_frame))
        visible = brier_frame.tail(visible_periods).copy()
        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        for metric, key in zip((metric_a, metric_b, metric_c, metric_d), CONFIG_LABELS, strict=True):
            metric.metric(CONFIG_LABELS[key], f"{visible[key].mean():.6f}")
        chart = cumulative_brier(visible).pivot(index="期數", columns="配置", values="累積平均 Brier")
        st.line_chart(chart)
        st.dataframe(visible.rename(columns=CONFIG_LABELS), width="stretch", hide_index=True)

        if len(visible) < 2:
            st.info("共同已結算完整機率紀錄不足 2 期，暫不執行 Bootstrap 或 Diebold–Mariano 比較。系統會在後續期數自動累積研究樣本。")
        else:
            max_block = min(10, len(visible))
            controls_a, controls_b = st.columns(2)
            with controls_a:
                block_length = st.slider("Bootstrap 區塊長度", min_value=1, max_value=max_block, value=min(5, max_block))
            with controls_b:
                bootstrap_runs = st.select_slider("Bootstrap 重抽次數", options=[500, 1_000, 2_000, 5_000], value=2_000)
            inference, inference_error = run_four_configuration_inference(visible, block_length=block_length, n_bootstrap=bootstrap_runs)
            if inference_error:
                st.info(inference_error)
            else:
                display = inference.loc[:, [
                    "配置", "candidate_mean_brier", "baseline_mean_brier", "mean_difference", "ci95_lower", "ci95_upper",
                    "brier_skill_score_vs_baseline", "bootstrap_p_value_holm", "dm_dm_statistic", "dm_p_value_holm",
                    "inference_methods_agree", "both_methods_support_candidate",
                ]].rename(columns={
                    "candidate_mean_brier": "候選平均 Brier", "baseline_mean_brier": "基準平均 Brier", "mean_difference": "平均差（候選−基準）",
                    "ci95_lower": "Bootstrap 95% CI 下界", "ci95_upper": "Bootstrap 95% CI 上界", "brier_skill_score_vs_baseline": "Brier Skill Score",
                    "bootstrap_p_value_holm": "Bootstrap Holm p", "dm_dm_statistic": "DM 統計量", "dm_p_value_holm": "DM Holm p",
                    "inference_methods_agree": "兩方法拒絕結論一致", "both_methods_support_candidate": "雙方法支持候選",
                })
                st.dataframe(display, width="stretch", hide_index=True)
                st.caption("Bootstrap 是主要推論，Diebold–Mariano 是敏感度／交叉驗證。四配置共同已結算期數少於 100 時，所有結果均只屬描述性與探索性，不可宣稱長期優勢。")

with weight_tab:
    st.subheader("受約束 Brier 權重演變與 50 期凍結監控")
    st.caption("本頁只展示已鎖定的權重版本。新的權重必須先通過 100 期共同盲測、Bootstrap、Diebold–Mariano、Holm 與效應量資格閘門，才可產生候選；候選權重再以 α = 0.25 平滑過渡並凍結 50 個未來期數。")
    weight_history = load_weight_adjustment_history(DEFAULT_WEIGHT_HISTORY_PATH)
    weight_state = build_weight_monitor_state(brier_frame, weight_history)
    weight_a, weight_b, weight_c, weight_d = st.columns(4)
    weight_a.metric("共同已結算期數", weight_state["completed_common_draws"])
    weight_b.metric("距離首次正式檢定", f"{weight_state['next_gate_remaining']} 期")
    weight_c.metric("目前權重版本", weight_state["active_version"])
    weight_d.metric("50 期凍結確認", f"{weight_state['freeze_completed_draws']}/{weight_state['freeze_confirmation_draws']}")
    st.dataframe(weight_state["gate_rows"], width="stretch", hide_index=True)
    st.markdown("#### 目前鎖定權重")
    current_weights = weight_state["weight_rows"].set_index("配置")["目前權重"]
    st.bar_chart(current_weights)
    st.dataframe(
        weight_state["weight_rows"].assign(目前權重=lambda table: table["目前權重"].map(lambda value: f"{value:.1%}")),
        width="stretch",
        hide_index=True,
    )
    if weight_state["history"].empty:
        st.info("目前仍在共同盲測累積期；尚未產生任何通過資格閘門的候選權重版本，因此不存在可凍結或可視覺化的權重變動。系統維持 25%／25%／25%／25% 的觀察期參照，不會自行調整。")
    else:
        st.markdown("#### 已鎖定權重版本歷史")
        history = weight_state["history"].copy()
        st.line_chart(history.set_index("版本")[[label for label in CONFIG_LABELS.values()]])
        st.dataframe(history, width="stretch", hide_index=True)
    st.caption("權重調整只是一種受約束的機率預報組合研究，並不代表可預測獨立隨機攪珠結果，也不構成投注建議。")

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

with window_research_tab:
    language_widget_key = "window_research_language_choice"
    if language_widget_key not in st.session_state:
        st.session_state[language_widget_key] = language_label_from_code(load_window_research_language())

    def persist_window_research_language() -> None:
        saved_language = language_code_from_label(st.session_state[language_widget_key])
        save_window_research_language(saved_language)
        st.session_state["window_research_language_saved"] = saved_language

    language_choice = st.selectbox(
        "Language / 語言",
        options=["繁體中文", "English"],
        key=language_widget_key,
        on_change=persist_window_research_language,
        help="This selector changes only the 5/10-draw window research view and remembers the last selection on this dashboard.",
    )
    language = language_code_from_label(language_choice)
    saved_language = st.session_state.pop("window_research_language_saved", None)
    if saved_language == "en":
        st.toast("Language preference saved: English", icon="✅", duration="long")
    elif saved_language == "zh":
        st.toast("已儲存語言偏好：繁體中文", icon="✅", duration="long")
    copy = research_copy(language)
    field = {
        "family": "Combination family" if language == "en" else "組合家族",
        "series": "Data series" if language == "en" else "數據系列",
        "draws": "Draws" if language == "en" else "期數",
        "observed_draws": "Observed draws" if language == "en" else "實際出現期數",
        "expected_draws": "Random expected draws" if language == "en" else "隨機期望期數",
        "frequency_deviation": "Frequency deviation" if language == "en" else "頻率偏離",
        "baseline_probability": "Baseline probability" if language == "en" else "基準機率",
        "frequency_raw_p": "Frequency raw p" if language == "en" else "總頻率原始 p",
        "frequency_holm_p": "Frequency Holm p" if language == "en" else "總頻率 Holm p",
        "frequency_holm_status": "Frequency Holm status" if language == "en" else "總頻率 Holm 狀態",
        "pattern": "Candidate pattern" if language == "en" else "候選模式",
        "window": "Window" if language == "en" else "窗口",
        "score": "Score" if language == "en" else "分數",
        "observed_score": "Observed window score" if language == "en" else "實際窗口分數",
        "expected_score": "Random expected score" if language == "en" else "隨機期望分數",
        "window_deviation": "Window deviation" if language == "en" else "窗口偏離",
        "direction": "Direction" if language == "en" else "方向",
        "window_raw_p": "Window raw p" if language == "en" else "窗口原始 p",
        "window_holm_p": "Window Holm p" if language == "en" else "窗口 Holm p",
        "window_holm_status": "Window Holm status" if language == "en" else "窗口 Holm 狀態",
    }
    st.subheader(copy["title"])
    st.caption(copy["intro"])
    research = build_long_window_research_state()
    if not research["available"]:
        st.warning(research["message"] if language == "zh" else "No verifiable 5/10-draw window-research snapshot was found.")
    else:
        canonical_options = research["family_table"]["組合家族"].tolist()
        family_options = [family_display_name(family, language) for family in canonical_options]
        selected_family_labels = st.multiselect(
            copy["family_filter"],
            options=family_options,
            default=family_options,
            help=copy["family_filter_help"],
        )
        selected_families = [canonical_family_name(label, language) for label in selected_family_labels]
        research = filter_long_window_research(research, selected_families)
        research = localize_long_window_research(research, language)
        start_date, end_date = research["date_range"]
        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        draw_unit = "draws" if language == "en" else "期"
        metric_a.metric(copy["sample"], f"{research['draw_count']:,} {draw_unit}")
        metric_b.metric(copy["tests"], f"{research['total_tests']:,}")
        metric_c.metric(copy["five_signals"], research["initial_signals"]["5"])
        metric_d.metric(copy["holdout_passed"], f"{research['passed_holdout']}/10")
        if not selected_families:
            st.info(copy["no_families"])
        else:
            st.info(copy["range"].format(start=start_date, end=end_date, holdout=research["holdout_draws"]))

        st.markdown(f"#### {copy['summary_title']}")
        summary_table, summary_charts = st.columns([1.55, 1])
        with summary_table:
            st.dataframe(research["family_table"], width="stretch", hide_index=True, height=260)
        with summary_charts:
            st.caption(f"**{copy['signal_holdout_title']}**")
            st.bar_chart(research["window_signal_chart"], height=230)
            st.caption(copy["signal_holdout_caption"])

        st.markdown(f"#### {copy['frequency_title']}")
        frequency_chart = (
            alt.Chart(research["frequency_tooltip_chart"])
            .mark_bar()
            .encode(
                x=alt.X(f"{field['family']}:N", sort=None, title=None),
                xOffset=f"{field['series']}:N",
                y=alt.Y(f"{field['draws']}:Q", title=field["draws"]),
                color=alt.Color(f"{field['series']}:N", title=field["series"]),
                tooltip=[
                    alt.Tooltip(f"{field['family']}:N"),
                    alt.Tooltip(f"{field['pattern']}:N"),
                    alt.Tooltip(f"{field['series']}:N"),
                    alt.Tooltip(f"{field['draws']}:Q", format=".2f"),
                    alt.Tooltip(f"{field['observed_draws']}:Q", format=".2f"),
                    alt.Tooltip(f"{field['expected_draws']}:Q", format=".2f"),
                    alt.Tooltip(f"{field['frequency_deviation']}:Q", format="+.2f"),
                    alt.Tooltip(f"{field['baseline_probability']}:Q", format=".4%"),
                    alt.Tooltip(f"{field['frequency_raw_p']}:Q", format=".4f"),
                    alt.Tooltip(f"{field['frequency_holm_p']}:Q", format=".4f"),
                    alt.Tooltip(f"{field['frequency_holm_status']}:N"),
                ],
            )
            .properties(height=280)
            .interactive()
        )
        st.altair_chart(frequency_chart, width="stretch")
        st.caption(copy["frequency_caption"])

        st.markdown(f"#### {copy['window_title']}")
        window_sort = ["5 draws", "10 draws"] if language == "en" else ["5 期", "10 期"]
        window_trend_chart = (
            alt.Chart(research["window_tooltip_chart"])
            .mark_line(point=True)
            .encode(
                x=alt.X(f"{field['window']}:O", sort=window_sort, title=field["window"]),
                y=alt.Y(f"{field['score']}:Q", title=field["score"]),
                color=alt.Color(f"{field['series']}:N", title=field["series"]),
                detail=[alt.Detail(f"{field['family']}:N"), alt.Detail(f"{field['series']}:N")],
                strokeDash=alt.StrokeDash(f"{field['family']}:N", title=field["family"]),
                tooltip=[
                    alt.Tooltip(f"{field['family']}:N"),
                    alt.Tooltip(f"{field['pattern']}:N"),
                    alt.Tooltip(f"{field['window']}:N"),
                    alt.Tooltip(f"{field['series']}:N"),
                    alt.Tooltip(f"{field['score']}:Q", format=".2f"),
                    alt.Tooltip(f"{field['observed_score']}:Q", format=".2f"),
                    alt.Tooltip(f"{field['expected_score']}:Q", format=".2f"),
                    alt.Tooltip(f"{field['window_deviation']}:Q", format="+.2f"),
                    alt.Tooltip(f"{field['direction']}:N"),
                    alt.Tooltip(f"{field['window_raw_p']}:Q", format=".4f"),
                    alt.Tooltip(f"{field['window_holm_p']}:Q", format=".4f"),
                    alt.Tooltip(f"{field['window_holm_status']}:N"),
                ],
            )
            .properties(height=320)
            .interactive()
        )
        st.altair_chart(window_trend_chart, width="stretch")
        st.caption(copy["window_caption"])

        st.markdown(f"#### {copy['holdout_title']}")
        st.caption(copy["holdout_caption"].format(training=research["training_draws"], holdout=research["holdout_draws"]))
        holdout_table, holdout_chart = st.columns([1.55, 1])
        with holdout_table:
            st.dataframe(research["holdout_table"], width="stretch", hide_index=True, height=380)
        with holdout_chart:
            st.caption(f"**{copy['flow_title']}**")
            st.bar_chart(research["holdout_flow_chart"], height=240)
            st.caption(copy["flow_caption"])

        with st.expander(copy["methods_title"]):
            st.markdown(copy["methods_text"])

with email_preview_tab:
    st.subheader("HTML 每日報告預覽")
    st.caption("此頁以排程每日 Email 相同的唯讀快照渲染，只供預覽；不會寄送 Email、更新開獎資料或改寫任何盲測、Brier、權重帳本。")
    report_snapshot = build_daily_status_snapshot()
    blind_summary = report_snapshot.get("recent_blind_hit_summary") or {}
    latest_report_prediction = report_snapshot.get("latest_prediction") or {}
    preview_recommendations = latest_report_prediction.get("top_5_recommendations", []) if isinstance(latest_report_prediction, dict) else []
    preview_a, preview_b, preview_c = st.columns(3)
    preview_a.metric("近期已結算盲測期數", blind_summary.get("settled_draws", 0))
    preview_b.metric("近期平均最高命中", f"{float(blind_summary.get('average_best_hits', 0.0)):.2f}/6")
    first_strength_value = "未提供"
    if preview_recommendations and isinstance(preview_recommendations[0], dict):
        relative_strength = preview_recommendations[0].get("relative_strength_percent")
        try:
            first_strength_value = f"{int(relative_strength)}%"
        except (TypeError, ValueError):
            pass
    preview_c.metric("第一組相對強度", first_strength_value)
    st.components.v1.html(render_daily_status_html(report_snapshot), height=1260, scrolling=True)
    with st.expander("檢視純文字後備內容"):
        st.code(render_daily_status_body(report_snapshot), language=None)
