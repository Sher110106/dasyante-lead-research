import io
import json
import unittest
from urllib.error import HTTPError

from dasyante.providers import ProviderConfigError, ProviderError, TavilyClient, TinyFishClient, _request_json, ensure_public_url


class ProviderTests(unittest.TestCase):
    def test_missing_key_fails_before_network(self):
        with self.assertRaises(ProviderConfigError):
            TavilyClient(api_key="")

    def test_linkedin_is_not_an_allowed_research_url(self):
        self.assertFalse(ensure_public_url("https://www.linkedin.com/company/acme"))
        self.assertTrue(ensure_public_url("https://acme.example/docs"))

    def test_tinyfish_requires_a_key(self):
        with self.assertRaises(ProviderConfigError):
            TinyFishClient(api_key="")

    def test_tinyfish_request_and_response(self):
        def opener(request, timeout):
            self.assertEqual(request.full_url, "https://api.fetch.tinyfish.ai")
            self.assertEqual(request.get_header("X-api-key"), "test-key")
            self.assertEqual(request.method, "POST")
            payload = json.loads(request.data)
            self.assertEqual(payload["urls"], ["https://acme.test/docs"])
            self.assertEqual(payload["format"], "markdown")
            return io.BytesIO(json.dumps({"results": [{"url": "https://acme.test/docs", "text": "# Acme docs", "title": "Acme"}], "errors": []}).encode())

        result = TinyFishClient("test-key", opener).scrape("https://acme.test/docs")
        self.assertIn("Acme docs", result.markdown)
        self.assertEqual(result.title, "Acme")

    def test_tinyfish_url_failure_is_not_a_successful_empty_page(self):
        def opener(request, timeout):
            return io.BytesIO(b'{"results": [], "errors": [{"error": "bot_blocked"}]}')

        with self.assertRaisesRegex(ProviderError, "bot_blocked"):
            TinyFishClient("test-key", opener).scrape("https://acme.test/docs")

    def test_tinyfish_rejects_linkedin_before_network(self):
        def opener(*args, **kwargs):
            self.fail("LinkedIn must not be fetched")

        with self.assertRaises(ProviderError):
            TinyFishClient("test-key", opener).scrape("https://linkedin.com/company/acme")

    def test_tinyfish_rejects_empty_content(self):
        def opener(request, timeout):
            return io.BytesIO(b'{"results": [{"text": ""}], "errors": []}')

        with self.assertRaisesRegex(ProviderError, "empty"):
            TinyFishClient("test-key", opener).scrape("https://acme.test/docs")

    def test_provider_errors_do_not_expose_credentials(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"invalid test-secret-key"))

        with self.assertRaises(ProviderError) as error:
            _request_json("GET", "https://api.example.test", headers={"X-API-Key": "test-secret-key"}, opener=opener)
        self.assertIn("[REDACTED]", str(error.exception))
        self.assertNotIn("test-secret-key", str(error.exception))

    def test_provider_timeout_is_actionable(self):
        def opener(request, timeout):
            raise TimeoutError()

        with self.assertRaisesRegex(ProviderError, "timed out"):
            _request_json("GET", "https://api.example.test", opener=opener)



if __name__ == "__main__":
    unittest.main()
