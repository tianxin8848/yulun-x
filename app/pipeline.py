from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from app.db import SessionLocal, init_db
from app.models import Article, Report, Run
from app.services.analyzer import sentiment, top_keywords
from app.services.deepseek_client import summarize
from app.services.news_fetcher import fetch_news_by_keyword
from app.services.reporter import build_markdown, save_markdown, save_pdf


def run_pipeline(keyword: str, limit: int = 30) -> dict:
    init_db()
    db = SessionLocal()
    try:
        run = Run(keyword=keyword, created_at=datetime.utcnow())
        db.add(run)
        db.flush()

        items = fetch_news_by_keyword(keyword=keyword, max_items=limit)
        texts: list[str] = []
        sentiment_labels: list[str] = []
        saved_articles: list[Article] = []

        for item in items:
            text_for_analysis = f"{item.get('title', '')} {item.get('content', '')}".strip()
            score, label = sentiment(text_for_analysis)
            keys = top_keywords([text_for_analysis], topn=6)
            article = Article(
                run_id=run.id,
                title=item.get("title", ""),
                source=item.get("source", ""),
                source_url=item.get("source_url", ""),
                published_at=item.get("published_at"),
                content=item.get("content", ""),
                sentiment_score=score,
                sentiment_label=label,
                keywords=",".join(keys),
            )
            db.add(article)
            db.flush()
            saved_articles.append(article)
            texts.append(text_for_analysis)
            sentiment_labels.append(label)

        merged_keywords = top_keywords(texts, topn=12)
        sentiment_dist = dict(Counter(sentiment_labels))

        llm_summary = summarize(
            keyword=keyword,
            articles=[{"title": x.title, "content": x.content} for x in saved_articles],
        )
        run.summary = llm_summary

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        md_filename = f"report_{keyword}_{timestamp}.md".replace(" ", "_")
        pdf_filename = f"report_{keyword}_{timestamp}.pdf".replace(" ", "_")
        markdown = build_markdown(
            keyword=keyword,
            run_time=run.created_at,
            summary=llm_summary,
            sentiment_distribution=sentiment_dist,
            top_keywords=merged_keywords,
            article_titles=[x.title for x in saved_articles],
        )
        md_path = save_markdown(markdown, md_filename)
        pdf_path = save_pdf(markdown, pdf_filename)

        report = Report(run_id=run.id, markdown_path=md_path, pdf_path=pdf_path)
        db.add(report)
        db.commit()

        return {
            "run_id": run.id,
            "article_count": len(saved_articles),
            "sentiment_distribution": sentiment_dist,
            "top_keywords": merged_keywords,
            "summary": llm_summary,
            "markdown_path": str(Path(md_path)),
            "pdf_path": str(Path(pdf_path)),
        }
    finally:
        db.close()
