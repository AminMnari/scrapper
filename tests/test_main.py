"""Tests for main orchestration module."""

from unittest.mock import MagicMock, patch

import main
from validators import Product


class TestRunRouting:
    @patch("main.detect_content_type", return_value="ecommerce")
    @patch("main.detect_platform", return_value=("shopify", "<html></html>"))
    @patch("main.scrape_shopify")
    def test_run_routes_shopify(self, mock_shopify, _mock_detect, _mock_content):
        mock_shopify.return_value = [Product(name="A", price="1")]

        items, platform, content_type = main.run(
            "https://example.com/collections/all", max_pages=2
        )

        assert len(items) == 1
        assert platform == "shopify"
        assert content_type == "ecommerce"
        mock_shopify.assert_called_once_with("https://example.com/collections/all", max_pages=2)

    @patch("main.detect_content_type", return_value="ecommerce")
    @patch("main.detect_platform", return_value=("woocommerce", "<html></html>"))
    @patch("main.scrape_woocommerce")
    @patch("main.scrape_with_selenium")
    def test_run_woocommerce_uses_api_when_available(self, mock_selenium, mock_woo, _mock_detect, _mock_content):
        mock_woo.return_value = [Product(name="W", price="2")]

        items, platform, _content_type = main.run("https://example.com", max_pages=1)

        assert len(items) == 1
        assert platform == "woocommerce"
        mock_selenium.assert_not_called()

    @patch("main.detect_content_type", return_value="ecommerce")
    @patch("main.detect_platform", return_value=("woocommerce", "<html></html>"))
    @patch("main.scrape_woocommerce", return_value=None)
    @patch("main.scrape_with_selenium", return_value=[{"name": "Fallback", "price": "3"}])
    def test_run_woocommerce_falls_back_to_selenium(self, mock_selenium, _mock_woo, _mock_detect, _mock_content):
        items, platform, _content_type = main.run("https://example.com", max_pages=3)

        assert len(items) == 1
        assert items[0]["name"] == "Fallback"
        assert platform == "woocommerce"
        mock_selenium.assert_called_once_with("https://example.com", max_pages=3, field_hints=None)

    @patch("main.detect_content_type", return_value="unknown")
    @patch("main.detect_platform", return_value=("react_spa", "<html></html>"))
    @patch("main.setup_driver")
    @patch("main.scrape_spa")
    @patch("main.scrape_with_selenium")
    def test_run_react_spa_uses_spa_scraper(self, mock_selenium, mock_spa, mock_setup_driver, _mock_detect, _mock_content):
        driver = MagicMock()
        mock_setup_driver.return_value = driver
        mock_spa.return_value = [{"title": "SPA"}]
        mock_selenium.return_value = []

        items, platform, _content_type = main.run("https://example.com/spa", max_pages=2)

        assert len(items) == 1
        assert items[0]["title"] == "SPA"
        assert platform == "react_spa"
        mock_selenium.assert_not_called()
        driver.quit.assert_called_once()

    @patch("main.detect_content_type", return_value="unknown")
    @patch("main.detect_platform", return_value=("react_spa", "<html></html>"))
    @patch("main.setup_driver")
    @patch("main.scrape_spa", return_value=[])
    @patch("main.scrape_with_selenium", return_value=[{"title": "DOM fallback"}])
    def test_run_react_spa_falls_back_dom_scrape(self, mock_selenium, _mock_spa, mock_setup_driver, _mock_detect, _mock_content):
        driver = MagicMock()
        mock_setup_driver.return_value = driver

        items, platform, _content_type = main.run("https://example.com/spa", max_pages=2)

        assert len(items) == 1
        assert items[0]["title"] == "DOM fallback"
        assert platform == "react_spa"
        mock_selenium.assert_called_once_with(
            "https://example.com/spa", max_pages=2, existing_driver=driver, field_hints=None
        )
        driver.quit.assert_called_once()

    @patch("main.detect_content_type", return_value="unknown")
    @patch("main.detect_platform", return_value=("prestashop", "<html></html>"))
    @patch("main.scrape_wordpress", return_value=None)
    @patch("main.scrape_ghost", return_value=None)
    @patch("main.scrape_with_selenium", return_value=[{"name": "P"}])
    def test_run_other_platforms_use_selenium(self, mock_selenium, _mock_ghost, _mock_wp, _mock_detect, _mock_content):
        items, platform, _content_type = main.run("https://example.com/p", max_pages=1)

        assert len(items) == 1
        assert platform == "prestashop"
        mock_selenium.assert_called_once_with("https://example.com/p", max_pages=1, field_hints=None)

    @patch("main.detect_content_type", return_value="news")
    @patch("main.detect_platform", return_value=("unknown", "<html></html>"))
    @patch("main.scrape_wordpress", return_value=[{"title": "post"}])
    @patch("main.scrape_ghost", return_value=None)
    @patch("main.scrape_with_selenium", return_value=[])
    def test_run_prefers_wordpress_api_when_available(
        self, mock_selenium, _mock_ghost, _mock_wp, _mock_detect, _mock_content
    ):
        items, platform, _content_type = main.run("https://example.com", max_pages=1)

        assert platform == "wordpress"
        assert items == [{"title": "post"}]
        mock_selenium.assert_not_called()

    @patch("main.detect_content_type", return_value="news")
    @patch("main.detect_platform", return_value=("unknown", "<html></html>"))
    @patch("main.scrape_wordpress", return_value=None)
    @patch("main.scrape_ghost", return_value=[{"title": "ghost-post"}])
    @patch("main.scrape_with_selenium", return_value=[])
    def test_run_uses_ghost_if_wordpress_unavailable(
        self, mock_selenium, _mock_ghost, _mock_wp, _mock_detect, _mock_content
    ):
        items, platform, _content_type = main.run("https://example.com", max_pages=1)

        assert platform == "ghost"
        assert items == [{"title": "ghost-post"}]
        mock_selenium.assert_not_called()

    @patch("main.detect_platform", side_effect=Exception("detect failed"))
    def test_run_returns_empty_on_detect_error(self, _mock_detect):
        result = main.run("https://example.com", max_pages=1)
        assert result == ([], "unknown", "unknown")


class TestSaveAndPreview:
    @patch("main.json.dump")
    @patch("builtins.open")
    def test_save_serializes_payload(self, mock_open, mock_dump):
        payload = {
            "url": "https://example.com",
            "platform": "wordpress",
            "content_type": "news",
            "detected_fields": ["title"],
            "items": [{"title": "A"}],
        }

        main.save(payload, filename="x.json")

        mock_open.assert_called_once_with("x.json", "w", encoding="utf-8")
        args, _kwargs = mock_dump.call_args
        assert args[0]["items"][0]["title"] == "A"

    @patch("main.print")
    def test_preview_prints_items(self, mock_print):
        items = [
            {"title": "Keyboard", "price": "99.90", "currency": "TND"},
            {"title": "Mouse", "price": "49.90", "currency": "TND"},
        ]

        main.preview(items, n=1, fields=["title", "price"])

        assert mock_print.call_count >= 2

    @patch("main.logger.warning")
    def test_preview_empty_list_logs_warning(self, mock_warning):
        main.preview([], n=3)
        mock_warning.assert_called_once()


class TestJobsNormalization:
    def test_infer_content_type_jobs_from_items(self):
        items = [
            {"title": "QA Engineer", "company": "Acme", "location": "Tunis"},
            {"title": "Data Analyst", "company": "Beta", "location": "Sousse"},
            {"company": "Gamma", "location": "Sfax"},
        ]

        assert main._infer_content_type_from_items(items, "unknown") == "jobs"

    def test_normalize_job_items_filters_and_deduplicates_fragments(self):
        raw_items = [
            {
                "title": "Collaborateur Comptable",
                "company": "BOOST SERVICES -",
                "location": "Tunis",
                "salary": "2,",
            },
            {"company": "BOOST SERVICES -", "location": "Tunis", "salary": "2,"},
            {"salary": "01"},
            {
                "title": "Ingénieur en Chimie",
                "company": "SGS Tunisie -",
                "location": "Tunis",
                "salary": "1878,",
            },
            {"company": "SGS Tunisie -", "location": "Tunis"},
            {"salary": "1878,"},
        ]

        normalized = main._normalize_job_items(raw_items)

        assert len(normalized) == 2
        assert normalized[0]["title"] == "Collaborateur Comptable"
        assert normalized[0]["company"] == "BOOST SERVICES"
        assert "salary" not in normalized[0]

        assert normalized[1]["title"] == "Ingénieur en Chimie"
        assert normalized[1]["company"] == "SGS Tunisie"
        assert normalized[1]["salary"] == "1878"

    @patch("main.detect_content_type", return_value="unknown")
    @patch("main.detect_platform", return_value=("unknown", "<html></html>"))
    @patch("main.scrape_wordpress", return_value=None)
    @patch("main.scrape_ghost", return_value=None)
    @patch(
        "main.scrape_with_selenium",
        return_value=[
            {"title": "DevOps Engineer", "company": "ACME -", "location": "Tunis", "salary": "01"},
            {"company": "ACME -", "location": "Tunis"},
            {"salary": "01"},
        ],
    )
    def test_main_job_cleanup_pipeline_applies_for_inferred_jobs(
        self, _mock_selenium, _mock_ghost, _mock_wp, _mock_detect, _mock_content
    ):
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args, \
                patch("main.save") as mock_save, \
                patch("main.preview"):
            mock_parse_args.return_value = MagicMock(
                url="https://www.tanitjobs.com/jobs/",
                pages=1,
                fields="title,company,location,salary",
            )

            main.main()

            payload = mock_save.call_args.args[0]
            assert payload["content_type"] == "jobs"
            assert len(payload["items"]) == 1
            assert payload["items"][0]["title"] == "DevOps Engineer"
            assert payload["items"][0]["company"] == "ACME"
            assert "salary" not in payload["items"][0]


class TestMainEntryPoint:
    @patch("main.print")
    @patch("main.run", return_value=([{"name": "A"}, {"name": "A"}], "shopify", "ecommerce"))
    @patch("main.save")
    @patch("main.preview")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_happy_path(self, mock_parse_args, mock_preview, mock_save, _mock_run, mock_print):
        mock_parse_args.return_value = MagicMock(
            url="https://example.com",
            pages=2,
            fields="name,price",
        )

        main.main()

        mock_save.assert_called_once()
        mock_preview.assert_called_once()
        assert mock_print.call_count >= 3

    @patch("main.run", side_effect=KeyboardInterrupt)
    @patch("main.logger.warning")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_handles_keyboard_interrupt(self, mock_parse_args, mock_warning, _mock_run):
        mock_parse_args.return_value = MagicMock(url="https://example.com", pages=1, fields="")
        main.main()
        mock_warning.assert_called_once()
