import pandas as pd
import plotly.express as px
import streamlit as st

from app.pipeline import run_pipeline

st.set_page_config(page_title="舆情分析系统", layout="wide")
st.title("舆情获取 + 分析系统（Python + PostgreSQL）")
st.caption("输入关键词，一键采集新闻、做情感分析，并生成 Markdown + PDF 报告。")

keyword = st.text_input("关键词", value="香港AI新闻")
limit = st.slider("采集条数", min_value=10, max_value=100, value=30, step=10)

if st.button("生成今日报告", type="primary"):
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
