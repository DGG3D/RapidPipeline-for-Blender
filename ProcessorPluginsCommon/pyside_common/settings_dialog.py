import os
from typing import List, Callable, Any
from PySide6 import QtWidgets

from pyside_common import utils as pyside_utils
from magic_actions import utils as action_utils

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, default_version:str, current_version:str, action_versions:List[str], current_show:bool, plugin_root:str):
        super().__init__(parent)

        # TODO: we need to add save/load of settings
        self.__settings_meta = {}
        self.__settings_from_file = {}
        self.__settings_file = os.path.join(plugin_root, "settings_file.json")
        if os.path.isfile(self.__settings_file):
            print(f"Loading Plugin Settings from: {self.__settings_file}")
            self.__settings_from_file = action_utils.loadJSON(self.__settings_file)

        # set window icon and title
        self.setWindowIcon(pyside_utils.getLogoIcon())
        self.setWindowTitle("Plugin Settings")

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)

        # empty settings container
        self.settings_container = QtWidgets.QWidget()
        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_container.setLayout(self.settings_layout)
        self.main_layout.addWidget(self.settings_container)

        # create version widget
        self.version_widget = QtWidgets.QWidget()
        self.version_layout = QtWidgets.QGridLayout()
        self.version_widget.setLayout(self.version_layout)

        # create combobox itself
        self.version_layout.addWidget(QtWidgets.QLabel("Magic Actions Version:"), 0, 0)
        self.version_selection_widget = QtWidgets.QComboBox()
        self.version_selection_widget.addItems(action_versions)
        self.version_selection_widget.setMinimumWidth(110)
        self.version_layout.addWidget(self.version_selection_widget, 0, 1)
        def setVersion(version_str:str):
            self.version_selection_widget.setCurrentIndex(action_versions.index(version_str))

        # show preview checkbox
        self.show_preview_widget = QtWidgets.QCheckBox("Show Magic Action Previews")
        self.show_preview_widget.setChecked(current_show) # TODO: this value should pick up from the settings file

        # create button widget
        self.button_widget = QtWidgets.QWidget()
        self.button_layout = QtWidgets.QGridLayout()
        self.button_widget.setLayout(self.button_layout)
        self.main_layout.addWidget(self.button_widget)

        # create and add buttons
        self.apply_btn = QtWidgets.QPushButton("Apply Settings")
        self.button_layout.addWidget(self.apply_btn, 0, 0)
        self.apply_btn.pressed.connect(self.onApply)

        self.default_btn = QtWidgets.QPushButton("Restore Defaults")
        self.button_layout.addWidget(self.default_btn, 0, 1)
        self.default_btn.pressed.connect(self.onDefault)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.button_layout.addWidget(self.cancel_btn, 0, 2)
        self.cancel_btn.pressed.connect(self.onCancel)

        self.__clicked_btn = -1

        # append basic settings to the settings container
        self.appendSetting("version", self.version_widget, self.version_selection_widget.currentText, setVersion, default_version)
        self.appendSetting("show_preview", self.show_preview_widget, self.show_preview_widget.isChecked, self.show_preview_widget.setChecked, True)
        self.setSettingToId("version", current_version)

    def getSettings(self) -> dict:
        settings = {}
        for setting_id in self.__settings_meta:
            settings[setting_id] = self.getSettingFromId(setting_id)
        return settings

    def getDefaultSettings(self) -> dict:
        settings = {}
        for setting_id in self.__settings_meta:
            settings[setting_id] = self.__settings_meta[setting_id]["default"]
        return settings

    def onApply(self):
        self.__clicked_btn = 1
        self.close()

    def onCancel(self):
        self.__clicked_btn = -1
        self.close()

    def onDefault(self):
        self.__clicked_btn = 0
        self.close()

    def appendSetting(self, setting_id:str, widget:QtWidgets.QWidget, get_setting_callback:Callable, set_setting_callback:Callable, default:Any):
        self.__settings_meta[setting_id] = {
            "id" : setting_id,
            "widget": widget,
            "get_function":get_setting_callback,
            "set_function":set_setting_callback,
            "default":default
        }
        self.settings_layout.addWidget(widget)

        # if we have the setting id in the settings file we use the value from there
        # otherwise, we use its default value
        if setting_id in self.__settings_from_file:
            set_setting_callback(self.__settings_from_file[setting_id])
        else:
            set_setting_callback(default)

    def setSettingToId(self, setting_id:str, value:Any):
        self.__settings_meta[setting_id]["set_function"](value)

    def getSettingFromId(self, setting_id:str) -> Any:
        return self.__settings_meta[setting_id]["get_function"]()

    def getSettingsFromDisk(self):
        return self.__settings_from_file

    def setSettingsFromDict(self, settings:dict):
        """
        Set a dictionary of settings. Settings that don't exist currently will take no effect.
        """
        for setting_id in settings:
            if setting_id not in self.__settings_meta:
                continue
            setting_value = settings[setting_id]
            self.__settings_meta[setting_id]["set_function"](setting_value)

    def saveSettingsToDisk(self):
        print(f"Save Plugin Settings to: {self.__settings_file}")
        action_utils.saveJSON(self.getSettings(), self.__settings_file)

    def exec(self):
        super().exec()
        return self.__clicked_btn
