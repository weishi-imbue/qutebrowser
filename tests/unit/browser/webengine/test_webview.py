# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import dataclasses

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

    @pytest.fixture
    def affected_version(self, monkeypatch):
        """Mock version_check to simulate an affected Qt version (e.g. 6.5.2)."""
        def fake_version_check(version, compiled=False):
            # 6.2.3 -> True (is >=6.2.3), 6.7.0 -> False (is <6.7.0)
            if version == "6.2.3":
                return True
            if version == "6.7.0":
                return False
            return True
        monkeypatch.setattr(webview.qtutils, 'version_check', fake_version_check)

    @pytest.fixture
    def unaffected_old_version(self, monkeypatch):
        """Mock version_check to simulate an old Qt version (e.g. 6.1.0)."""
        def fake_version_check(version, compiled=False):
            # 6.2.3 -> False (is <6.2.3)
            if version == "6.2.3":
                return False
            if version == "6.7.0":
                return False
            return False
        monkeypatch.setattr(webview.qtutils, 'version_check', fake_version_check)

    @pytest.fixture
    def unaffected_new_version(self, monkeypatch):
        """Mock version_check to simulate a fixed Qt version (e.g. 6.7.0)."""
        def fake_version_check(version, compiled=False):
            # 6.2.3 -> True, 6.7.0 -> True (is >=6.7.0)
            if version == "6.2.3":
                return True
            if version == "6.7.0":
                return True
            return True
        monkeypatch.setattr(webview.qtutils, 'version_check', fake_version_check)

    def test_returns_empty_for_old_qt(self, unaffected_old_version):
        result = webview.extra_suffixes_workaround(["image/jpeg"])
        assert result == set()

    def test_returns_empty_for_fixed_qt(self, unaffected_new_version):
        result = webview.extra_suffixes_workaround(["image/jpeg"])
        assert result == set()

    def test_specific_mimetype(self, affected_version):
        result = webview.extra_suffixes_workaround(["image/jpeg"])
        assert ".jpg" in result or ".jpe" in result or ".jpeg" in result
        # At minimum, .jpg should be returned as an extra suffix
        assert ".jpg" in result

    def test_existing_extension_not_duplicated(self, affected_version):
        result = webview.extra_suffixes_workaround(["image/jpeg", ".jpg"])
        assert ".jpg" not in result

    def test_wildcard_mimetype(self, affected_version):
        result = webview.extra_suffixes_workaround(["image/*"])
        # Should include common image extensions
        assert ".jpg" in result or ".png" in result

    def test_extension_passthrough(self, affected_version):
        # Entries starting with "." are treated as existing extensions
        result = webview.extra_suffixes_workaround([".jpg", ".png"])
        # No MIME types to process, so no extras
        assert result == set()

    def test_empty_input(self, affected_version):
        result = webview.extra_suffixes_workaround([])
        assert result == set()

    def test_mixed_mimetypes_and_extensions(self, affected_version):
        result = webview.extra_suffixes_workaround(["image/jpeg", ".jpeg"])
        # .jpeg is already present, so should not be in extras
        assert ".jpeg" not in result
        # But .jpg and .jpe should still be returned if available
        assert ".jpg" in result
