"""
The RapidPipeline 3D Processor Plugin for Blender
Copyright 2024, Darmstadt Graphics Group GmbH <info@dgg3d.com>
Licensed under GNU GPL-3.0-or-later.

This file is part of The RapidPipeline 3D Processor Plugin for Blender.
The RapidPipeline 3D Processor Plugin for Blender is free software:
you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The RapidPipeline 3D Processor Plugin for Blender is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License (under licenses/processorpluginblender.txt)
for more details.

You should have received a copy of the GNU General Public License
along with The RapidPipeline 3D Processor Plugin for Blender. If not,
see <https://www.gnu.org/licenses/>.

Note that the RapidPipeline 3D Processor Engine CLI ("rpde") is a copyrighted
software governed by its own EULA. The RapidPipeline 3D Processor Engine CLI
does NOT make use of the 3D Processor Plugin For Blender and does NOT follow
the GNU GPL-3.0 license. See the RapidPipeline 3D Processor EULA file (under
rpde/EULA_RapidPipelineEngine.rtf after installation, or during the install
process) for further information.
"""

import os
import subprocess
import traceback
from abc import abstractmethod
from sys import platform
from typing import Any, Dict, List

import bpy  # type: ignore

from .json_utils import JSonUtils
from .scene_utils import blend_scene_getattr, blend_scene_setattr, blend_scene_setattr_enum


def parseTextFile(file_path: str, encoding: bool = "utf-8") -> List[str]:
    """
    Utility function to open a text file in read mode, and parse it into
    a list of strings/lines.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file {file_path} doesn't exist.")

    with open(file_path, "r", encoding=encoding) as file_handle:
        return file_handle.readlines()


class ProcessorPlugin:
    PLUGIN_FOLDER = os.path.dirname(__file__)
    RESOURCES_FOLDER = os.path.join(os.path.dirname(__file__), "resources")
    RPDE_PATH = os.path.join(os.path.dirname(__file__), "rpde")
    SCHEMA_PATH = os.path.join(RESOURCES_FOLDER, "schema.json")
    SOLVED_SCHEMA_PATH = os.path.join(RESOURCES_FOLDER, "schema_solved.json")
    METADATA_PATH = os.path.join(PLUGIN_FOLDER, "plugin_metadata.json")

    @staticmethod
    def getRPDEPath() -> str:
        """
        Returns path of RPDE executable from default installation folder
        """
        os.environ["RPD_HOOPS_DIR"] = os.path.join(ProcessorPlugin.RPDE_PATH, 'hoops')
        if "RPDE_PLUGIN_CLI" not in os.environ or not os.environ["RPDE_PLUGIN_CLI"].endswith(".exe"):
            exec = 'rpde' if 'darwin' in platform else 'rpde.exe'
            os.environ["RPDE_PLUGIN_CLI"] = os.path.join(ProcessorPlugin.RPDE_PATH, exec)
        return os.environ["RPDE_PLUGIN_CLI"]

    __schema_solved = {}

    @classmethod
    def loadSchema(cls):
        """
        Reads schema file from predetermined path and updates class variable with file contents.
        """
        schema = JSonUtils.loadJSON(cls.SCHEMA_PATH)
        schema_defs = JSonUtils.getSchemaDefs(schema)
        schema_solved, _ = JSonUtils.solveSchemaRefs(schema, schema_defs)
        JSonUtils.saveJSON(schema_solved, cls.SOLVED_SCHEMA_PATH)

        cls.__schema_solved.clear()
        cls.__schema_solved.update(schema_solved)

    @classmethod
    def getSolvedSchema(cls) -> dict:
        return cls.__schema_solved

    __metadata = {}

    @classmethod
    def loadPluginMetadata(cls) -> bool:
        """
        Reads JSon Metadata file for plugin, containing version as well as host applciation info.
        Returns True if successful, or False if there was an error or the file could not be found.
        """
        if not os.path.isfile(cls.METADATA_PATH):
            return False

        try:
            metadata = JSonUtils.loadJSON(cls.METADATA_PATH)
        except Exception:
            return False

        cls.__metadata.clear()
        cls.__metadata.update(metadata)
        return True

    @classmethod
    def getMetadata(cls) -> dict:
        return cls.__metadata

    @classmethod
    def isDarkTheme(cls) -> bool:
        # overrides dark theme, useful in certain apps such as blender
        if "RPDP_PROCESSOR_DCC_DARK_THEME" in os.environ:
            return os.environ["RPDP_PROCESSOR_DCC_DARK_THEME"] == "1"
        return False

    @classmethod
    def getLogoPath(cls) -> str:
        # the logo in use differs depending on the color scheme of the app
        logo_color = "black" if not cls.isDarkTheme() else "white"
        return f":/logos/logo_{logo_color}.svg"

    @classmethod
    def getLogoLabel(cls, width: int = 400) -> str:
        """
        Loads image and creates QLabel.
        """
        logo_label = "TODO"
        return logo_label

    ui_rules = {}

    @classmethod
    def loadUIRules(cls):
        # uses default file, if no override was provided
        if "RPDP_PROCESSOR_DCC_RULES" not in os.environ:
            default_rules_path = os.path.join(os.path.dirname(__file__), "resources", "ui_rules.json")
            os.environ["RPDP_PROCESSOR_DCC_RULES"] = default_rules_path

        # read UI rules file, if any
        cls.ui_rules.update(JSonUtils.loadJSON(os.environ["RPDP_PROCESSOR_DCC_RULES"]))

    widgets_from_path: Dict[str, "UIElement"] = {}
    LEVELS = ["basic", "advanced", "expert"]
    dividers_by_level: Dict[str, List[Any]] = {k: [] for k in LEVELS}

    @classmethod
    def getAllWidgets(cls) -> List["UIElement"]:
        return list(cls.widgets_from_path.values())

    @classmethod
    def getWidgetByPath(cls, path: str) -> List["UIElement"]:
        return cls.widgets_from_path.get(path, None)

    @classmethod
    def trackWidget(cls, path: str, widget: "UIElement"):
        widget_path = widget.path
        if widget_path in cls.widgets_from_path:
            raise ValueError(f"Unable to create UI Element {path}, path already exists/is not unique.")
        else:
            cls.widgets_from_path[widget_path] = widget

    @classmethod
    def trackDivider(cls, level: str, divider: Any):
        if level not in cls.dividers_by_level:
            cls.dividers_by_level[level] = []
        cls.dividers_by_level[level].append(divider)

    @classmethod
    def getAllDividersByLevel(cls) -> Dict[str, List[Any]]:
        return cls.dividers_by_level

    @classmethod
    def getAllDividersForLevel(cls, level: str) -> List[Any]:
        return cls.dividers_by_level[level]

    @classmethod
    def reset(cls):
        """
        Resets lists of widgets and dividers.
        TODO: this should use proper deletion methods for cleaning up/delete widgets and free up resources.
        """
        cls.widgets_from_path.clear()
        cls.dividers_by_level.clear()

    @classmethod
    def getChildElements(cls, path_components: List[str]) -> List["UIElement"]:
        """
        Returns all UI elements that are children of a given UIElement path.
        The list is ordered descending by how far away the child nodes are from the root.
        """
        path = "/".join(path_components[:-1])  # ignore element itself
        child_elements = list(
            {k: cls.widgets_from_path[k] for k in cls.widgets_from_path if k.startswith(path)}.values()
        )
        child_elements.sort(key=lambda x: len(x.path_components), reverse=True)
        return child_elements

    @classmethod
    def getAllParentElements(cls, path_components: List[str]) -> List["UIElement"]:
        """
        Returns all UI elements that are parents of a given UIElement path.
        The list is ordered descending by how far away the child nodes are from the root.
        """
        if not path_components:
            return []
        path_components = path_components[:-1]  # ignore element itself
        if not path_components:
            return []
        parent_elements = [
            cls.widgets_from_path["/".join(path_components[: i + 1])] for i in range(len(path_components))
        ]
        parent_elements.sort(key=lambda x: len(x.path_components), reverse=True)
        return parent_elements


class SettingsValidator:
    def __init__(self) -> None:
        self.is_valid = False

    def validate(self, file_path: str) -> bool:
        """
        Validate a settings file with RPDE, through a subprocess.
        Returns True if the settings are valid, or False otherwise.
        """
        self.is_valid = False
        try:
            rpde_path = ProcessorPlugin.getRPDEPath()
            p = subprocess.Popen(
                [rpde_path, "--read_config", file_path], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            _ = p.wait()
            return True
        except Exception:
            print(traceback.format_exc())
            return False

class UserDialog:
    """
    Definition of helper functions of modal dialogs for user interaction.
    """

    @staticmethod
    def okWarning(parent: Any, title: str, label: str):
        """
        Modal warning message dialog, offering only an OK button to the user.
        """

    @staticmethod
    def okCancelWarning(parent: Any, title: str, label: str) -> bool:
        """
        Modal warning message dialog, returning True if the user pressed OK,
        or False if the user pressed Cancel.
        """
        return None

    @staticmethod
    def yesNo(parent: Any, title: str, label: str) -> bool:
        """
        Modal question message dialog, returning True if the user pressed Yes,
        or False if the user pressed No.
        """
        return None

    @staticmethod
    def okInfo(parent: Any, title: str, label: str):
        """
        Modal information message dialog, offering only an OK button to the user.
        """
        return None

    @staticmethod
    def critical(parent: Any, title: str, label: str, details: str = None):
        """
        Modal critical error dialog, offering only an OK button to the user.
        Optionally, adds details regarding the error.
        """
        return None

    @staticmethod
    def errorRetry(parent: Any, title: str, label: str, details: str = None) -> bool:
        """
        Modal Retry/Cancel error dialog, returns True if user pressed Retry,
        or False if user pressed Cancel. Optionally, adds details regarding the error.
        """
        return None


class UIElementOperator(bpy.types.Operator):
    bl_idname = "processor.ui_element"
    bl_description = "UI_element"
    bl_label = "UI_Element_Label"
    bl_options = {'REGISTER', 'UNDO'}


    def execute(self, context:bpy.types.Context) -> set[str]:

        print("UI ELEMENT EXECUTE")
        print(f"UI Element name: {self.bl_label}")

        return {'FINISHED'}

class UIElement():
    def __init__(
            self, name: str, settingid:str, parent: "UIElement",
            schema: dict={}, uuid_dict:dict={}, type_required: str = "") -> None:
        super(UIElement, self).__init__()
        self.name: str = name
        self.schema: dict = schema
        self.parent_element: "UIElement" = parent
        self.title: str = schema.get("title", name)
        self.type: str = schema.get("type", None)
        self.settingid: str = settingid
        self.hidden_settings: list = ProcessorPlugin.ui_rules.get("hideSettings", [])
        self.drawn: bool = False
        self.level = self.getLevel()
        self.path = self.getPath()
        self.default = schema.get("default", None)
        self.uuid_dict = uuid_dict
        self.panel = None

    def isdrawn(self) -> bool:
        if not self.settingid or self.settingid in self.hidden_settings:
            return False

        levels = {"basic": 1, "advanced": 2, "expert": 3}

        if levels[self.level] > levels[bpy.context.scene.level]: #TODO get level from context scene element
            return False

        if self.parent_element:
            from .compound_elements import SimpleContainer, TabElement

            #check if correct tab is selected
            if isinstance(self.parent_element, SimpleContainer):
                current_tab = bpy.context.scene.tabelements
                if not current_tab == self.parent_element.settingid:
                    return False

            #case for Oneof widgets directly in Container
            elif isinstance(self.parent_element, TabElement):
                current_tab = bpy.context.scene.tabelements
                if not isinstance(self, SimpleContainer):
                    if not current_tab == self.settingid:
                        return False


            #Check if correct oneof widget is selected
            if 'oneOf' not in self.schema:
                if 'oneOf' in self.parent_element.schema:
                    oneof_path = self.parent_element.path.copy()
                    oneof_path.append("Oneof")
                    attribute_env, oneof_selection = blend_scene_getattr(
                        bpy.context.scene, self.parent_element.parent_element.settingid,
                        self.uuid_dict, "oneOf", oneof_path)
                    oneof_attribute = getattr(attribute_env, oneof_selection)
                    if not oneof_attribute == self.settingid:
                        return False

            #check if parent is drawn
            if not isinstance(self, SimpleContainer):
                parent_draw = self.parent_element.isdrawn()
                if not parent_draw:
                    return False

        return True

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        self.drawn = self.isdrawn()

    @abstractmethod
    def setDisabledExport(self):
        pass

    def printPath(self):
        print(self.path)

    def validateSchema(self):
        """
        Validates UIElement creation against its schema properties

        NOTE: For certain cases, e.g. oneOf and enum, this function should be overriden.
        """
        type_provided = self.schema["type"]
        if not type_provided == self.type_required:
            class_name = self.__class__.__name__
            raise ValueError(f"Incorrect schema type {type_provided} for {class_name}: {self.type_required} required.")

    def setTooltipToWidget(self, widget: Any):
        """
        If a schema description is available, set it as a tooltip to a specific widget.
        """
        if self.schema.get("description", None):
            widget.setToolTip(self.schema["description"])

    # returns the value of a given UI element
    # if the value is a boolean than returns that boolean if the setting is 'toggleable'
    # otherwise returns True
    def getSettings(self) -> Any:
        try:
            setting = getattr(*self.getValue(bpy.context))
            if setting == self.default and self.isToggleable():
                return None
        except Exception:
            print(f"Warning: could not get settings for {self.settingid}")
            return None
        return setting

    @abstractmethod
    def setSettings(self, settings):  # noqa: ANN001
        """
        Updates settings of the current UI component and activates it.
        """
        self.setValue(settings, context=None)

        # make sure to set toggable properties to checked - if the setting was changed, we want it
        if self.isToggleable():
            self.setIgnoreExport(True)

    def setValue(self, value:Any, context:bpy.types.Context=None) -> bool:
        if not self.settingid or self.settingid in self.hidden_settings:
            return False

        if value is None:
            return False
        if self.type == 'object':
            blend_scene_setattr(
                *self.getValue(context), bool(value))
        if self.type == 'array':        #special case for colors: we need to strip the alpha color
            value = value[0:3]
        if 'enum' in self.schema:
            enum_options = []
            for element in self.schema['enum']:
                enum_options.append((element,)*3)
            blend_scene_setattr_enum(bpy.types.Scene, self.settingid, self.uuid_dict,
                bpy.props.EnumProperty(items=enum_options), self.path)
            blend_scene_setattr(
                *self.getValue(context), value)
        else:
            blend_scene_setattr(
                *self.getValue(context), value)
        return True

    def getValue(self, context:bpy.types.Context)-> tuple[Any,str]:
        return blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)

    def setDefaultValue(self, context:bpy.types.Context):
        self.setValue(self.default, context)

        # make sure to set toggable properties to unchecked
        if self.isToggleable():
            self.setIgnoreExport(False)

    def getParentElement(self) -> "UIElement":
        return self.parent_element

    def getPath(self) -> List[str]:
        if self.parent_element:
            if self.parent_element.path:
                out_list = self.parent_element.path.copy()
                if self.name:
                    out_list.append(self.name)
                return out_list
        if not self.name:
            return
        return [self.name]

    def isToggleable(self) -> bool:
        if self.parent_element and self.name in self.parent_element.schema.get("required", []):
            return False
        return self.schema.get("toggleable", False)

    def getLevel(self) -> str:
        return self.schema.get("level", ProcessorPlugin.LEVELS[0])

    def setIgnoreExport(self, value: bool):
        pass

    def ignoreSettingExport(self) -> bool:
        """
        Returns True if the settings of the current element should not be exported.
        """
        # we never ignore the export of required settings, even if they are the same as the default
        if self.name in self.parent_element.schema.get("required", []):
            return False

        # if the current element value is similar to its default, ignore
        if "default" in self.schema and self.schema["default"] == self.getValue(bpy.context):
            return True

        # we never ignore the settings if the UI element is required in the output
        if not self.isToggleable():
            return False

        # ignore_export flag is set by the respective checkboxes of each UI element
#        return not self.ignore_widget.isChecked()

clss = (
    UIElementOperator,
    )

reg, unreg = bpy.utils.register_classes_factory(clss)

def register():
    reg()

def unregister():
    unreg()

