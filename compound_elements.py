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
from .scene_utils import blend_create_prop, blend_scene_getattr, blend_scene_setattr, get_uuid, set_uuid

ui_elements_dict = {} #key -> paths, value -> UIElement
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
                set_uuid(uuid_dict, set(oneof_path))
                ui_elements_dict[get_uuid(uuid_dict, oneof_path)] = created_oneof
                parent.child_elements.append(created_oneof)

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
            created_property = EmptyCompoundUIElement(name, settingid, parent, uuid_dict, schema)
        else:
            print("no oneof, type or enum found. Creating empty schema object")
            created_property = EmptySchemaObject(name, settingid, parent, uuid_dict, schema)
    except Exception:
        # default: unsupported
        print(f"Unable to create Property {name}, type not implemented or invalid.")
        print(traceback.format_exc())
        print(traceback.print_stack())

    if created_property.path:
        set_uuid(uuid_dict, set(created_property.path))
        ui_elements_dict[get_uuid(uuid_dict, created_property.path)] = created_property
    return created_property

def get_ui_elements_dict() -> dict:
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
            oneof:OneOfWidget = ui_elements_dict[get_uuid(self.uuid_dict, oneof_path)]
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

    def setValue(self, value, context) -> bool:
        return super().setValue(bool(value), context)

    def getValue(self, context):
        return super().getValue(context)

    def getSettings(self) -> dict:
        out_settings = {}
        if (getattr(*blend_scene_getattr(bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path))) or (
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

        # make sure to set toggable properties to checked - if the setting was changed, we want it
        if self.isToggleable():
            self.setIgnoreExport(True)

    def setDefaultValue(self, context:bpy.types.Context):
        """
        Unless otherwise specified, CompoundElements don't have a default value, so we only uncheck them.
        """
        super().setDefaultValue(context)
        # make sure to set toggable properties to unchecked
        if self.isToggleable():
            self.setIgnoreExport(False)

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
            text=self.name,
            icon_value=getattr(context.scene, f"icon_{self.settingid}").icon_id,
            depress=depress)

        simple_container_operator.settingid = self.settingid

        if self.isToggleable(): #TODO
            pass
            #panel_layout.prop(self.ignore_widget, 0, self.layout.columnCount())

    def isToggleable(self):
        return True

    def setDefaultValue(self, context):
        self.setValue(False, context)

    def setValue(self, value:bool, context):
        blend_scene_setattr(*self.getValue(context), bool(value))

    def getValue(self, context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)

class EmptyCompoundUIElement(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def isdrawn(self):
        return super().isdrawn()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return
        if "oneOf" not in self.schema:
            panel_layout = panel.layout.row()
            prop_env, attribute = self.getValue(context)
            blend_create_prop(panel_layout, prop_env, attribute, self.title)

    def getSettings(self) -> dict:
        if not getattr(*self.getValue(context=bpy.context)):
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
            if getattr(*self.getValue(context=bpy.context)) and (
                getattr(*self.parent_element.getValue(context=bpy.context))):
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

    def setDefaultValue(self, context):
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
                bpy.context.scene, self.settingid, self.uuid_dict, self.type, oneof_path)
        else:
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        return getattr(attribute_env, attribute)

    def setValue(self, value, context):
        # set oneOf to correct value:
        if 'oneOf' in self.schema:
            oneof_path = self.path.copy()
            oneof_path.append("Oneof")
            attribute_env, attribute = blend_scene_getattr(
                bpy.context.scene, self.settingid, self.uuid_dict, self.type, oneof_path)
            #find the correct enum:
            possible_enums = bpy.context.scene.bl_rna.properties[str(attribute)].enum_items
            for enum in possible_enums:
                if value and value in enum.identifier:
                    setattr(attribute_env, attribute, enum.identifier)

        # make sure to set toggable properties to checked - if the setting was changed, we want it
        if self.isToggleable():
            self.setIgnoreExport(True)

        # in any case set UIElement to true
        return super().setValue(bool(value), context)

class PopupOverrideElement(CompoundUIElement):
    """
    Compound Widget for groups of similar settings. Assumes that the first item is a "Default",
    and follow up ones are overrides that will be set through a popup.
    """

    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def openDialog(self):
        self.dialog_widget.exec()

    def closeDialog(self):
        self.dialog_widget.close()

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

    def setHideElement(self, value: bool):
        # the UI rules file takes priority
        hidden_settings = ProcessorPlugin.ui_rules.get("hideSettings", [])
        if "settingid" in self.schema and self.schema["settingid"] in hidden_settings:
            value = True

        self.setHidden(value)

        # if we are changing the visibility to True, we need to hide non-chosen elements
        if not value:
            current_element = self.getCurrentUIElement()
            for element in self.child_elements[1:]:
                if element != current_element:
                    element.setHidden(True)

        # the button should only be displayed if one or more items of the dialog are visible
        self.button_widget.setHidden(all(e.isHidden() for e in self.child_elements[1:]))

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
                context.scene, parent_element.settingid, parent_element.uuid_dict,
                parent_element.type, parent_element.path)
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_panel:bpy.types.Panel = getParentPanel(self.bl_parent_id)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        if context.scene.rpde_running or not context.scene.has_license or context.scene.rpde_UI_error:
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
                        context.scene, self.parent_element.settingid,
                        self.parent_element.uuid_dict, "", self.parent_element.path)
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
                    context.scene, self.parent_panel.parent_element.settingid,
                    self.parent_panel.parent_element.uuid_dict, "", self.parent_panel.parent_element.path)
                self.layout.enabled = getattr(env, attr)
            env, attr = blend_scene_getattr(
                context.scene, self.parent_element.settingid,
                self.parent_element.uuid_dict, "", self.parent_element.path)
            self.layout.prop(env, attr, text="Enable")

class GroupWidget(CompoundUIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")
        self.createChildElements()

    def isdrawn(self):
        return super().isdrawn()

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        _ = panel.layout.row()

    def setValue(self, value:bool, context):
        setattr(*self.getValue(context), bool(value))

    def getValue(self, context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)

    def setIgnoreExport(self, is_displayed:bool):
        self.setValue(is_displayed, context=None)

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
        if (getattr(*blend_scene_getattr(bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)) or
            not self.isToggleable()):
            for e in self.child_elements:
                if e.name and not e.ignoreSettingExport():
                    settings = e.getSettings()
                    if settings is not None:
                        out_settings[e.name] = settings #TODO DONT CREATE ELEMENT IF NO CHILDREN
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

        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)

#
        if self.isToggleable(): #TODO
            pass

    def setDisabledExport(self):
        self.dropdown_widget.setDisabled(not self.ignore_widget.isChecked())
        for child in self.child_elements:
            child.setDisabled(not self.ignore_widget.isChecked())

    def getValue(self, context:bpy.types.Context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)

    def setDefaultValue(self, context:bpy.types.Context):
        # for oneofs, we reset to the first element
        first_item = bpy.context.scene.bl_rna.properties[str(self.getValue(context)[1])].enum_items[0].identifier
        setattr(*self.getValue(context), first_item)

        # make sure to set toggable properties to unchecked
        if self.isToggleable():
            self.setIgnoreExport(False)

    def validateSchema(self):
        if "oneOf" not in self.schema or not self.schema["oneOf"]:
            raise ValueError("Unable to create OneOfWidget. Schema could not be validated.")

    #get settingid of selected child
    def getCurrentUIElement(self) -> str:
        attribute_env, attribute = blend_scene_getattr(
            bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        return getattr(attribute_env, attribute)

    def setCurrentUIElement(self, element: UIElement):
        self.dropdown_widget.setCurrentIndex(self.child_element_names.index(element.title))

    def updateElement(self):
        self.adjustSize()
        self.updateGeometry()

        # update fixed size
        self.stacked_widget.setCurrentIndex(self.dropdown_widget.currentIndex())
        h = self.stacked_widget.currentWidget().sizeHint().height()
        self.stacked_widget.setFixedHeight(h)

    def setHideElement(self, value: bool):
        self.setHidden(value)

        # if we are changing the visibility to True, we need to hide non-chosen elements
        if not value:
            current_element = self.getCurrentUIElement()
            for element in self.child_elements:
                if element != current_element:
                    element.setHidden(True)

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
        self.setCurrentUIElement(child_by_name[setting_provided])
        self.onDropdownChanged()

        # make sure to set toggable properties to checked - if the setting was changed, we want it
        if self.isToggleable():
            self.setIgnoreExport(True)

    def setValue(self, value, context):
        return super().setValue(value, context)

class FileExportType(SimpleContainer):
    def __init__(self, name:str, settingid:str, parent:UIElement, uuid_dict:dict, schema:dict = {}):
        super().__init__(name, settingid, parent, uuid_dict,  schema)

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        pass 

    def getSettings(self) -> list:
        # NOTE: the actual CLI schema has an array of export settings
        return {}

    def setDefaultValue(self, context):
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

    def getSettings(self):
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
    TabElementOperator, SimpleContainerOperator
]

reg, unreg = bpy.utils.register_classes_factory(clss)

def register():
    reg()

def unregister():
    unreg()
