from typing import List
from PySide6 import QtWidgets, QtCore

from magic_actions import utils as action_utils
from pyside_common import utils as pyside_utils
#from actions_widget import ActionsContainer, ADDITIONAL_SPACING
from actions_widget import ActionsContainer


class ImportDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, schema:dict, actions:List[action_utils.MagicAction], show_preview:bool, width:int = 550):
        super().__init__(parent)

        # set window icon and title
        self.setWindowIcon(pyside_utils.getLogoIcon())
        self.setWindowTitle("Select an Import Action")

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        # create actions container
        self.actions_container = ActionsContainer(use_scrollable=False, column_count=1)
        self.actions_container.populateContainer(schema, actions)
        self.actions_container.setShowPreview(show_preview)

        # create button widget
        self.button_widget = QtWidgets.QWidget()
        self.button_layout = QtWidgets.QGridLayout()
        self.button_widget.setLayout(self.button_layout)

        # create and add buttons
        self.select_btn = pyside_utils.IconButton(name="Import")
        self.button_layout.addWidget(self.select_btn, 0, self.button_layout.columnCount())
        self.select_btn.pressed.connect(self.onSelect)
        self.select_btn.setRPDButtonHighlight()
        self.select_btn.setDefault(True)
        self.select_btn.setToolTip("Start processing with the current settings.")

        # self.default_btn = pyside_utils.IconButton("Reset to Defaults")
        # self.button_layout.addWidget(self.default_btn, 0, self.button_layout.columnCount())
        # self.default_btn.pressed.connect(self.onDefault)
        # self.select_btn.setToolTip("Reset settings to their default values.")

        self.cancel_btn = pyside_utils.IconButton("Cancel")
        self.button_layout.addWidget(self.cancel_btn, 0, self.button_layout.columnCount())
        self.cancel_btn.pressed.connect(self.onCancel)
        self.select_btn.setToolTip("Cancel processing.")

        self.button_layout.addWidget(QtWidgets.QWidget(), 0, self.button_layout.columnCount())

        # add widgets to main layout
        self.main_layout.addWidget(self.actions_container)
        if not self.actions_container.isEmpty():
            self.actions_container.actionChanged(0) # initialize
        print(f"Current Widget Height: {self.actions_container.stacked_widget.size().height()}")

        self.main_layout.addWidget(self.button_widget)

        # import dialog size hint
        self.setFixedWidth(width + 20)
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)
        self.actions_container.setFixedWidth(width)

        self.actions_container.setHideName(True)

        self._clicked_btn = -1

    def onSelect(self):
        self._clicked_btn = 1
        self.close()

    def onDefault(self):
        self.actions_container.getCurrentActionWidget().resetSettingsToDefault()

    def onCancel(self):
        self._clicked_btn = -1
        self.close()

    def exec(self):
        if self.actions_container.isEmpty():
            print("Container has no actions, using defaults...")
            self._clicked_btn = 0
        else:
            print(f"Current Widget Height: {self.actions_container.stacked_widget.size().height()}")
            super().exec()
        return self._clicked_btn

class ExportDialog(ImportDialog):
    def __init__(self, parent: QtWidgets.QWidget, schema:dict, actions:List[action_utils.MagicAction], file_format:str, show_preview:bool, width:int = 550):
        filtered_actions = [a for a in actions if a.file_format == file_format]
        print(f"Export Action for {file_format}: {filtered_actions}")
        super().__init__(parent, schema, [filtered_actions[0]], show_preview, width) # we only want one action
        self.setWindowTitle(f"{file_format} Export Settings")
        self.select_btn.setText("Export")
        self.select_btn.setToolTip("Export 3D file with the current settings.")
        self.cancel_btn.setToolTip("Cancel export.")
        self.actions_container.setHideDescription(True)

    def exec(self):
        if self.actions_container.isEmpty():
            print("Container has no actions, using defaults...")
            self._clicked_btn = 0
        elif not self.actions_container.getCurrentActionWidget().getSettingWidgets():
            print("Action has no settings, using defaults...")
            self._clicked_btn = 0
        else:
            super().exec()
        return self._clicked_btn
