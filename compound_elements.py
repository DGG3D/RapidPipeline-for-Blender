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

import traceback
from typing import Any, Dict, List

import bpy  # type: ignore
from bpy.types import Context, Panel, UILayout

from .basic_elements import (
    BooleanProperty,
    ColorPicker,
    EmptySchemaObject,
    EnumProperty,
    FloatProperty,
    IntegerProperty,
    StringProperty,
)
from .gui_commons import ProcessorPlugin, UIElement
from .scene_utils import (
    blend_create_prop,
    blend_scene_getattr,
    blend_scene_setattr,
    get_path,
    get_ui_element,
    get_uuid,
    set_uuid,
)

ui_elements_dict:dict[str, UIElement] = {} #key -> paths, value -> UIElement
def init_ui_element(
        name: str, settingid: str, parent: UIElement = None, uuid_dict:dict= {}, schema: dict = {}) -> UIElement:
    override_rules = ProcessorPlugin.ui_rules.get("overrideUIElement", {})
    created_property: UIElement = None
    try:
        if not schema:
            print(f"Warning: No schema object found for element {settingid}")
            return None

        #Oneof gets added to ui_elements but not returned as a child object
        # this is important since its not part of the settings itself but drawn to the UI
        if "oneOf" in schema:
            created_oneof = OneOfWidget(name, settingid, parent, uuid_dict, schema)
            if created_oneof.path:
                oneof_path = created_oneof.path.copy()
                oneof_path.append("Oneof")
                set_uuid(set(oneof_path))
                ui_elements_dict[get_uuid(oneof_path)] = created_oneof
                parent.child_elements.append(created_oneof)

        #case only for export
        if "items" in schema and settingid == "exportArray":
            init_ui_element(name, settingid, parent, uuid_dict, schema["items"])

        if "type" in schema:
            if schema["type"] == "boolean":
                created_property = BooleanProperty(name, settingid, parent, uuid_dict, schema)
            elif schema["type"] == "integer":
                created_property = IntegerProperty(name, settingid, parent, uuid_dict, schema)
            elif schema["type"] == "number":
                created_property = FloatProperty(name, settingid, parent, uuid_dict, schema)
            elif schema["type"] == "object":
                if schema.get("settingid", None) in override_rules.get("SimpleContainer", []):
                    created_property = SimpleContainer(name, settingid, parent, uuid_dict, schema)
                elif not schema.get("properties", None):
                    created_property = EmptyCompoundUIElement(name, settingid, parent, uuid_dict, schema)
                elif schema.get("settingid", None) in override_rules.get("TabElement", []):
                    created_property = TabElement(name, settingid, parent, uuid_dict, schema)
                elif schema.get("settingid", None) in override_rules.get("PopupOverrideElement", []):
                    created_property = PopupOverrideElement(name, settingid, parent, uuid_dict, schema)
                else:
                    created_property = GroupWidget(name, settingid, parent, uuid_dict, schema)
            elif schema["type"] == "array":
                if name.lower().endswith("color"):
                    created_property = ColorPicker(name, settingid, parent, uuid_dict, schema)
                elif name == "export":
                    created_property = FileExportType(name, settingid, parent, uuid_dict, schema)
            elif schema["type"] == "string":
                created_property = StringProperty(name, settingid, parent, uuid_dict, schema)
        elif "enum" in schema and schema["enum"]:
            created_property = EnumProperty(name, settingid, parent, uuid_dict, schema)
        elif "oneOf" in parent.schema:
            created_property = OneOfContainer(name, settingid, parent, uuid_dict, schema)
        else:
            print("no oneof, type or enum found. Creating empty schema object")
            created_property = EmptySchemaObject(name, settingid, parent, uuid_dict, schema)
    except Exception:
        # default: unsupported
        print(f"Unable to create Property {name}, type not implemented or invalid.")
        print(traceback.format_exc())
        print(traceback.print_stack())

    if created_property.path:
        set_uuid(path=(set(created_property.path)))
        ui_elements_dict[get_uuid(created_property.path)] = created_property
    return created_property

def get_ui_elements_dict() -> dict[str, UIElement]:
    return ui_elements_dict

class CompoundUIElement(UIElement):

    def __init__(self, name: str, settingid: str, parent: "UIElement",
                 schema: dict, uuid_dict:dict, type_required: str) -> None:
        super().__init__(name, settingid, parent, schema, uuid_dict, type_required)

        self.child_elements: List[UIElement] = []
        self.children_by_level: Dict[str, List[UIElement]] = {k: [] for k in ProcessorPlugin.LEVELS}
        self.level_dividers: Dict[str, List[Any]] = {}

    def validateSchema(self):
        if "properties" not in self.schema:
            class_name = self.__class__.__name__
            raise ValueError(f"Invalid schema for {class_name}, 'properties' required.")

    def createChildElements(self):
        """
        Create sub-elements, based on the current UIElement schema properties.
        """
        if isinstance(self, EmptyCompoundUIElement) and 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append('Oneof')
            #TODO maybe instead dont create children in Oneof widget at all and just create them here
            oneof:OneOfWidget = ui_elements_dict[get_uuid(oneof_path)]
            for element in oneof.child_elements.copy():
                self.child_elements.append(element)
                self.children_by_level[element.getLevel()].append(element)

        else:

            if "properties" not in self.schema:
                return
            for name in self.schema["properties"]:
                if name == 'version':
                    continue

                settingid = self.schema['properties'][name].get('settingid', 'settingid_not_found')
                child_element = init_ui_element(name, settingid, self, self.uuid_dict, self.schema["properties"][name])
                if not child_element:
                    continue

                self.child_elements.append(child_element)
                self.children_by_level[child_element.getLevel()].append(child_element)

    def setDisabledExport(self):
        for child in self.child_elements:
            child.setDisabled(not self.ignore_widget.isChecked())

    def setValue(self, value:Any, context:bpy.types.Context) -> bool:
        return super().setValue(bool(value), context)

    def get_env_uuid(self, context:bpy.types.Context)-> tuple[Any,str]:
        return super().get_env_uuid(context)

    def getSettings(self) -> dict:
        out_settings = {}
        if (getattr(*blend_scene_getattr(bpy.context.scene, self.path))) or (
            # check for empty properties specifically for "addcheckertexture"
            not self.isToggleable() and self.schema.get("properties", {}) != {}):
            for e in self.child_elements:
                if e.name and not e.ignoreSettingExport():
                    settings = e.getSettings()
                    if settings is not None:
                        if isinstance(settings, dict):
                            if bool(settings):
                                out_settings[e.name] = settings
                            else:
                                continue
                        else:
                            out_settings[e.name] = settings
                    else:
                        continue

            if not out_settings:
                if len(self.child_elements) >= 1:
                    # case for empty children of oneOfs (like with type:stl in export)
                    toggle_children = getattr(*blend_scene_getattr(bpy.context.scene, self.child_elements[0].path))
                    if toggle_children:
                        return {self.child_elements[0].name : {}}

            return out_settings
        else:
            return None

    def setSettings(self, settings: dict):
        """
        Updates settings of the current UI component and activates it.
        """
        child_by_name = {c.name: c for c in self.child_elements}
        for s in settings:
            child_by_name[s].setSettings(settings[s])

class SimpleContainerOperator(bpy.types.Operator):
    bl_idname = "processor.simplecontainer"
    bl_description = "RapidPipeline Tab"
    bl_label = "container_label"
    bl_options = {'REGISTER', 'UNDO'}

    settingid: bpy.props.StringProperty(options={'HIDDEN'}) # type: ignore

    def execute(self, context:bpy.types.Context) -> set[str]:
        context.scene.tabelements = self.settingid
        return {'FINISHED'}

class SimpleContainer(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return
        panel_layout = layout
        depress = context.scene.tabelements == self.settingid
        simple_container_operator = panel_layout.operator(
            SimpleContainerOperator.bl_idname,
            text=self.title,
            icon_value=getattr(context.scene, f"icon_{self.settingid}").icon_id,
            depress=depress)

        simple_container_operator.settingid = self.settingid

        if self.isToggleable(): #TODO
            pass
            #panel_layout.prop(self.ignore_widget, 0, self.layout.columnCount())

    def isToggleable(self) -> bool:
        return True

    def setDefaultValue(self, context:bpy.types.Context):
        self.setValue(False, context)

    def setValue(self, value:bool, context:bpy.types.Context):
        blend_scene_setattr(*self.get_env_uuid(context), bool(value))

    def get_env_uuid(self, context:bpy.types.Context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.path)

class OneOfContainer(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def isdrawn(self) -> bool:
        return super().isdrawn()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return
        if "oneOf" not in self.schema:
            panel_layout = panel.layout.row()
            prop_env, attribute = self.get_env_uuid(context)
            blend_create_prop(panel_layout, prop_env, attribute, self.title)

    def getSettings(self) -> dict:
        if not getattr(*self.get_env_uuid(context=bpy.context)):
            # check if Oneof widget is toggled on
            if isinstance(self.parent_element, OneOfWidget):
                if self.parent_element.isToggleable():
                    return None
                out_settings = {}
                for e in self.child_elements:
                    if e.name and not e.ignoreSettingExport():
                        settings = e.getSettings()
                        if settings is not None:
                            if isinstance(settings, dict):
                                if bool(settings):
                                    out_settings[e.name] = settings
                                else:
                                    continue
                            else:
                                out_settings[e.name] = settings
                return out_settings

        if 'oneOf' in self.schema:
            if getattr(*self.get_env_uuid(context=bpy.context)) and (
                getattr(*self.parent_element.get_env_uuid(context=bpy.context))):
                current_element = self.getCurrentUIElement()
                for child in self.child_elements:
                    if child.settingid == current_element:
                        return child.getSettings()
                print(f"ERROR: getting settings from EmptyCompoundUIElement: {self.settingid}.")
                return {"ERROR": "ERROR"}
            else:
                return None
        else:
            return super().getSettings()

    def setDefaultValue(self, context:bpy.types.Context) -> None:
        if self.default:
            return super().setDefaultValue(context)
        else:
            self.setValue(False, context)

    #get settingid of selected child
    def getCurrentUIElement(self) -> str:
        if 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append("Oneof")
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, oneof_path)
        else:
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, self.path)
        return getattr(attribute_env, attribute)

    def setValue(self, value:Any, context:bpy.types.Context) -> bool:
        # set oneOf to correct value:
        if 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append("Oneof")
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, oneof_path)
            #find the correct enum:
            possible_enums = bpy.context.scene.bl_rna.properties[str(attribute)].enum_items
            for enum in possible_enums:
                if value and value in enum.identifier:
                    setattr(attribute_env, attribute, enum.identifier)

        # in any case set UIElement to true
        return super().setValue(bool(value), context)


class EmptyCompoundUIElement(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def isdrawn(self) -> bool:
        return super().isdrawn()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return
        if "oneOf" not in self.schema:
            panel_layout = panel.layout.row()
            prop_env, attribute = self.get_env_uuid(context)
            blend_create_prop(panel_layout, prop_env, attribute, self.title)

    def getSettings(self) -> dict:
        if not getattr(*self.get_env_uuid(context=bpy.context)):
            # check if Oneof widget is toggled on
            if isinstance(self.parent_element, OneOfWidget):
                if self.parent_element.isToggleable():
                    return None
                out_settings = {}
                for e in self.child_elements:
                    if e.name and not e.ignoreSettingExport():
                        settings = e.getSettings()
                        if settings is not None:
                            if isinstance(settings, dict):
                                if bool(settings):
                                    out_settings[e.name] = settings
                                else:
                                    continue
                            else:
                                out_settings[e.name] = settings
                return out_settings
        else:
            # case for Add Checker texture
            if self.name and self.name == "addCheckerTexture":
                return {}

    def setDefaultValue(self, context:bpy.types.Context) -> None:
        if self.default:
            return super().setDefaultValue(context)
        else:
            self.setValue(False, context)

    #get settingid of selected child
    def getCurrentUIElement(self) -> str:
        if 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append("Oneof")
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, oneof_path)
        else:
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, self.path)
        return getattr(attribute_env, attribute)

    def setValue(self, value:Any, context:bpy.types.Context) -> bool:
        return super().setValue(bool(value), context)
        # set oneOf to correct value:
        if 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append("Oneof")
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, oneof_path)
            #find the correct enum:
            possible_enums = bpy.context.scene.bl_rna.properties[str(attribute)].enum_items
            for enum in possible_enums:
                if value and value in enum.identifier:
                    setattr(attribute_env, attribute, enum.identifier)

        # in any case set UIElement to true
        return super().setValue(bool(value), context)

class PopupOverrideOperator(bpy.types.Operator):
    bl_idname = "processor.popupoverride"
    bl_description = "Click to see and edit more Texture Map Thresholds"
    bl_label = "Expand"
    bl_options = {'REGISTER', 'UNDO'}

    target_uuid: bpy.props.StringProperty() # type: ignore

    def execute(self, context:bpy.types.Context) -> set[str]:
        path = get_path(self.target_uuid)
        ui_element = get_ui_element(path)
        try:
            if ui_element:
                ui_element.create_children(context)
        except AttributeError:
            print("could not find children of PopupOverrideElement")
            traceback.print_stack()
            traceback.print_exc()
        return {'FINISHED'}

class PopupOverrideElement(CompoundUIElement):
    """
    Compound Widget for groups of similar settings. Assumes that the first item is a "Default",
    and follow up ones are overrides that will be set through a popup.
    """
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements(default_element=True)

    def createChildElements(self, default_element:bool = False):
        """
        Create sub-elements, based on the current UIElement schema properties.
        """

        if "properties" not in self.schema:
            return
        for idx, name in enumerate(self.schema["properties"]):
            if name == 'version':
                continue

            settingid = self.schema['properties'][name].get('settingid', 'settingid_not_found')
            child_element = init_ui_element(name, settingid, self, self.uuid_dict, self.schema["properties"][name])
            if not child_element:
                continue

            self.child_elements.append(child_element)
            self.children_by_level[child_element.getLevel()].append(child_element)

            # hide all children except for the default value
            if default_element and idx != 0:
                child_element.inactive = True

    def isdrawn(self) -> bool:
        return super().isdrawn()

    def create_children(self, context:bpy.types.Context):
        for idx, child in enumerate(self.child_elements):
            if idx != 0:
                child.inactive = not child.inactive
                child.setDefaultValue(context)


    def draw_on_panel(self, layout:UILayout, context:Context, panel:Panel) -> Any:
        panel_layout = panel.layout.row()
        op = panel_layout.operator(PopupOverrideOperator.bl_idname, text="Toggle Texture Map Thresholds")
        uuid = get_uuid(self.path)
        op.target_uuid = uuid

        return super().draw_on_panel(layout, context, panel)

    def setDefaultValue(self, context:Context) -> Any:
        return super().setDefaultValue(context)

    def getSettings(self) -> dict:
        return super().getSettings()

    def setValue(self, value:Any, context:Context) -> bool:
        return super().setValue(value, context)

    def setDisabledExport(self):
        self.button_widget.setDisabled(not self.ignore_widget.isChecked())
        for child in self.child_elements:
            child.setDisabled(not self.ignore_widget.isChecked())

    def getCurrentUIElement(self) -> UIElement:
        return self.child_elements[self.list_widget.currentIndex().row() + 1]

    def elementChanged(self):
        self.stacked_widget.setCurrentIndex(self.list_widget.currentIndex().row())
        self.stacked_widget.updateGeometry()
        self.stacked_widget.adjustSize()

    def updateElement(self):
        self.stacked_widget.updateGeometry()
        self.stacked_widget.adjustSize()
        self.group_widget.adjustSize()
        self.group_widget.updateGeometry()
        self.adjustSize()
        self.updateGeometry()

def check_parents_drawn(parent_element:UIElement, parent_panel:bpy.types.Panel, context:bpy.types.Context) -> bool:
    if parent_element:
        if parent_element.isToggleable():
            parent_elment_value = blend_scene_getattr(
                context.scene, parent_element.path)
            if not getattr(*parent_elment_value):
                return False # parent disabled
            else:
                #direct parent is enabled, check next parent
                return check_parents_drawn(
                    parent_panel.parent_element, getParentPanel(parent_panel.bl_parent_id), context)
        else:
            #direct parent is enabled, check next parent
            return check_parents_drawn(
                parent_panel.parent_element, getParentPanel(parent_panel.bl_parent_id), context)
    else:
        return True # all parents enabled

def getParentPanel(parent_id:str) -> bpy.types.Panel:
    for panel in bpy.types.Panel.__subclasses__():
        if panel.__name__ == parent_id:
            return panel

class GroupPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_Subpanel"
    bl_description = "Group"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_label = "Group"
    bl_options = set()

    UI_elements:list[UIElement] = []
    parent_element: UIElement = None

    def __init__(self, *args:Any, **kwargs:Any):
        super().__init__(*args, **kwargs)
        self.parent_panel:bpy.types.Panel = getParentPanel(self.bl_parent_id)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if context.scene.rpde_running or context.scene.rpde_UI_error:
            return False
        if cls.parent_element:
            if isinstance(cls.parent_element, SimpleContainer):
                current_tab = bpy.context.scene.tabelements
                if cls.parent_element.settingid != current_tab:
                    return False
            return cls.parent_element.isdrawn()
        if cls.bl_label == "RapidPipeline 3D Processing Schema": #TODO find a better way to check this
            return True
        else:
            return False

    def draw(self, context: bpy.types.Context):
        if context.scene.rpde_UI_error:
            from .main_widget import drawUIError
            drawUIError(self, context)
            return
        try:
            panel_layout = self.layout.row()
            self.layout.enabled = True
            if self.parent_element:
                if self.parent_element.isToggleable():
                    attr = blend_scene_getattr(
                        context.scene, self.parent_element.path)
                    self.layout.enabled = getattr(*attr)
                if self.layout.enabled:
                    #parent object also needs to be enabled
                    self.layout.enabled = check_parents_drawn(self.parent_element, self.parent_panel, context)

            for ui_element in self.UI_elements:
                ui_element.draw_on_panel(panel_layout, context, self)

        except Exception:
            print("ERROR: Could not draw parts of UI Components of RapidPipeline Blender Plugin.")
            bpy.types.Scene.rpde_UI_error = True


    def draw_header(self, context: bpy.types.Context):
        if self.parent_element and self.parent_element.isToggleable():
            if self.parent_panel.parent_element and self.parent_panel.parent_element.isToggleable():
                env, attr = blend_scene_getattr(
                    context.scene, self.parent_panel.parent_element.path)
                self.layout.enabled = getattr(env, attr)
            env, attr = blend_scene_getattr(
                context.scene, self.parent_element.path)
            self.layout.prop(env, attr, text="")

class GroupWidget(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def isdrawn(self) -> bool:
        return super().isdrawn()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        _ = panel.layout.row()

    def setValue(self, value:bool, context:bpy.types.Context):
        setattr(*self.get_env_uuid(context), bool(value))

    def get_env_uuid(self, context:bpy.types.Context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.path)

    def updateElement(self):
        self.adjustSize()
        self.updateGeometry()

        # updates fixed height
        if self.group_widget.isChecked():
            self.group_widget.setFixedHeight(self.group_widget.sizeHint().height())
        else:
            self.group_widget.setFixedHeight(self.collapsed_height)

        # make sure the element is not shown and its height is 0 if all its children are disabled
        if not self.isHidden():
            all_elements_hidden = all(e.isHidden() for e in self.child_elements)
            self.setEnabled(not all_elements_hidden)
            self.setHidden(all_elements_hidden)
            if all_elements_hidden:
                self.group_widget.setFixedHeight(0)

    def onToggle(self):
        """
        Groupbox collapsable callback.
        """
        if self.isToggleable():
            self.ignore_widget.setHidden(not self.group_widget.isChecked())

        # update element itself
        self.updateElement()

        # propagate changes in size to parents
        self.updateParents()

    def getSettings(self) -> dict:
        out_settings = {}
        if (getattr(*blend_scene_getattr(bpy.context.scene, self.path)) or
            not self.isToggleable()):
            for e in self.child_elements:
                if e.name and not e.ignoreSettingExport():
                    settings = e.getSettings()
                    if settings is not None:
                        out_settings[e.name] = settings
        else:
            return None
        return out_settings

class OneOfWidget(CompoundUIElement):
    child_elements = []

    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()
        oneof_path = self.path.copy()
        oneof_path.append("Oneof")
        self.path = oneof_path

    def isdrawn(self) -> bool:
        return super().isdrawn()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        prop_env, attribute = blend_scene_getattr(context.scene, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)

#
        if self.isToggleable(): #TODO
            pass

    def setDisabledExport(self):
        self.dropdown_widget.setDisabled(not self.ignore_widget.isChecked())
        for child in self.child_elements:
            child.setDisabled(not self.ignore_widget.isChecked())

    def get_env_uuid(self, context:bpy.types.Context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.path)

    def setDefaultValue(self, context:bpy.types.Context):
        # for oneofs, we reset to the first element
        env, attr = self.get_env_uuid(context)
        first_item = bpy.context.scene.bl_rna.properties[attr].enum_items[0].identifier
        setattr(env, attr, first_item)

    def validateSchema(self):
        if "oneOf" not in self.schema or not self.schema["oneOf"]:
            raise ValueError("Unable to create OneOfWidget. Schema could not be validated.")

    #get settingid of selected child
    def getCurrentUIElement(self) -> str:
        attribute_env, attribute = blend_scene_getattr(
            bpy.context.scene, self.path)
        return getattr(attribute_env, attribute)

    def setCurrentUIElement(self, element_title: str):
        self.dropdown_widget.setCurrentIndex(self.child_element_names.index(element_title))

    def updateElement(self):
        self.adjustSize()
        self.updateGeometry()

        # update fixed size
        self.stacked_widget.setCurrentIndex(self.dropdown_widget.currentIndex())
        h = self.stacked_widget.currentWidget().sizeHint().height()
        self.stacked_widget.setFixedHeight(h)

    def createChildElements(self):
        """
        Create sub-elements, based on the current UIElement schema properties.
        """
        # we create all properties, and just switch the view
        if 'oneOf' in self.schema:
            for oneof in self.schema["oneOf"]:
                settingid = oneof.get('settingid', "Settingid")
                title = "" #enum elements dont have a key so that should not contribute to the paths

                oneof_child = init_ui_element(
                    name = title, settingid=settingid, parent=self, uuid_dict=self.uuid_dict, schema=oneof)
                if not oneof_child:
                    continue

                self.child_elements.append(oneof_child)

        if not self.child_elements:
            print(f"Invalid or Empty CompoundUIElement (no child elements found): {self.settingid}")
            raise ValueError(f"Invalid or Empty CompoundUIElement: {self.settingid}.")

    def onDropdownChanged(self):
        """
        Callback, upon selecting a new index, the element visible in the OneOf
        widget main layout will be the one index by the ComboBox.
        """
        # update element itself
        self.updateElement()

        # propagate size changes
        self.updateParents()

    def getSettings(self) -> dict:
        current_element = self.getCurrentUIElement()
        for child in self.child_elements:
            if child.settingid == current_element:
                return child.getSettings()
        print(f"ERROR: getting settings from OneOf Widget: {self.settingid}.")
        return {"ERROR": "ERROR"}

    def setSettings(self, settings: dict):
        """
        Updates settings of the current UI component and activates it.
        """
        child_by_name = {c.name: c for c in self.child_elements}
        setting_provided = next((s for s in settings), None)
        if not setting_provided:
            raise ValueError("Invalid Settings file: setting not found.")
        child_by_name[setting_provided].setSettings(settings[setting_provided])

        # update the UIElement being displayed
        self.setCurrentUIElement(child_by_name[setting_provided].title)
        self.onDropdownChanged()

    def setValue(self, value:Any, context:bpy.types.Context) -> bool:
        # set oneOf to correct value:
        if 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append("Oneof")
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, oneof_path)
            #find the correct enum:
            possible_enums = bpy.context.scene.bl_rna.properties[str(attribute)].enum_items
            for enum in possible_enums:
                if value and value in enum.identifier:
                    setattr(attribute_env, attribute, enum.identifier)

        else:
            return super().setValue(value, context)

class FileExportType(SimpleContainer):
    def __init__(self, name:str, settingid:str, parent:UIElement, uuid_dict:dict, schema:dict = {}):
        if "items" in schema:
            schema = schema["items"]
        super().__init__(name, settingid, parent, uuid_dict,  schema)
        self.createChildElements()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        pass

    def getSettings(self) -> dict:
        out_settings = {}
        for e in self.child_elements:
            if e.name and not e.ignoreSettingExport():
                settings = e.getSettings()
                if settings is not None:
                    if isinstance(settings, dict):
                        if bool(settings):
                            out_settings[e.name] = settings
                        else:
                            continue
                    else:
                        out_settings[e.name] = settings
        return out_settings

    def setDefaultValue(self, context:bpy.types.Context):
        pass

    def setSettings(self, settings: dict):
        """
        Updates settings of the current UI component, and its children, and activates it.
        """
        pass

class TabElementOperator(bpy.types.Operator):
    bl_idname = "processor.tabelement"
    bl_description = "Tab_Element"
    bl_label = "Tab_Element_Label"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        print(f"execute Tab element: {self.bl_label}")
        return {'FINISHED'}

class TabElement(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def isdrawn(self) -> bool:
        return True

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

    def getActiveElement(self) -> UIElement:
        #TODO
        return None

    def getSettings(self) -> dict:
        out_settings = {}
        for e in self.child_elements:
            if e.name and not e.ignoreSettingExport():
                settings = e.getSettings()
                if settings is not None:
                    if isinstance(settings, dict):
                        if bool(settings):
                            out_settings[e.name] = settings
                        else:
                            continue
                    else:
                        out_settings[e.name] = settings
        return out_settings

clss = [
    TabElementOperator, SimpleContainerOperator, PopupOverrideOperator
]

reg, unreg = bpy.utils.register_classes_factory(clss)

def register():
    reg()

def unregister():
    unreg()
