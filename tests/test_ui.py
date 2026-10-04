import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("node"), "Node is needed for the UI rendering check")
class UiTests(unittest.TestCase):
    def test_company_profile_metadata_and_warnings_are_escaped(self):
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const element = { addEventListener() {}, querySelectorAll() { return []; } };
const context = {
  document: { querySelector() { return element; }, querySelectorAll() { return []; }, addEventListener() {} },
  fetch: async () => ({ ok: true, json: async () => ({ candidates: [], stats: {} }) }),
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('web/app.js', 'utf8'), context);
const html = context.renderCompanyProfile({ company_profile: {
  status: 'error', error: '<script>bad</script>', fetched_at: '2026-10-03T00:00:00Z',
  data: { industry: '<b>software</b>', employee_count: 150, technologies: ['LangChain'] },
} });
assert(html.includes('150'));
assert(html.includes('LangChain'));
assert(html.includes('&lt;b&gt;software&lt;/b&gt;'));
assert(html.includes('&lt;script&gt;bad&lt;/script&gt;'));
assert(!html.includes('<script>'));
assert(html.includes('previous profile'));
assert(html.includes('does not add fit-score points'));
assert(context.renderCompanyProfile({ company_profile: { status: 'not_found', data: null } }).includes('no company match'));
assert(context.renderCompanyProfile({}).includes('not configured'));
"""
        result = subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
