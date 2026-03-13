from src.analyzer import AnalysisResult
from src.formatters import (
    chunk_content_by_max_bytes,
    chunk_content_by_max_words,
    markdown_to_plain_text,
    slice_at_max_bytes,
)
from src.notification import NotificationService


def test_slice_at_max_bytes_preserves_utf8():
    first, second = slice_at_max_bytes("贵州茅台ABC", 7)
    assert first
    assert first.encode("utf-8")
    assert second
    assert first + second == "贵州茅台ABC"


def test_chunk_content_by_max_bytes_splits_large_content():
    content = "## 标题\n\n" + ("内容段落\n" * 200)
    chunks = chunk_content_by_max_bytes(content, 300, add_page_marker=True)
    assert len(chunks) > 1
    assert any("📄" in chunk for chunk in chunks)


def test_chunk_content_by_max_words_splits_large_content():
    content = "### 小节\n" + ("测试内容 " * 300)
    chunks = chunk_content_by_max_words(content, 120)
    assert len(chunks) > 1


def test_markdown_to_plain_text_removes_markup():
    text = markdown_to_plain_text("# 标题\n\n**加粗**\n\n- 项目")
    assert "标题" in text
    assert "加粗" in text
    assert "项目" in text


def test_generate_single_stock_report_matches_jarvis_style():
    notifier = NotificationService()
    result = AnalysisResult(
        code="600519",
        name="贵州茅台",
        sentiment_score=65,
        trend_prediction="看多",
        operation_advice="观望",
        decision_type="hold",
        analysis_summary="当前处于高位震荡，等待更清晰的回踩买点。",
        dashboard={
            "core_conclusion": {
                "one_sentence": "等待回踩确认后再考虑介入。",
            },
            "intelligence": {
                "sentiment_summary": "市场情绪偏中性，等待催化。",
                "earnings_outlook": "短期业绩预期稳定，没有明显下修迹象。",
                "risk_alerts": ["短线波动较大，追高风险偏高。"],
                "positive_catalysts": ["消费白马配置需求仍在。"],
                "latest_news": "暂无重大利空，板块关注度维持稳定。",
            },
        },
    )

    content = notifier.generate_single_stock_report(result)
    assert "Jarvis Daily Investment Advice" in content
    assert "🎯" in content
    assert "共分析1只股票" in content
    assert "📊 分析结果摘要" in content
    assert "📰 重要信息速览" in content
    assert "🚨 风险警报" in content
    assert "✨ 利好催化" in content
    assert "📢 最新动态" in content
