# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2024 The qutebrowser contributors

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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Module providing a completion category for filesystem paths."""

import os
from typing import Optional, List
from urllib.parse import urlparse

from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex
from PyQt5.QtWidgets import QWidget

from qutebrowser.config import config
from qutebrowser.utils import log


class FilePathCategory(QAbstractListModel):
    """Public completion category representing filesystem paths."""

    def __init__(self, name: str, parent: Optional[QWidget] = None) -> None:
        """Initialize the category model and internal storage for path suggestions.

        Args:
            name: human readable identifier for the category.
            parent: optional Qt parent.
        """
        super().__init__(parent)
        self.name = name
        self._suggestions: List[str] = []

    def set_pattern(self, val: str) -> None:
        """Update the model's internal list of suggested paths.

        Updates the model's internal list of suggested paths based on the
        current command-line pattern so the completion view can render
        appropriate filesystem suggestions.

        Args:
            val: the user's partially typed URL or path used to update suggestions.
        """
        self.beginResetModel()
        try:
            self._suggestions = self._get_suggestions_for_pattern(val)
        finally:
            self.endResetModel()

    def _get_suggestions_for_pattern(self, pattern: str) -> List[str]:
        """Get filesystem suggestions for the given pattern.

        Args:
            pattern: The pattern to match against.

        Returns:
            List of filesystem path suggestions.
        """
        if not pattern:
            # Return favorite paths when no pattern is provided
            try:
                return list(config.val.completion.favorite_paths)
            except (AttributeError, TypeError):
                # Config not available (e.g., during testing), return empty list
                return []

        # Handle file:// URLs
        if pattern.startswith('file://'):
            try:
                parsed = urlparse(pattern)
                if parsed.scheme == 'file' and parsed.netloc in ('', 'localhost'):
                    # Convert file:// URL to local path
                    local_path = parsed.path
                    return self._get_directory_suggestions(local_path)
            except Exception:
                # Invalid URL, return no suggestions
                return []
            return []

        # Handle ~ (home directory expansion)
        if pattern.startswith('~'):
            expanded_pattern = os.path.expanduser(pattern)
            suggestions = self._get_directory_suggestions(expanded_pattern)
            # Convert back to ~ form for display where appropriate
            home = os.path.expanduser('~')
            return [
                s.replace(home, '~', 1) if s.startswith(home) else s
                for s in suggestions
            ]

        # Handle absolute paths
        if os.path.isabs(pattern):
            return self._get_directory_suggestions(pattern)

        # For non-filesystem patterns, return no suggestions
        return []

    def _get_directory_suggestions(self, path: str) -> List[str]:
        """Get directory listing suggestions for the given path.

        Args:
            path: The directory path to list.

        Returns:
            List of filesystem entries in the directory.
        """
        try:
            if os.path.isdir(path):
                # If path is a directory, list its contents
                entries = []
                try:
                    for entry in sorted(os.listdir(path)):
                        full_path = os.path.join(path, entry)
                        entries.append(full_path)
                    return entries
                except (OSError, PermissionError) as e:
                    log.completion.debug(f"Cannot list directory {path}: {e}")
                    return []
            else:
                # If path is not a complete directory, try to find matches in parent dir
                parent_dir = os.path.dirname(path)
                basename = os.path.basename(path)

                if not os.path.isdir(parent_dir):
                    return []

                entries = []
                try:
                    for entry in sorted(os.listdir(parent_dir)):
                        if entry.startswith(basename):
                            full_path = os.path.join(parent_dir, entry)
                            entries.append(full_path)
                    return entries
                except (OSError, PermissionError) as e:
                    log.completion.debug(f"Cannot list directory {parent_dir}: {e}")
                    return []
        except Exception as e:
            log.completion.debug(f"Error getting directory suggestions for {path}: {e}")
            return []

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Optional[str]:
        """Supply display data for the view.

        When asked for Qt.DisplayRole and column 0, returns the path string
        for the given row.

        Args:
            index: row/column to fetch.
            role: Qt data role.

        Returns:
            The display string (path) for column 0; None for other roles/columns
            or out-of-range indices.
        """
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            row = index.row()
            if 0 <= row < len(self._suggestions):
                if index.column() == 0:
                    return self._suggestions[row]
                else:
                    # Return None for accessory columns (1 and 2)
                    return None

        return None

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns.

        Args:
            parent: parent index.

        Returns:
            Number of columns (3 for path, None, None tuple format).
        """
        return 3

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Report how many suggestion rows the model currently contains.

        Args:
            parent: parent index.

        Returns:
            Number of available path suggestion rows.
        """
        if parent.isValid():
            return 0
        return len(self._suggestions)