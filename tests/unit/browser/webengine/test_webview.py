# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import dataclasses
from unittest import mock

import pytest
webview = pytest.importorskip('qutebrowser.browser.webengine.webview')

from qutebrowser.qt.webenginecore import QWebEnginePage

from helpers import testutils


@dataclasses.dataclass
class Naming:

    prefix: str = ""
    suffix: str = ""


def camel_to_snake(naming, name):
    if naming.prefix:
        assert name.startswith(naming.prefix)
        name = name[len(naming.prefix):]
    if naming.suffix:
        assert name.endswith(naming.suffix)
        name = name[:-len(naming.suffix)]
    # https://stackoverflow.com/a/1176023
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


@pytest.mark.parametrize("naming, name, expected", [
    (Naming(prefix="NavigationType"), "NavigationTypeLinkClicked", "link_clicked"),
    (Naming(prefix="NavigationType"), "NavigationTypeTyped", "typed"),
    (Naming(prefix="NavigationType"), "NavigationTypeBackForward", "back_forward"),
    (Naming(suffix="MessageLevel"), "InfoMessageLevel", "info"),
])
def test_camel_to_snake(naming, name, expected):
    assert camel_to_snake(naming, name) == expected


@pytest.mark.parametrize("enum_type, naming, mapping", [
    (
        QWebEnginePage.JavaScriptConsoleMessageLevel,
        Naming(suffix="MessageLevel"),
        webview.WebEnginePage._JS_LOG_LEVEL_MAPPING,
    ),
    (
        QWebEnginePage.NavigationType,
        Naming(prefix="NavigationType"),
        webview.WebEnginePage._NAVIGATION_TYPE_MAPPING,
    )
])
def test_enum_mappings(enum_type, naming, mapping):
    members = testutils.enum_members(QWebEnginePage, enum_type).items()
    for name, val in members:
        mapped = mapping[val]
        assert camel_to_snake(naming, name) == mapped.name


class TestExtraSuffixesWorkaround:
    """Tests for the extra_suffixes_workaround function."""

    @pytest.mark.parametrize("qt_version, expected_active", [
        ("6.2.2", False),  # Too old
        ("6.2.3", True),   # At minimum threshold
        ("6.5.0", True),   # Within range
        ("6.6.9", True),   # Within range
        ("6.7.0", False),  # At maximum threshold (exclusive)
        ("6.8.0", False),  # Too new
    ])
    def test_qt_version_check(self, qt_version, expected_active):
        """Test that the workaround only applies for Qt versions ≥6.2.3 and <6.7.0."""
        with mock.patch("qutebrowser.utils.qtutils.version_check") as version_check_mock:
            # Mock version_check to return expected values based on version
            def mock_version_check(version, compiled=False):
                if version == "6.2.3":
                    return qt_version >= "6.2.3"
                elif version == "6.7.0":
                    return qt_version >= "6.7.0"
                return False

            version_check_mock.side_effect = mock_version_check

            result = webview.extra_suffixes_workaround(["image/jpeg"])

            if expected_active:
                # Should return some extensions for image/jpeg
                assert len(result) > 0
                assert any(ext.endswith(('.jpg', '.jpeg', '.jpe')) for ext in result)
            else:
                # Should return empty set
                assert result == set()

    def test_empty_input(self):
        """Test handling of empty input."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            # First call returns True (≥6.2.3), second returns False (<6.7.0)
            mock_check.side_effect = [True, False]

            result = webview.extra_suffixes_workaround([])
            assert result == set()

    def test_existing_suffixes_deduplication(self):
        """Test that existing suffixes are not duplicated in the output."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            result = webview.extra_suffixes_workaround(["image/jpeg", ".jpg", ".jpeg"])

            # Should not include .jpg or .jpeg since they're already in input
            assert ".jpg" not in result
            assert ".jpeg" not in result
            # But might include .jpe if it exists for image/jpeg
            assert len([ext for ext in result if ext.startswith(".jp")]) <= 1

    def test_wildcard_mime_types(self):
        """Test handling of wildcard MIME types like 'image/*'."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            result = webview.extra_suffixes_workaround(["image/*"])

            # Should include common image extensions
            image_extensions = {ext for ext in result if ext.startswith('.') and
                              any(ext.endswith(suffix) for suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'])}
            assert len(image_extensions) > 0

    def test_specific_mime_types(self):
        """Test handling of specific MIME types."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            result = webview.extra_suffixes_workaround(["image/jpeg"])

            # Should include extensions for JPEG
            jpeg_extensions = {ext for ext in result if ext.endswith(('.jpg', '.jpeg', '.jpe'))}
            assert len(jpeg_extensions) > 0

    def test_mixed_input_types(self):
        """Test handling of mixed input with both MIME types and existing extensions."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            input_types = ["image/jpeg", "text/plain", ".txt", ".jpg"]
            result = webview.extra_suffixes_workaround(input_types)

            # Should not include .txt or .jpg since they're already provided
            assert ".txt" not in result
            assert ".jpg" not in result
            # May include other extensions for the MIME types
            assert isinstance(result, set)

    def test_case_insensitive_extension_handling(self):
        """Test that extension comparison is case-insensitive."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            # Test with uppercase extension
            result = webview.extra_suffixes_workaround(["image/jpeg", ".JPG"])

            # Should not include .jpg since .JPG is equivalent
            assert ".jpg" not in result

    def test_return_type_and_lowercase(self):
        """Test that function returns a set and extensions are lowercase."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            result = webview.extra_suffixes_workaround(["image/jpeg"])

            # Should return a set
            assert isinstance(result, set)
            # All extensions should be lowercase and start with '.'
            for ext in result:
                assert isinstance(ext, str)
                assert ext.startswith('.')
                assert ext == ext.lower()

    def test_multiple_wildcard_types(self):
        """Test handling of multiple wildcard MIME types."""
        with mock.patch("qutebrowser.utils.qtutils.version_check", return_value=True) as mock_check:
            mock_check.side_effect = [True, False]  # Active workaround

            result = webview.extra_suffixes_workaround(["image/*", "video/*"])

            # Should include extensions for both image and video types
            assert len(result) > 0
            # Result should be a proper set (no duplicates)
            assert len(result) == len(set(result))
