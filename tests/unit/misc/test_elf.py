# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
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

import io
import struct

import pytest
import hypothesis
from hypothesis import strategies as hst

from qutebrowser.misc import elf
from qutebrowser.utils import utils


@pytest.mark.parametrize('fmt, expected', [
    (elf.Ident._FORMAT, 0x10),

    (elf.Header._FORMATS[elf.Bitness.x64], 0x30),
    (elf.Header._FORMATS[elf.Bitness.x32], 0x24),

    (elf.SectionHeader._FORMATS[elf.Bitness.x64], 0x40),
    (elf.SectionHeader._FORMATS[elf.Bitness.x32], 0x28),
])
def test_format_sizes(fmt, expected):
    """Ensure the struct format have the expected sizes.

    See https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#File_header
    and https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#Section_header
    """
    assert struct.calcsize(fmt) == expected


@pytest.mark.skipif(not utils.is_linux, reason="Needs Linux")
def test_result(qapp, caplog):
    """Test the real result of ELF parsing.

    NOTE: If you're a distribution packager (or contributor) and see this test failing,
    I'd like your help with making either the code or the test more reliable! The
    underlying code is susceptible to changes in the environment, and while it's been
    tested in various environments (Archlinux, Ubuntu), might break in yours.

    If that happens, please report a bug about it!
    """
    pytest.importorskip('qutebrowser.qt.webenginecore')

    versions = elf.parse_webenginecore()
    assert versions is not None

    # No failing mmap
    assert len(caplog.messages) == 2
    assert caplog.messages[0].startswith('QtWebEngine .so found at')
    assert caplog.messages[1].startswith('Got versions from ELF:')

    from qutebrowser.browser.webengine import webenginesettings
    webenginesettings.init_user_agent()
    ua = webenginesettings.parsed_user_agent

    assert ua.qt_version == versions.webengine
    assert ua.upstream_browser_version == versions.chromium


@pytest.mark.parametrize("data, expected", [
    # Simple match (original behavior)
    (
        b"\x00QtWebEngine/5.15.9 Chrome/87.0.4280.144\x00",
        elf.Versions("5.15.9", "87.0.4280.144"),
    ),
    # Ignoring garbage string-like data
    (
        b"\x00QtWebEngine/5.15.9 Chrome/87.0.4xternalclearkey\x00\x00"
        b"QtWebEngine/5.15.9 Chrome/87.0.4280.144\x00",
        elf.Versions("5.15.9", "87.0.4280.144"),
    ),
    # Qt 6.4+ partial match fallback - no trailing null after Chrome version
    (
        b"some data\x00QtWebEngine/6.4.2 Chrome/112.0.5 suffix data\x00"
        b"another section\x00112.0.5615.213\x00end",
        elf.Versions("6.4.2", "112.0.5615.213"),
    ),
    # Another Qt 6.4+ case with different positioning
    (
        b"\x00112.0.5615.213\x00prefix\x00QtWebEngine/6.5.0 Chrome/112.0.5"
        b" more data",
        elf.Versions("6.5.0", "112.0.5615.213"),
    ),
])
def test_find_versions(data, expected):
    assert elf._find_versions(data) == expected


@pytest.mark.parametrize("data, expected_error", [
    # No match at all
    (
        b"no version strings here",
        "No match in .rodata",
    ),
    # Inconclusive partial Chromium bytes - no dot
    (
        b"\x00QtWebEngine/6.4.2 Chrome/112",
        "Inconclusive partial Chromium bytes",
    ),
    # Inconclusive partial Chromium bytes - too short (< 6 bytes)
    (
        b"\x00QtWebEngine/6.4.2 Chrome/11.0",
        "Inconclusive partial Chromium bytes",
    ),
    # Partial match found but no full version string
    (
        b"\x00QtWebEngine/6.4.2 Chrome/112.0.5",
        "No match in .rodata for full version",
    ),
])
def test_find_versions_errors(data, expected_error):
    """Test error cases for _find_versions function."""
    with pytest.raises(elf.ParseError, match=expected_error):
        elf._find_versions(data)




@hypothesis.given(data=hst.builds(
    lambda *a: b''.join(a),
    hst.sampled_from([b'', b'\x7fELF', b'\x7fELF\x02\x01\x01']),
    hst.binary(min_size=0x70),
))
def test_hypothesis(data):
    """Fuzz ELF parsing and make sure no crashes happen."""
    fobj = io.BytesIO(data)
    try:
        elf._parse_from_file(fobj)
    except elf.ParseError as e:
        print(e)
