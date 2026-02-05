import os
from typing import List, Dict
import webbrowser
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    PYSIDE_VERSION = 2
import copy

from magic_actions import utils as action_utils
from pyside_common import utils as pyside_utils
from pyside_common import setting_widgets


class MagicActionWidget(QtWidgets.QWidget):
    def __init__(self, parent:QtWidgets.QWidget, action:action_utils.MagicAction, schema:dict):
        super().__init__(parent)
        self.main_action_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_action_layout)

        # action label
        print(f"Creating UI for Action: {action.name}")
        self.main_action_layout.addSpacing(5)
        self.name_label = QtWidgets.QLabel(action.name, alignment=QtCore.Qt.AlignLeft)
        self.name_label.setStyleSheet('font-size: 10pt;font-weight:bold')
        self.main_action_layout.addWidget(self.name_label, alignment=QtCore.Qt.AlignLeft)
        self.main_action_layout.addSpacing(5)

        # create base description widget
        self.preview_widget = QtWidgets.QWidget()
        self.preview_layout = QtWidgets.QHBoxLayout()
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_widget.setLayout(self.preview_layout)
        self.main_action_layout.addWidget(self.preview_widget)

        # create widget for video/gif, if file is present
        video_size = QtCore.QSize(200, 112)
        self.video_label = None
        if os.path.isfile(action.gif_path):
            self.video_label = pyside_utils.Gif(action.gif_path, video_size)
            self.preview_layout.addWidget(self.video_label, 1)

        self.description_widget = QtWidgets.QWidget()
        self.description_layout = QtWidgets.QVBoxLayout()
        self.description_layout.setContentsMargins(0, 0, 0, 0)
        self.description_widget.setLayout(self.description_layout)
        self.preview_layout.addWidget(self.description_widget, 1)

        # action description
        self.description_label = QtWidgets.QLabel(action.description[:200]) # TODO: testing...
        self.description_label.setWordWrap(True)
        self.description_layout.addWidget(self.description_label)

        # create link, if needed
        self.link_address = action.meta.get("read_more", "")
        if self.link_address:
            self.link_address = action.meta["read_more"]
            link_tooltip = "Opens documentation page for the current action."
            self.description_link = pyside_utils.LinkLabel("Read More", self.link_address, self.openLinkOnBrowser, link_tooltip)
            self.description_layout.addWidget(self.description_link, alignment=QtCore.Qt.AlignLeft)

        # add widget for video and description
        self.settings_widget = QtWidgets.QWidget()
        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_widget.setLayout(self.settings_layout)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)

        exposed_options : list = action.meta.get("exposed_options", [])

        self.main_action_layout.addSpacing(5)
        self.main_action_layout.addWidget(self.settings_widget)
        self.main_action_layout.addSpacing(5)

        self.__all_setting_widgets : Dict[str, setting_widgets.BaseProperty] = {}
        for setting in list(exposed_options):
            if not isinstance(setting, dict):
                exposed_options.remove(setting)
                continue
            setting_path = setting.get("path", None)
            if not setting_path:
                exposed_options.remove(setting)
                continue

            # get default value from loaded preset, and setting schema from schema
            # schema default will take effect when config preset doesn't have a value
            schema_property, name = action_utils.getSchemaPropertyFromPath(schema, setting_path)
            if not schema_property:
                raise ValueError(f"Unable to find the magic action in the path: {setting_path}")
            default = action_utils.getSettingValueFromPath(action.config, setting_path, schema_property.get("default", None), setting_path)

            # create widget
            setting_title, setting_widget = setting_widgets.getPropertyWidget(name, setting, schema_property, default)
            self.__all_setting_widgets[setting_path] = setting_widget

            action_widget = QtWidgets.QWidget()
            action_layout = QtWidgets.QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_widget.setLayout(action_layout)
            if setting_title:
                action_layout.addWidget(QtWidgets.QLabel(setting_title), 1, alignment=QtCore.Qt.AlignRight)
            else:
                action_layout.addWidget(QtWidgets.QWidget(), 1)
            action_layout.addSpacing(4)
            action_layout.addWidget(setting_widget, 1)
            self.settings_layout.addWidget(action_widget)

        if not exposed_options:
            self.settings_layout.addWidget(QtWidgets.QLabel("No settings are exposed for the current Action."))

        # button with icon - note that this is *not* added to the layout of this widget
        # this button will refer to the current MagicActionWidget
        button_name = action.meta.get("button_name", action.name)
        self.__magic_button = pyside_utils.IconButton(button_name, icon_path=action.icon_dark_path)

        self.main_action_layout.setAlignment(QtGui.Qt.AlignTop) # align widgets to top

        self.magic_action : action_utils.MagicAction = action

        self.main_action_layout.setAlignment(QtGui.Qt.AlignTop) # align widgets to top


    def showSettings(self, show_flag:bool):
        self.settings_widget.setHidden(not show_flag)

    def getMagicButton(self) -> QtWidgets.QWidget:
        return self.__magic_button

    def setShowPreview(self, show_flag:bool):
        if self.video_label:
            self.video_label.setHidden(not show_flag)

    def openLinkOnBrowser(self):
        webbrowser.open(self.link_address)

    def getSettingValues(self) -> dict:
        """
        Retrives the current values for all setting widgets for the current magic action.
        """
        setting_values = {}
        for setting_path in self.__all_setting_widgets:
            setting_values[setting_path] = self.__all_setting_widgets[setting_path].getSettingValue()
        return setting_values

    def getSettingWidgetFromPath(self, setting_path:str):
        return self.__all_setting_widgets[setting_path]

    def getSettingWidgets(self):
        return self.__all_setting_widgets

    def resetSettingsToDefault(self):
        for setting_path in self.__all_setting_widgets:
            self.__all_setting_widgets[setting_path].resetSettingDefault()

class ActionsContainer(QtWidgets.QWidget):
    def __init__(self, use_scrollable:bool = True, column_count:int = 2):
        super().__init__()

        self.__current_action = 0
        self.__use_scrollable = use_scrollable

        self.customButtonStyle = ""

        self.magic_widgets : List[MagicActionWidget] = []
        self.magic_buttons : List[pyside_utils.IconButton] = []

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.button_group = QtWidgets.QButtonGroup()

        # widget for magic action buttons with flow/resizable layout
        self.buttons_widget = QtWidgets.QWidget()
        self.buttons_layout = QtWidgets.QGridLayout()
        self.buttons_widget.setLayout(self.buttons_layout)
        self.buttons_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.buttons_widget)

        self.stacked_widget = QtWidgets.QStackedWidget()
        if self.__use_scrollable:
            self.scroll_area = QtWidgets.QScrollArea()
            self.main_layout.addWidget(self.scroll_area)
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setWidget(self.stacked_widget)
            self.scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.MinimumExpanding)
        else:
            self.main_layout.addWidget(self.stacked_widget)

        self.stacked_widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.MinimumExpanding)

        self.button_group.idClicked.connect(self.actionChanged)

        self.__column_count = column_count

    def isEmpty(self) -> bool:
        return not self.magic_buttons or not self.magic_widgets

    def actionChanged(self, btn_id:int, skip_default_recolor:bool = False):
        # set previously selected button to default color, set newly selected to dark blue
        if self.isEmpty():
            return

        if not skip_default_recolor:
            self.magic_buttons[self.__current_action].setDefaultColor()
        self.magic_buttons[btn_id].setCustomColor(QtGui.QColor("#496a93"))

        self.__current_action = btn_id
        action_widget = self.magic_widgets[btn_id]
        print(f"Button Selected: {btn_id} - {action_widget.magic_action.name}")
        self.stacked_widget.setCurrentWidget(action_widget)
        if self.__use_scrollable:
            self.resetScrollBar()

    def resetScrollBar(self):
        self.scroll_area.verticalScrollBar().setValue(0)

        # set stacked widget to the size of the current widget
        current_height = self.getCurrentActionWidget().sizeHint().height()
        self.stacked_widget.setFixedHeight(current_height)

    def setShowPreview(self, show_flag:bool):
        for action in self.magic_widgets:
            if action.video_label:
                action.setShowPreview(show_flag)

    def setHideName(self, show_flag:bool):
        for action in self.magic_widgets:
            action.name_label.setHidden(show_flag)

    def setHideDescription(self, show_flag:bool):
        for action in self.magic_widgets:
            action.preview_widget.setHidden(show_flag)

    def getCurrentAction(self) -> action_utils.MagicAction:
        return self.magic_widgets[self.__current_action].magic_action

    def getCurrentActionWidget(self) -> MagicActionWidget:
        return self.magic_widgets[self.__current_action]

    def getSettingsFromCurrentAction(self) -> dict:
        # get current action and action widget
        current_action = self.getCurrentAction()
        current_widget = self.getCurrentActionWidget()

        # get input config and settings from UI
        # if we don't make a deep copy here, we are altering the dict of the action itself
        input_config = copy.deepcopy(current_action.config)
        current_settings = current_widget.getSettingValues()

        # override values from input with values from UI
        for path in current_settings:
            setting_widget = current_widget.getSettingWidgetFromPath(path)

            is_toggleable = isinstance(setting_widget, setting_widgets.ToggleableObject)
            if not is_toggleable:
                action_utils.setSettingValueFromPath(input_config, path, current_settings[path], path)
            elif is_toggleable and not current_settings[path]:
                action_utils.removeSettingFromPath(input_config, path, path)

        return input_config

    def clearContainer(self):
        for button in self.magic_buttons:
            self.button_group.removeButton(button)
        for i in reversed(range(self.buttons_layout.count())):
            self.buttons_layout.itemAt(i).widget().setParent(None)
        self.magic_buttons.clear()

        for widget in self.magic_widgets:
            self.stacked_widget.removeWidget(widget)
            widget.destroy()
        self.magic_widgets.clear()


    def applyCustomButtonStyle(self):
        if self.customButtonStyle == "":
            return
        for mbutton in self.magic_buttons:
            mbutton.setStyleSheet(self.customButtonStyle)


    def setCustomButtonStyle(self, stylesheet):
        self.customButtonStyle = stylesheet
        self.applyCustomButtonStyle()


    def populateContainer(self, schema:dict, magic_actions:List[action_utils.MagicAction]):
        # delete any current widgets and buttons
        self.clearContainer()

        self.__schema = schema
        self.__actions = magic_actions

        # collect magic actions and create widgets
        for idx, action in enumerate(magic_actions):
            print(action.name)
            action_widget = MagicActionWidget(self, action, schema)
            action_widget.setHidden(True)
            magic_button = action_widget.getMagicButton()

            magic_button.setMinimumHeight(28)

            column_idx = idx % self.__column_count
            row_idx = int(idx / self.__column_count)
            self.buttons_layout.addWidget(magic_button, row_idx, column_idx)
            self.magic_buttons.append(magic_button)

            # add button to group and set custom id as index
            self.button_group.addButton(magic_button, id=idx)

            self.magic_widgets.append(action_widget)
            self.stacked_widget.addWidget(action_widget)

        # update custom style, if any, after populating
        self.applyCustomButtonStyle()

        # update widget sizes after populating
        self.buttons_widget.update()
        self.buttons_widget.updateGeometry()
        self.buttons_widget.adjustSize()

        self.stacked_widget.update()
        self.stacked_widget.updateGeometry()
        self.stacked_widget.adjustSize()

        if self.__use_scrollable:
            self.scroll_area.update()
            self.scroll_area.updateGeometry()
            self.scroll_area.adjustSize()

        if not self.isEmpty():
            # when populating, we don't want to change the color of the current button
            self.actionChanged(0, skip_default_recolor=True)

            # if we only have one action we don't need to show its button
            if len(self.magic_buttons) == 1 or len(self.magic_widgets) == 1:
                self.buttons_widget.setHidden(True)
            else:
                self.buttons_widget.setHidden(False)

