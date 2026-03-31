# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pytest
import unittest.mock

from qutebrowser.browser import shared
from qutebrowser.utils import usertypes


@pytest.mark.parametrize('dnt, accept_language, custom_headers, expected', [
    # DNT
    (True, None, {}, {b'DNT': b'1'}),
    (False, None, {}, {b'DNT': b'0'}),
    (None, None, {}, {}),
    # Accept-Language
    (False, 'de, en', {}, {b'DNT': b'0', b'Accept-Language': b'de, en'}),
    # Custom headers
    (False, None, {'X-Qute': 'yes'}, {b'DNT': b'0', b'X-Qute': b'yes'}),
    # Mixed
    (False, 'de, en', {'X-Qute': 'yes'}, {b'DNT': b'0',
                                          b'Accept-Language': b'de, en',
                                          b'X-Qute': b'yes'}),
])
def test_custom_headers(config_stub, dnt, accept_language, custom_headers,
                        expected):
    headers = config_stub.val.content.headers
    headers.do_not_track = dnt
    headers.accept_language = accept_language
    headers.custom = custom_headers

    expected_items = sorted(expected.items())
    assert shared.custom_headers(url=None) == expected_items


class TestJsLogToUi:
    """Tests for _js_log_to_ui function."""

    def test_basic_level_filtering_allowed(self, config_stub, monkeypatch):
        """Test that messages matching level filters are shown."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error', 'warning'],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        mock_message_error = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.error', mock_message_error)

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='userscript:test_script',
            line=42,
            msg='Test error message'
        )

        assert result is True
        mock_message_error.assert_called_once_with('JS: [userscript:test_script:42] Test error message')

    def test_basic_level_filtering_blocked(self, config_stub):
        """Test that messages not matching level filters are blocked."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error', 'warning'],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.info,
            source='userscript:my_script',  # Use name that doesn't match *test*
            line=42,
            msg='Test info message'
        )

        assert result is False

    def test_source_pattern_matching(self, config_stub, monkeypatch):
        """Test that source pattern matching works correctly."""
        config_stub.val.content.javascript.log_message.levels = {
            '*test*': ['info', 'warning', 'error']
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        mock_message_info = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.info', mock_message_info)

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.info,
            source='my_test_script',
            line=10,
            msg='Info message'
        )

        assert result is True
        mock_message_info.assert_called_once_with('JS: [my_test_script:10] Info message')

    def test_excludes_basic_functionality(self, config_stub):
        """Test basic exclude pattern functionality."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error'],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            'userscript:*': ['*CSP*', '*Content Security Policy*']
        }

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='userscript:stylesheet',
            line=66,
            msg='Refused to apply inline style because it violates CSP directive'
        )

        assert result is False

    def test_excludes_pattern_matching(self, config_stub, monkeypatch):
        """Test exclude pattern matching with different patterns."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error'],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            'userscript:*': ['*CSP*', 'Permission denied*']
        }

        mock_message_error = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.error', mock_message_error)

        # Should be excluded - matches '*CSP*' pattern
        result1 = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='userscript:test',
            line=1,
            msg='CSP violation detected'
        )

        # Should be excluded - matches 'Permission denied*' pattern
        result2 = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='userscript:test',
            line=2,
            msg='Permission denied to access property'
        )

        # Should NOT be excluded - doesn't match any pattern
        result3 = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='userscript:test',
            line=3,
            msg='Different error message'
        )

        assert result1 is False
        assert result2 is False
        assert result3 is True
        mock_message_error.assert_called_once_with('JS: [userscript:test:3] Different error message')

    def test_multiple_exclude_patterns(self, config_stub):
        """Test multiple exclude patterns for the same source."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error'],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            'userscript:*': ['*CSP*', '*CORS*', '*Permission denied*']
        }

        test_cases = [
            ('CSP violation', False),
            ('CORS error occurred', False),
            ('Permission denied', False),
            ('Some other error', True)
        ]

        for msg_text, should_show in test_cases:
            result = shared._js_log_to_ui(
                level=usertypes.JsLogLevel.error,
                source='userscript:test',
                line=1,
                msg=msg_text
            )
            assert result is should_show

    def test_no_matching_source_pattern(self, config_stub):
        """Test behavior when no source pattern matches."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error'],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='unknown:source',
            line=1,
            msg='Error message'
        )

        assert result is False

    def test_empty_excludes_config(self, config_stub, monkeypatch):
        """Test that empty excludes config doesn't affect normal operation."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error'],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        mock_message_error = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.error', mock_message_error)

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.error,
            source='userscript:test',
            line=1,
            msg='Error message'
        )

        assert result is True
        mock_message_error.assert_called_once_with('JS: [userscript:test:1] Error message')

    def test_debug_level_support(self, config_stub, monkeypatch):
        """Test that debug level is supported."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['debug'],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        mock_message_info = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.info', mock_message_info)

        result = shared._js_log_to_ui(
            level=usertypes.JsLogLevel.debug,
            source='userscript:test',
            line=1,
            msg='Debug message'
        )

        assert result is True
        mock_message_info.assert_called_once_with('JS: [userscript:test:1] Debug message')


class TestJavascriptLogMessage:
    """Tests for javascript_log_message function."""

    def test_message_shown_in_ui(self, config_stub, monkeypatch):
        """Test that messages shown in UI are not logged normally."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error']
        }
        config_stub.val.content.javascript.log_message.excludes = {}
        config_stub.val.content.javascript.log = {
            'error': 'debug'
        }

        mock_message_error = unittest.mock.Mock()
        mock_log_debug = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.error', mock_message_error)
        monkeypatch.setattr('qutebrowser.browser.shared.log.js.debug', mock_log_debug)

        shared.javascript_log_message(
            level=usertypes.JsLogLevel.error,
            source='userscript:test',
            line=42,
            msg='Test error'
        )

        # Should be shown in UI
        mock_message_error.assert_called_once_with('JS: [userscript:test:42] Test error')
        # Should NOT be logged normally
        mock_log_debug.assert_not_called()

    def test_message_not_shown_in_ui(self, config_stub, monkeypatch):
        """Test that messages not shown in UI are logged normally."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error']  # info not enabled
        }
        config_stub.val.content.javascript.log_message.excludes = {}
        config_stub.val.content.javascript.log = {
            'info': 'debug'
        }

        mock_message_info = unittest.mock.Mock()
        mock_log_debug = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.info', mock_message_info)
        monkeypatch.setattr('qutebrowser.browser.shared.log.js.debug', mock_log_debug)

        shared.javascript_log_message(
            level=usertypes.JsLogLevel.info,
            source='userscript:test',
            line=42,
            msg='Test info'
        )

        # Should NOT be shown in UI
        mock_message_info.assert_not_called()
        # Should be logged normally
        mock_log_debug.assert_called_once_with('[userscript:test:42] Test info')

    def test_excluded_message_logged_normally(self, config_stub, monkeypatch):
        """Test that excluded messages are logged normally, not shown in UI."""
        config_stub.val.content.javascript.log_message.levels = {
            'userscript:*': ['error']
        }
        config_stub.val.content.javascript.log_message.excludes = {
            'userscript:*': ['*CSP*']
        }
        config_stub.val.content.javascript.log = {
            'error': 'debug'
        }

        mock_message_error = unittest.mock.Mock()
        mock_log_debug = unittest.mock.Mock()
        monkeypatch.setattr('qutebrowser.browser.shared.message.error', mock_message_error)
        monkeypatch.setattr('qutebrowser.browser.shared.log.js.debug', mock_log_debug)

        shared.javascript_log_message(
            level=usertypes.JsLogLevel.error,
            source='userscript:test',
            line=42,
            msg='CSP violation error'
        )

        # Should NOT be shown in UI (excluded)
        mock_message_error.assert_not_called()
        # Should be logged normally
        mock_log_debug.assert_called_once_with('[userscript:test:42] CSP violation error')
