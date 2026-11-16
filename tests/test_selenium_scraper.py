"""
Tests for selenium_scraper module with mocked drivers.
"""

from unittest.mock import MagicMock, patch

import selenium_scraper as ss


class TestHelperFunctions:
    def test_clean_price_normalizes_symbols_and_spaces(self):
        assert ss.clean_price("  120,50 DT ") == "120.50"
        assert ss.clean_price("$99.99") == "99.99"
        assert ss.clean_price("") == ""

    def test_parse_llm_json_from_plain_json(self):
        raw = '{"container":".card","name":".title","price":".price"}'
        out = ss._parse_llm_json(raw)
        assert out["container"] == ".card"

    def test_parse_llm_json_from_fenced_block(self):
        raw = "```json\n{\"container\":\".c\",\"name\":\".n\",\"price\":\".p\"}\n```"
        out = ss._parse_llm_json(raw)
        assert out["name"] == ".n"


class TestCssFallback:
    def _driver_with_counts(self, mapping):
        driver = MagicMock()

        def find_elements(_by, selector):
            return [object()] * mapping.get(selector, 0)

        driver.find_elements.side_effect = find_elements
        return driver

    def test_css_fallback_returns_valid_selectors(self):
        mapping = {
            ".product-card": 5,
            ".product-title": 6,
            ".price": 6,
        }
        driver = self._driver_with_counts(mapping)

        with patch.object(ss, "CSS_CONTAINERS", [".product-card"]), \
             patch.object(ss, "CSS_NAMES", [".product-title"]), \
             patch.object(ss, "CSS_PRICES", [".price"]):
            selectors = ss.css_fallback(driver)

        assert selectors == {
            "container": ".product-card",
            "fields": {
                "name": ".product-title",
                "price": ".price",
            },
        }

    def test_css_fallback_returns_none_when_not_enough_matches(self):
        mapping = {
            ".product-card": 2,
            ".product-title": 2,
            ".price": 2,
        }
        driver = self._driver_with_counts(mapping)

        with patch.object(ss, "CSS_CONTAINERS", [".product-card"]), \
             patch.object(ss, "CSS_NAMES", [".product-title"]), \
             patch.object(ss, "CSS_PRICES", [".price"]):
            selectors = ss.css_fallback(driver)

        assert selectors is None

    def test_css_fallback_jobs_mode_returns_job_selectors(self):
        mapping = {
            ".listing-item": 12,
            ".listing-item__title": 12,
            ".listing-item-info-company": 12,
            ".listing-item-info-location": 12,
        }
        driver = self._driver_with_counts(mapping)

        with patch.object(ss, "JOB_CONTAINER_SELECTORS", [".listing-item"]), \
             patch.object(ss, "JOB_TITLE_SELECTORS", [".listing-item__title"]), \
             patch.object(ss, "JOB_COMPANY_SELECTORS", [".listing-item-info-company"]), \
             patch.object(ss, "JOB_LOCATION_SELECTORS", [".listing-item-info-location"]):
            selectors = ss.css_fallback(driver, field_hints=["title", "company", "location"])

        assert selectors == {
            "container": ".listing-item",
            "fields": {
                "title": ".listing-item__title",
                "company": ".listing-item-info-company",
                "location": ".listing-item-info-location",
            },
        }


class TestNextPageUrl:
    def test_get_next_page_url_finds_first_valid_href(self):
        driver = MagicMock()
        el = MagicMock()
        el.get_attribute.return_value = "https://example.com/page/2"
        driver.find_element.return_value = el

        with patch.object(ss, "NEXT_PAGE_SELECTORS", ["a.next"]):
            url = ss.get_next_page_url(driver)

        assert url == "https://example.com/page/2"

    def test_get_next_page_url_returns_none_when_missing(self):
        driver = MagicMock()
        driver.find_element.side_effect = Exception("not found")

        with patch.object(ss, "NEXT_PAGE_SELECTORS", ["a.next"]):
            url = ss.get_next_page_url(driver)

        assert url is None


class TestScrapeWithSelenium:
    def _mock_container(self, name, price):
        c = MagicMock()

        name_el = MagicMock()
        name_el.text = name

        price_el = MagicMock()
        price_el.text = price

        c.find_element.return_value = name_el

        def _find_elements(_by, selector):
            if selector == ".title":
                return [name_el]
            if selector == ".price":
                return [price_el]
            return []

        c.find_elements.side_effect = _find_elements
        return c

    def _mock_container_multi_title(self):
        c = MagicMock()

        primary_title = MagicMock()
        primary_title.text = "Real Job Title"

        trailing_title = MagicMock()
        trailing_title.text = "Voir Plus"

        company_el = MagicMock()
        company_el.text = "ACME"

        def _find_elements(_by, selector):
            if selector == ".title":
                return [primary_title, trailing_title]
            if selector == ".company":
                return [company_el]
            return []

        c.find_elements.side_effect = _find_elements
        return c

    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value={"container": ".card", "fields": {"name": ".title", "price": ".price"}})
    def test_scrape_with_existing_driver_single_page(self, _mock_llm, _mock_scroll, _mock_popups):
        driver = MagicMock()
        driver.find_elements.return_value = [
            self._mock_container("Laptop", "1200.00"),
            self._mock_container("Mouse", "49.90"),
        ]

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium(
                "https://example.com", max_pages=1, existing_driver=driver
            )

        assert len(result) == 2
        assert result[0]["name"] == "Laptop"
        driver.quit.assert_not_called()

    @patch("selenium_scraper.setup_driver")
    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value={"container": ".card", "fields": {"name": ".title", "price": ".price"}})
    def test_scrape_owns_driver_quits_on_finish(self, _mock_llm, _mock_scroll, _mock_popups, mock_setup):
        driver = MagicMock()
        mock_setup.return_value = driver
        driver.find_elements.return_value = [self._mock_container("Laptop", "1200.00")]

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium("https://example.com", max_pages=1, enable_preverify=False)

        assert len(result) == 1
        assert driver.quit.call_count >= 1

    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value=None)
    @patch("selenium_scraper.css_fallback", return_value=None)
    def test_scrape_returns_empty_when_selectors_not_found(self, _mock_css, _mock_llm, _mock_scroll, _mock_popups):
        driver = MagicMock()

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium(
                "https://example.com", max_pages=1, existing_driver=driver
            )

        assert result == []

    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value={"container": ".card", "fields": {"name": ".title", "price": ".price"}})
    @patch("selenium_scraper.get_next_page_url", return_value="https://example.com/page/2")
    def test_scrape_multi_page_uses_next_url(self, _mock_next, _mock_llm, _mock_scroll, _mock_popups):
        driver = MagicMock()
        driver.find_elements.return_value = [self._mock_container("Laptop", "1200.00")]

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium(
                "https://example.com", max_pages=2, existing_driver=driver
            )

        assert len(result) == 2
        assert driver.get.call_count == 2

    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value={"container": ".card", "fields": {"name": ".title", "price": ".price"}})
    def test_scrape_skips_invalid_products(self, _mock_llm, _mock_scroll, _mock_popups):
        driver = MagicMock()
        driver.find_elements.return_value = [
            self._mock_container("Laptop", "1200.00"),
            self._mock_container("", "50.00"),
        ]

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium(
                "https://example.com", max_pages=1, existing_driver=driver
            )

        assert len(result) == 2

    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch(
        "selenium_scraper.llm_detect_selectors",
        return_value={"container": ".card", "fields": {"title": ".title", "company": ".company"}},
    )
    def test_scrape_prefers_first_text_for_title_fields(self, _mock_llm, _mock_scroll, _mock_popups):
        driver = MagicMock()
        driver.find_elements.return_value = [self._mock_container_multi_title()]

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium(
                "https://example.com", max_pages=1, existing_driver=driver
            )

        assert len(result) == 1
        assert result[0]["title"] == "Real Job Title"

    @patch("selenium_scraper.BROWSER_HEADLESS", True)
    @patch("selenium_scraper.preverify_challenge")
    @patch("selenium_scraper.setup_driver")
    @patch("selenium_scraper.wait_for_human_verification", side_effect=[False, True])
    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value=None)
    @patch("selenium_scraper.css_fallback", return_value=None)
    def test_challenge_retries_once_in_headed_mode(
        self,
        _mock_css,
        _mock_llm,
        _mock_scroll,
        _mock_popups,
        _mock_wait_challenge,
        mock_setup,
        _mock_preverify,
    ):
        driver_headless = MagicMock()
        driver_headed = MagicMock()
        mock_setup.side_effect = [driver_headless, driver_headed]

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium("https://example.com", max_pages=1, enable_preverify=False)

        assert result == []
        assert mock_setup.call_count == 2

    @patch("selenium_scraper.BROWSER_HEADLESS", True)
    @patch("selenium_scraper.preverify_challenge")
    @patch("selenium_scraper.setup_driver")
    @patch("selenium_scraper.wait_for_human_verification", side_effect=[False, True])
    @patch("selenium_scraper.dismiss_popups")
    @patch("selenium_scraper.scroll_to_load_all")
    @patch("selenium_scraper.llm_detect_selectors", return_value=None)
    @patch("selenium_scraper.css_fallback", return_value=None)
    def test_challenge_retries_once_with_existing_driver(
        self,
        _mock_css,
        _mock_llm,
        _mock_scroll,
        _mock_popups,
        _mock_wait_challenge,
        mock_setup,
        _mock_preverify,
    ):
        existing_driver = MagicMock()
        retry_driver = MagicMock()
        mock_setup.return_value = retry_driver

        with patch("selenium_scraper.WebDriverWait") as mock_wait:
            wait_obj = MagicMock()
            wait_obj.until.return_value = True
            mock_wait.return_value = wait_obj

            result = ss.scrape_with_selenium(
                "https://example.com",
                max_pages=1,
                existing_driver=existing_driver,
                enable_preverify=False,
            )

        assert result == []
        assert mock_setup.call_count == 1
        assert mock_setup.call_args.kwargs.get("headless") is False
