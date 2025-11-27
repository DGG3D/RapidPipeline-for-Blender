import os
from typing import Any, List, Tuple
from PySide6 import QtCore, QtWidgets, QtGui
from abc import abstractmethod

import utils as pyside_utils

class BaseProperty:
    def __init__(self, name:str, setting:dict, schema:dict, default:Any):
        self.setting_name = name
        self.setting_title = setting.get("name", schema.get("title", name))
        self.setting_schema = schema
        self.default_value = default
        self.setting = setting
        self.setting_path = setting.get("path", "")

    @abstractmethod
    def setSettingValue(self, value):
        pass

    @abstractmethod
    def getSettingValue(self):
        pass

    @abstractmethod
    def resetSettingDefault(self):
        self.setSettingValue(self.default_value)

    def setTooltipToSetting(self, widget:QtWidgets.QWidget) -> str:
        """
        If a schema description is available, set it as a tooltip to a specific widget.
        """
        tooltip = self.setting.get("description", self.setting_schema.get("description", ""))
        if tooltip:
            widget.setToolTip(tooltip)

class StringProperty(BaseProperty, QtWidgets.QLineEdit):
    def __init__(self, name:str, setting:dict, schema:dict, default:str):
        BaseProperty.__init__(self, name, setting, schema, default)
        QtWidgets.QLineEdit.__init__(self)

        if self.default_value is None:
            self.default_value = ""

        self.setText(self.default_value)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.setClearButtonEnabled(True)
        self.setTooltipToSetting(self)

    def setSettingValue(self, value: str):
        self.setText(value)

    def getSettingValue(self) -> str:
        return self.text()

class BooleanProperty(BaseProperty, QtWidgets.QCheckBox):
    def __init__(self, name:str, setting:dict, schema:dict, default:bool):
        BaseProperty.__init__(self, name, setting, schema, default)
        QtWidgets.QCheckBox.__init__(self)

        if self.default_value is None:
            self.default_value = False

        self.setText(self.setting_title)
        self.setChecked(self.default_value)
        self.setTooltipToSetting(self)

    def setSettingValue(self, value: bool):
        self.setChecked(value)

    def getSettingValue(self) -> bool:
        return self.isChecked()

class ToggleableObject(BooleanProperty):
    def __init__(self, name:str, setting:dict, schema:dict):
        default = setting.get("toggled", False)
        super().__init__(name, setting, schema, default)

class IntegerProperty(BaseProperty, QtWidgets.QSpinBox):
    def __init__(self, name:str, setting:dict, schema:dict, default:float):
        BaseProperty.__init__(self, name, setting, schema, default)
        QtWidgets.QSpinBox.__init__(self)

        self.spinner_minimum = self.setting_schema.get("minimum", 0)
        self.spinner_maximum = self.setting_schema.get("maximum", pyside_utils.MAX_INT)
        if self.default_value is None:
            self.default_value = self.spinner_minimum

        # create spinner itself
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.setMinimum(self.spinner_minimum)
        self.setMaximum(self.spinner_maximum)
        self.setValue(self.default_value)
        self.setMinimumWidth(110)
        self.setTooltipToSetting(self)

    def setSettingValue(self, value: int) -> int:
        self.setValue(value)

    def getSettingValue(self) -> int:
        return self.value()

class FloatProperty(BaseProperty, QtWidgets.QDoubleSpinBox):
    def __init__(self, name:str, setting:dict, schema:dict, default:float):
        BaseProperty.__init__(self, name, setting, schema, default)
        QtWidgets.QDoubleSpinBox.__init__(self)

        self.spinner_minimum = self.setting_schema.get("minimum", 0.0)
        self.spinner_maximum = self.setting_schema.get("maximum", pyside_utils.MAX_FLOAT)
        if self.default_value is None:
            self.default_value = self.spinner_minimum

        # create spinner itself
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.setMinimum(self.spinner_minimum)
        self.setMaximum(self.spinner_maximum)
        self.setValue(self.default_value)
        self.setMinimumWidth(110)
        self.setTooltipToSetting(self)

    def setSettingValue(self, value: int) -> int:
        self.setValue(value)

    def getSettingValue(self) -> int:
        return self.value()

class PercentageProperty(FloatProperty):
    def __init__(self, name: str, setting:str, schema: dict, default:float):
        schema["type"] = "number"
        schema["maximum"] = 100.0
        schema["minimum"] = 0.0
        super().__init__(name, setting, schema, default)
        self.setSuffix(r"%")

class EnumProperty(BaseProperty, QtWidgets.QComboBox):
    def __init__(self, name:str, setting:dict, schema:dict, default:str):
        BaseProperty.__init__(self, name, setting, schema, default)
        QtWidgets.QComboBox.__init__(self)

        self.enum_elements: List[str] = self.setting_schema["enum"]
        if self.default_value is None:
            self.default_value = self.enum_elements[0]

        # create combobox itself
        self.addItems(self.enum_elements)
        self.setCurrentIndex(self.enum_elements.index(self.default_value))
        self.setMinimumWidth(110)
        self.setTooltipToSetting(self)

    def setSettingValue(self, value: str):
        if value not in self.enum_elements:
            raise ValueError(f"Invalid enum value '{value}' provided, accepted values: {self.enum_elements}")
        self.setCurrentIndex(self.enum_elements.index(value))

    def getSettingValue(self) -> str:
        return self.enum_elements[self.currentIndex()]

def getPropertyWidget(name:str, setting:str, schema: dict, default:Any) -> Tuple[str, BaseProperty]:
    schema_type = schema.get("type", None)
    setting_widget = None
    if schema_type == "integer":
        setting_widget = IntegerProperty(name, setting, schema, default)
    elif schema_type == "number":
        setting_widget = FloatProperty(name, setting, schema, default)
    elif schema_type == "boolean":
        setting_widget = BooleanProperty(name, setting, schema, default)
    elif schema_type == "string":
        setting_widget = StringProperty(name, setting, schema, default)
    elif "enum" in schema:
        setting_widget = EnumProperty(name, setting, schema, default)
    elif schema_type == "object" and schema.get("toggleable", False):
        setting_widget = ToggleableObject(name, setting, schema)
    else:
        raise NotImplementedError(f"The type for {name} has not been implemented.\nSchema:{schema}")

    # boolean properties already show their own titles
    if isinstance(setting_widget, BooleanProperty):
        return "", setting_widget
    else:
        return setting_widget.setting_title, setting_widget
