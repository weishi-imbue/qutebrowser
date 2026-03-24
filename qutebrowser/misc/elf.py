# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""A best-effort, simplistic ELF parser to extract version info from
QtWebEngineCore."""

import enum
import struct
import re
import mmap
import pathlib
import dataclasses
from typing import IO, Optional, cast

from PyQt5.QtCore import QLibraryInfo

from qutebrowser.utils import log


class ParseError(Exception):
    """Raised when ELF parsing fails."""


class Bitness(enum.Enum):
    """ELF bitness (32 or 64 bit)."""
    x32 = 1
    x64 = 2


class Endianness(enum.Enum):
    """ELF endianness."""
    little = 1
    big = 2


@dataclasses.dataclass
class Ident:
    """ELF identification header."""
    magic: bytes
    klass: Bitness
    data: Endianness

    @classmethod
    def parse(cls, fobj: IO[bytes]) -> 'Ident':
        """Parse ELF identification from a file object."""
        magic = fobj.read(4)
        if magic != b'\x7fELF':
            raise ParseError(f"Invalid ELF magic: {magic!r}")
        klass_byte = fobj.read(1)
        try:
            klass = Bitness(klass_byte[0])
        except (ValueError, IndexError):
            raise ParseError(f"Unsupported ELF class: {klass_byte!r}")
        data_byte = fobj.read(1)
        try:
            data = Endianness(data_byte[0])
        except (ValueError, IndexError):
            raise ParseError(f"Unsupported ELF data encoding: {data_byte!r}")
        # Skip rest of e_ident (10 bytes: version + OS/ABI + padding)
        fobj.read(10)
        return cls(magic=magic, klass=klass, data=data)


@dataclasses.dataclass
class Header:
    """ELF file header."""
    e_shoff: int
    e_shentsize: int
    e_shnum: int
    e_shstrndx: int

    @classmethod
    def parse(cls, fobj: IO[bytes], bitness: Bitness) -> 'Header':
        """Parse ELF header from a file object."""
        if bitness == Bitness.x64:
            # e_type(2) + e_machine(2) + e_version(4) + e_entry(8) +
            # e_phoff(8) + e_flags(4) + e_ehsize(2) + e_phentsize(2) +
            # e_phnum(2) => skip to e_shoff
            # After ident (16 bytes):
            # e_type(2) + e_machine(2) + e_version(4) + e_entry(8) + e_phoff(8)
            fobj.read(2 + 2 + 4 + 8 + 8)  # 24 bytes
            e_shoff = struct.unpack('<Q', fobj.read(8))[0]
            # e_flags(4) + e_ehsize(2) + e_phentsize(2) + e_phnum(2)
            fobj.read(4 + 2 + 2 + 2)
            e_shentsize = struct.unpack('<H', fobj.read(2))[0]
            e_shnum = struct.unpack('<H', fobj.read(2))[0]
            e_shstrndx = struct.unpack('<H', fobj.read(2))[0]
        else:
            # 32-bit
            fobj.read(2 + 2 + 4 + 4 + 4)  # 16 bytes
            e_shoff = struct.unpack('<I', fobj.read(4))[0]
            fobj.read(4 + 2 + 2 + 2)
            e_shentsize = struct.unpack('<H', fobj.read(2))[0]
            e_shnum = struct.unpack('<H', fobj.read(2))[0]
            e_shstrndx = struct.unpack('<H', fobj.read(2))[0]
        return cls(e_shoff=e_shoff, e_shentsize=e_shentsize,
                   e_shnum=e_shnum, e_shstrndx=e_shstrndx)


@dataclasses.dataclass
class SectionHeader:
    """ELF section header."""
    sh_name: int
    sh_type: int
    sh_offset: int
    sh_size: int

    @classmethod
    def parse(cls, fobj: IO[bytes], bitness: Bitness) -> 'SectionHeader':
        """Parse a section header from a file object."""
        if bitness == Bitness.x64:
            sh_name = struct.unpack('<I', fobj.read(4))[0]
            sh_type = struct.unpack('<I', fobj.read(4))[0]
            fobj.read(8 + 8)  # sh_flags + sh_addr
            sh_offset = struct.unpack('<Q', fobj.read(8))[0]
            sh_size = struct.unpack('<Q', fobj.read(8))[0]
            fobj.read(4 + 4 + 8 + 8)  # rest of section header
        else:
            sh_name = struct.unpack('<I', fobj.read(4))[0]
            sh_type = struct.unpack('<I', fobj.read(4))[0]
            fobj.read(4 + 4)  # sh_flags + sh_addr
            sh_offset = struct.unpack('<I', fobj.read(4))[0]
            sh_size = struct.unpack('<I', fobj.read(4))[0]
            fobj.read(4 + 4 + 4 + 4)  # rest of section header
        return cls(sh_name=sh_name, sh_type=sh_type,
                   sh_offset=sh_offset, sh_size=sh_size)


@dataclasses.dataclass
class Versions:
    """Extracted version strings."""
    webengine: str
    chromium: str


def _find_lib() -> Optional[pathlib.Path]:
    """Find the QtWebEngineCore library."""
    lib_path = pathlib.Path(QLibraryInfo.location(QLibraryInfo.LibrariesPath))
    candidates = [
        lib_path / 'libQt5WebEngineCore.so.5',
        lib_path / 'libQt5WebEngineCore.so',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_rodata_header(f: IO[bytes]) -> SectionHeader:
    """Find and return the .rodata section header from an ELF file."""
    ident = Ident.parse(f)
    header = Header.parse(f, ident.klass)

    # Read the section header string table
    f.seek(header.e_shoff + header.e_shstrndx * header.e_shentsize)
    shstrtab = SectionHeader.parse(f, ident.klass)

    f.seek(shstrtab.sh_offset)
    strtab_data = f.read(shstrtab.sh_size)

    # Find .rodata section
    for i in range(header.e_shnum):
        f.seek(header.e_shoff + i * header.e_shentsize)
        sh = SectionHeader.parse(f, ident.klass)
        try:
            name_end = strtab_data.index(b'\x00', sh.sh_name)
            name = strtab_data[sh.sh_name:name_end].decode('ascii')
        except (ValueError, UnicodeDecodeError):
            continue
        if name == '.rodata':
            return sh

    raise ParseError("No .rodata section found")


def parse_webenginecore() -> Versions:
    """Find and parse the QtWebEngineCore library to extract versions."""
    lib_path = _find_lib()
    if lib_path is None:
        raise ParseError("QtWebEngineCore library not found")

    try:
        with open(lib_path, 'rb') as f:
            rodata = get_rodata_header(f)

            # Use mmap for efficient reading
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                rodata_data = mm[rodata.sh_offset:
                                 rodata.sh_offset + rodata.sh_size]
    except OSError as e:
        raise ParseError(f"Failed to read library: {e}")

    webengine_match = re.search(rb'QtWebEngine/([0-9.]+)', rodata_data)
    chromium_match = re.search(rb'Chrome/([0-9.]+)', rodata_data)

    if not webengine_match:
        raise ParseError("QtWebEngine version string not found in .rodata")
    if not chromium_match:
        raise ParseError("Chromium version string not found in .rodata")

    try:
        webengine = webengine_match.group(1).decode('ascii')
        chromium = chromium_match.group(1).decode('ascii')
    except UnicodeDecodeError as e:
        raise ParseError(f"Failed to decode version string: {e}")

    return Versions(webengine=webengine, chromium=chromium)
