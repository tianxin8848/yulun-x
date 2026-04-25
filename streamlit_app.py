import pandas as pd
import plotly.express as px
import streamlit as st

from app.pipeline import run_pipeline
from app.services.deepseek_client import generate_leadership_report_from_grok
from app.services.grok_records import fetch_grok_chat_records, fetch_grok_records_by_ids

st.set_page_config(page_title="舆情分析系统", layout="wide")
st.title("舆情获取 + 分析系统（Python + PostgreSQL）")

tab_news, tab_grok = st.tabs(["关键词新闻舆情", "Grok 对话 → 领导报告"])

with tab_news:
    st.caption("输入关键词，一键采集新闻、做情感分析，并生成 Markdown + PDF 报告。")
    keyword = st.text_input("关键词", value="香港AI新闻", key="kw")
    limit = st.slider("采集条数", min_value=10, max_value=100, value=30, step=10, key="lim")

    if st.button("生成今日报告", type="primary", key="btn_news"):
        with st.spinner("正在采集、分析并生成报告..."):
            result = run_pipeline(keyword=keyword, limit=limit)

        st.success(f"完成，保存 {result['article_count']} 条资讯。")
        if result["article_count"] == 0:
            st.warning("当前关键词未抓到新闻，建议改为更短关键词（如“香港 AI”）后重试。")
        st.write("### 智能总结")
        st.write(result["summary"])

        dist = result["sentiment_distribution"]
        dist_df = pd.DataFrame(
            [
                {"label": "positive", "count": dist.get("positive", 0)},
                {"label": "neutral", "count": dist.get("neutral", 0)},
                {"label": "negative", "count": dist.get("negative", 0)},
            ]
        )
        fig = px.pie(dist_df, values="count", names="label", title="情感分布")
        st.plotly_chart(fig, use_container_width=True)

        st.write("### 高频关键词")
        st.write(", ".join(result["top_keywords"]) if result["top_keywords"] else "无")

        st.write("### 报告文件")
        st.code(f"Markdown: {result['markdown_path']}\nPDF: {result['pdf_path']}")

with tab_grok:
    st.caption(
        "数据来自数据库表 **grok_chat_records**（Tampermonkey 采集的 Grok 问答）。"
        "勾选若干条后，将 **问题 + 回答** 与采集时间、来源链接一并交给 DeepSeek，"
        "生成面向中国领导的参阅报告（强调时间、地点、信息来源，不编造材料外内容）。"
    )
    load_limit = st.number_input("最多加载条数", min_value=20, max_value=1000, value=300, step=20)

    if st.button("从数据库刷新列表", key="btn_reload_grok"):
        st.session_state.pop("grok_df", None)

    if "grok_df" not in st.session_state:
        records = fetch_grok_chat_records(limit=max(1, int(load_limit)))
        if not records:
            st.warning(
                "未读到 **grok_chat_records** 数据（表不存在、库未连上或表为空）。"
                "请确认已执行 `scripts/grok_chat_records.sql` 且 Tampermonkey 已写入记录。"
            )
        else:
            st.session_state["grok_df"] = pd.DataFrame(records)

    if "grok_df" in st.session_state and not st.session_state["grok_df"].empty:
        df = st.session_state["grok_df"].copy()
        if "选择" not in df.columns:
            df.insert(0, "选择", False)

        st.write("### 对话列表（勾选要纳入报告的行）")
        edited = st.data_editor(
            df,
            column_config={
                "选择": st.column_config.CheckboxColumn("纳入报告", default=False),
                "question": st.column_config.TextColumn("问题", width="large"),
                "answer": st.column_config.TextColumn("回答", width="large"),
                "page_url": st.column_config.LinkColumn("信息来源链接"),
                "captured_at": st.column_config.TextColumn("采集时间(UTC)"),
            },
            disabled=[c for c in df.columns if c != "选择"],
            hide_index=True,
            use_container_width=True,
            height=420,
            key="grok_editor",
        )

        selected_ids = edited.loc[edited["选择"] == True, "id"].astype(int).tolist()

        col_a, col_b = st.columns(2)
        with col_a:
            gen = st.button("生成领导参阅报告（DeepSeek）", type="primary", key="btn_lead_report")
        with col_b:
            if st.button("仅预览已选条数", key="btn_count"):
                st.info(f"当前已选 **{len(selected_ids)}** 条。")

        if gen:
            if not selected_ids:
                st.error("请至少勾选一条记录。")
            else:
                full_rows = fetch_grok_records_by_ids(selected_ids)
                if not full_rows:
                    st.error("按 ID 重新查询失败，请检查数据库连接。")
                else:
                    with st.spinner("正在调用 DeepSeek 生成报告（可能需数十秒）…"):
                        report = generate_leadership_report_from_grok(full_rows)
                    st.write("### 领导参阅报告")
                    st.markdown(report)
                    st.download_button(
                        label="下载为 Markdown",
                        data=report.encode("utf-8"),
                        file_name="leadership_report_grok.md",
                        mime="text/markdown",
                        key="dl_report",
                    )
