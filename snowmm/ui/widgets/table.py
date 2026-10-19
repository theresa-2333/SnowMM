"""Reusable table listing mods, with checkbox toggling and a context menu."""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from ...core.models import Mod, human_size
from ...i18n import character_name, tr
from .. import icons
from ..theme import Theme

ROLE_MOD_ID = Qt.ItemDataRole.UserRole + 1


class ModTable(QTableWidget):
    """Lists mods with an "enabled" checkbox in the first column."""

    selection_changed = Signal(list)
    toggle_requested = Signal(list, bool)
    action_requested = Signal(str, list)  # action name, mods
    open_requested = Signal(object)

    def __init__(self, theme: Theme, columns: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.theme = theme
        self._mods: list[Mod] = []
        self.columns = columns or ["enabled", "name", "character", "author", "added", "size"]
        headers = {
            "enabled": tr("column_enabled"),
            "name": tr("column_name"),
            "character": tr("column_character"),
            "author": tr("column_author"),
            "added": tr("column_added"),
            "size": tr("column_size"),
            "note": tr("column_note"),
        }
        self.setColumnCount(len(self.columns))
        self.setHorizontalHeaderLabels([headers.get(key, key) for key in self.columns])
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(False)
        self.setWordWrap(False)
        self.setIconSize(QSize(16, 16))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.itemChanged.connect(self._on_item_changed)
        self.itemSelectionChanged.connect(self._emit_selection)
        self.doubleClicked.connect(self._on_double_clicked)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if "name" in self.columns:
            header.setSectionResizeMode(self.columns.index("name"), QHeaderView.ResizeMode.Stretch)

    # ------------------------------------------------------------------ state
    def set_mods(self, mods: list[Mod]) -> None:
        selected = {mod.id for mod in self.selected_mods()}
        scroll = self.verticalScrollBar().value()
        self.blockSignals(True)
        self.setRowCount(0)
        self._mods = list(mods)
        self.setRowCount(len(mods))
        for row, mod in enumerate(mods):
            self._fill_row(row, mod)
            if mod.id in selected:
                self.selectionModel().select(
                    self.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                )
        self.verticalScrollBar().setValue(scroll)
        self.blockSignals(False)
        self._update_columns()
        self._emit_selection()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_columns()

    def _update_columns(self) -> None:
        width = self.viewport().width()
        for column, key in enumerate(self.columns):
            hidden = (
                (key in {"author", "added", "note"} and width < 520)
                or (key == "character" and width < 400)
                or (key == "size" and width < 300)
            )
            self.setColumnHidden(column, hidden)

    def selected_mods(self) -> list[Mod]:
        rows = sorted({index.row() for index in self.selectedIndexes()})
        return [self._mods[row] for row in rows if 0 <= row < len(self._mods)]

    def mod_rows(self) -> list[Mod]:
        return list(self._mods)

    def _fill_row(self, row: int, mod: Mod) -> None:
        for column, key in enumerate(self.columns):
            if key == "enabled":
                item = QTableWidgetItem()
                item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                item.setCheckState(Qt.CheckState.Checked if mod.enabled else Qt.CheckState.Unchecked)
                item.setToolTip(str(mod.enabled_path))
            else:
                item = QTableWidgetItem(self._text_for(mod, key))
                item.setToolTip(str(mod.enabled_path))
            if key == "size":
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if key == "name":
                colour = self.theme.success if mod.enabled else self.theme.text_faint
                item.setIcon(icons.icon("package" if mod.enabled else "close", colour, 14))
            item.setData(ROLE_MOD_ID, mod.id)
            self.setItem(row, column, item)

    @staticmethod
    def _text_for(mod: Mod, key: str) -> str:
        if key == "name":
            return mod.name
        if key == "character":
            return character_name(mod.character)
        if key == "author":
            return mod.author
        if key == "added":
            return mod.added_at[:10]
        if key == "size":
            return human_size(mod.size)
        if key == "note":
            return mod.note
        return ""

    def _mod_at(self, row: int) -> Mod | None:
        return self._mods[row] if 0 <= row < len(self._mods) else None

    # ----------------------------------------------------------------- events
    def _emit_selection(self) -> None:
        self.selection_changed.emit(self.selected_mods())

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self.columns[item.column()] != "enabled":
            return
        mod = self._mod_at(item.row())
        if mod is None:
            return
        self.toggle_requested.emit([mod], item.checkState() == Qt.CheckState.Checked)

    def _on_double_clicked(self, index) -> None:
        mod = self._mod_at(index.row())
        if mod is not None:
            self.open_requested.emit(mod)

    def _show_menu(self, position) -> None:
        mods = self.selected_mods()
        if not mods:
            return
        menu = QMenu(self)
        enable = QAction(tr("button_enable"), menu)
        enable.triggered.connect(lambda: self.action_requested.emit("enable", mods))
        disable = QAction(tr("button_disable"), menu)
        disable.triggered.connect(lambda: self.action_requested.emit("disable", mods))
        reveal = QAction(tr("button_open_folder"), menu)
        reveal.triggered.connect(lambda: self.action_requested.emit("reveal", mods))
        copy = QAction(tr("button_copy_path"), menu)
        copy.triggered.connect(lambda: self.action_requested.emit("copy", mods))
        remove = QAction(tr("button_delete"), menu)
        remove.triggered.connect(lambda: self.action_requested.emit("delete", mods))
        menu.addAction(enable)
        menu.addAction(disable)
        menu.addSeparator()
        menu.addAction(reveal)
        menu.addAction(copy)
        menu.addSeparator()
        menu.addAction(remove)
        menu.exec(self.viewport().mapToGlobal(position))

    def select_mod(self, mod_id: str) -> None:
        for row, mod in enumerate(self._mods):
            if mod.id == mod_id:
                self.selectRow(row)
                return
