import pytest


@pytest.mark.asyncio
async def test_crawl4ai_renders_local_html():
    crawl4ai = pytest.importorskip(
        "crawl4ai",
        reason="install the tool.web optional dependencies",
    )

    browser_config = crawl4ai.BrowserConfig(headless=True)
    run_config = crawl4ai.CrawlerRunConfig()
    html = "raw://<html><body><h1>Crawl4AI is ready</h1></body></html>"

    async with crawl4ai.AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(html, config=run_config)

    assert result.success
    assert "Crawl4AI is ready" in result.markdown.raw_markdown
