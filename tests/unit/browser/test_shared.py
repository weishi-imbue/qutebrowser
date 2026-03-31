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

import logging

import pytest

from qutebrowser.browser import shared
from qutebrowser.utils import usertypes


class TestJsLogToUi:

    """Tests for _js_log_to_ui and javascript_log_message."""

    def test_show_error_matching_source(self, config_stub, message_mock,
                                         caplog):
        """Message shown when source matches and level is enabled."""
        config_stub.val.content.javascript.log_message.levels = {
            "qute:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        with caplog.at_level(logging.ERROR, 'message'):
            result = shared._js_log_to_ui(
                usertypes.JsLogLevel.error, "qute:test", 42, "some error")

        assert result is True
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text == "JS: [qute:test:42] some error"

    def test_no_show_level_not_enabled(self, config_stub, message_mock):
        """Message not shown when level is not in the enabled list."""
        config_stub.val.content.javascript.log_message.levels = {
            "qute:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        result = shared._js_log_to_ui(
            usertypes.JsLogLevel.info, "qute:test", 1, "info msg")

        assert result is False
        assert not message_mock.messages

    def test_no_show_source_not_matching(self, config_stub, message_mock):
        """Message not shown when source doesn't match any pattern."""
        config_stub.val.content.javascript.log_message.levels = {
            "qute:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        result = shared._js_log_to_ui(
            usertypes.JsLogLevel.error, "other:source", 1, "error msg")

        assert result is False
        assert not message_mock.messages

    def test_exclude_matching_message(self, config_stub, message_mock):
        """Message excluded when source and msg pattern both match."""
        config_stub.val.content.javascript.log_message.levels = {
            "userscript:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            "userscript:*": ["Refused to apply inline style*"],
        }

        result = shared._js_log_to_ui(
            usertypes.JsLogLevel.error,
            "userscript:_qute_stylesheet",
            66,
            "Refused to apply inline style because it violates CSP",
        )

        assert result is False
        assert not message_mock.messages

    def test_exclude_non_matching_message(self, config_stub, message_mock,
                                          caplog):
        """Message shown when source matches exclude but msg does not."""
        config_stub.val.content.javascript.log_message.levels = {
            "userscript:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            "userscript:*": ["Refused to apply inline style*"],
        }

        with caplog.at_level(logging.ERROR, 'message'):
            result = shared._js_log_to_ui(
                usertypes.JsLogLevel.error,
                "userscript:_qute_stylesheet",
                10,
                "TypeError: undefined is not a function",
            )

        assert result is True
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text == (
            "JS: [userscript:_qute_stylesheet:10] "
            "TypeError: undefined is not a function"
        )

    def test_exclude_source_not_matching(self, config_stub, message_mock,
                                         caplog):
        """Message shown when exclude source pattern doesn't match."""
        config_stub.val.content.javascript.log_message.levels = {
            "qute:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            "userscript:*": ["*"],
        }

        with caplog.at_level(logging.ERROR, 'message'):
            result = shared._js_log_to_ui(
                usertypes.JsLogLevel.error, "qute:page", 5, "an error")

        assert result is True
        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text == "JS: [qute:page:5] an error"

    def test_warning_level(self, config_stub, message_mock, caplog):
        """Warning-level messages use the warning message function."""
        config_stub.val.content.javascript.log_message.levels = {
            "*": ["warning"],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        with caplog.at_level(logging.WARNING, 'message'):
            result = shared._js_log_to_ui(
                usertypes.JsLogLevel.warning, "any:source", 1, "warn msg")

        assert result is True
        msg = message_mock.getmsg(usertypes.MessageLevel.warning)
        assert msg.text == "JS: [any:source:1] warn msg"

    def test_info_level(self, config_stub, message_mock):
        """Info-level messages use the info message function."""
        config_stub.val.content.javascript.log_message.levels = {
            "*": ["info"],
        }
        config_stub.val.content.javascript.log_message.excludes = {}

        result = shared._js_log_to_ui(
            usertypes.JsLogLevel.info, "src", 1, "info msg")

        assert result is True
        msg = message_mock.getmsg(usertypes.MessageLevel.info)
        assert msg.text == "JS: [src:1] info msg"

    def test_empty_levels_config(self, config_stub, message_mock):
        """No messages shown when levels config is empty."""
        config_stub.val.content.javascript.log_message.levels = {}
        config_stub.val.content.javascript.log_message.excludes = {}

        result = shared._js_log_to_ui(
            usertypes.JsLogLevel.error, "qute:test", 1, "error")

        assert result is False
        assert not message_mock.messages

    def test_javascript_log_message_shown(self, config_stub, message_mock,
                                          caplog):
        """javascript_log_message doesn't log when message is shown in UI."""
        config_stub.val.content.javascript.log_message.levels = {
            "qute:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {}
        config_stub.val.content.javascript.log = {
            'info': 'info',
            'error': 'error',
            'unknown': 'error',
            'warning': 'warning',
        }

        with caplog.at_level(logging.ERROR, 'message'):
            shared.javascript_log_message(
                usertypes.JsLogLevel.error, "qute:test", 42, "bad thing")

        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        assert msg.text == "JS: [qute:test:42] bad thing"
        # Should not be logged to standard logger when shown in UI
        js_records = [r for r in caplog.records if r.name == 'js']
        assert not any("[qute:test:42] bad thing" in r.message
                       for r in js_records)

    def test_javascript_log_message_not_shown(self, config_stub, message_mock,
                                              caplog):
        """javascript_log_message logs when message is not shown in UI."""
        config_stub.val.content.javascript.log_message.levels = {}
        config_stub.val.content.javascript.log_message.excludes = {}
        config_stub.val.content.javascript.log = {
            'info': 'info',
            'error': 'error',
            'unknown': 'error',
            'warning': 'warning',
        }

        with caplog.at_level(logging.ERROR, 'js'):
            shared.javascript_log_message(
                usertypes.JsLogLevel.error, "other:src", 1, "an error")

        assert not message_mock.messages
        js_records = [r for r in caplog.records if r.name == 'js']
        assert any("[other:src:1] an error" in r.message
                   for r in js_records)

    def test_multiple_exclude_patterns(self, config_stub, message_mock):
        """Exclusion works when one of multiple msg patterns matches."""
        config_stub.val.content.javascript.log_message.levels = {
            "userscript:*": ["error"],
        }
        config_stub.val.content.javascript.log_message.excludes = {
            "userscript:*": [
                "Refused to apply inline style*",
                "Refused to execute inline script*",
            ],
        }

        result = shared._js_log_to_ui(
            usertypes.JsLogLevel.error,
            "userscript:test",
            1,
            "Refused to execute inline script because of CSP",
        )

        assert result is False
        assert not message_mock.messages


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
