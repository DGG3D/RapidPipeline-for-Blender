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

from typing import Any

import bpy  # type: ignore

from .gui_commons import UIElement
from .scene_utils import blend_create_prop, blend_scene_getattr


class GroupWidgetPropertyGroup(bpy.types.PropertyGroup):
    boolean_prop : bpy.props.BoolProperty()  # type: ignore
    value_prop : bpy.props.BoolProperty()  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore
    toggable: bpy.props.BoolProperty(default=False)  # type: ignore

class StringPropertyGroup(bpy.types.PropertyGroup):
    value_prop : bpy.props.StringProperty()  # type: ignore
    string_prop : bpy.props.StringProperty(default="")  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

class StringProperty(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "string")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return
        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)
#
        if self.isToggleable(): #TODO
            pass

class BooleanPropertyGroup(bpy.types.PropertyGroup):
    value_prop : bpy.props.BoolProperty() # type: ignore
    boolean_prop : bpy.props.BoolProperty(default=True)  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

class BooleanProperty(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "boolean")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)

        if self.isToggleable(): #TODO
            pass

class IntegerPropertyGroup(bpy.types.PropertyGroup):
    value_prop : bpy.props.IntProperty(default=0)  # type: ignore
    integer_prop : bpy.props.IntProperty(default=0)  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

class IntegerProperty(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "integer")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return
        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)


class FloatPropertyGroup(bpy.types.PropertyGroup):
    number_prop : bpy.props.FloatProperty(default = 0.0)  # type: ignore
    value_prop : bpy.props.FloatProperty(default = 0.0)  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

#NOTE currently unused
class FloatPropertyMinMax(bpy.types.PropertyGroup):
    number_prop : bpy.props.FloatProperty(default = 0.0, min=0.0, max=100.0, subtype='PERCENTAGE')  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

class FloatProperty(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "number")
        self.has_slider = ('maximum' in schema and schema['maximum'] < 1000)

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title, slider=self.has_slider)


        if self.isToggleable(): #TODO
            pass

#NOTE currently unused
class PercentageProperty(bpy.types.PropertyGroup):
    numer_prop : bpy.props.FloatProperty(default = 0.0, min=0, max= 100.0) # type: ignore
    value_prop : bpy.props.FloatProperty(default = 0.0, min=0, max= 100.0) # type: ignore
    path : bpy.props.StringProperty(default="")   # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

#NOTE currently unused
class PercentageProperty(FloatProperty):  # noqa: F811
    def __init__(self, name: str, settingid: str, parent: "UIElement", schema: dict = {}):
        super().__init__(name, settingid, parent, schema, "number")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)


class EnumProperty(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "enum")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)

    def getValue(self, context:bpy.types.Context=None) -> tuple[Any, Any]:
        return blend_scene_getattr(bpy.context.scene, self.settingid, self.uuid_dict, self.type, self.path)

    def setDefaultValue(self, context:bpy.types.Context):
        # for enums, we reset to the first element
        first_item = bpy.context.scene.bl_rna.properties[str(self.getValue(context)[1])].enum_items[0].identifier
        setattr(*self.getValue(context), first_item)


class ColorPropertyGroup(bpy.types.PropertyGroup):
    array_prop : bpy.props.FloatVectorProperty(default = (1.0, 1.0, 1.0), min=0.0, max=1.0, subtype='COLOR')  # type: ignore
    value_prop : bpy.props.FloatVectorProperty(default = (1.0, 1.0, 1.0), min=0.0, max=1.0, subtype='COLOR')  # type: ignore
    path : bpy.props.StringProperty(default="")  # type: ignore
    settingid : bpy.props.StringProperty(default="")  # type: ignore
    type : bpy.props.StringProperty(default="")  # type: ignore

class ColorPicker(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "array")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        if not self.isdrawn():
            return

        prop_env, attribute = blend_scene_getattr(context.scene, self.settingid, self.uuid_dict, self.type, self.path)
        panel_layout = panel.layout.row()
        blend_create_prop(panel_layout, prop_env, attribute, self.title)

        if self.isToggleable(): #TODO
            pass

    def getSettings(self) -> list[Any]:
        outlist = list(super().getSettings())
        outlist.append(1.0)     #append alpha value
        return outlist


class EmptySchemaObject(UIElement):
    def __init__(self, name: str, settingid: str, parent: "UIElement", uuid_dict:dict, schema: dict = {}):
        super().__init__(name, settingid, parent, schema, uuid_dict, "object")

    def draw_on_panel(self, layout:bpy.types.UILayout, context:bpy.types.Context, panel:bpy.types.Panel):
        pass

    def getSettings(self) -> dict:
        return {}

clss = ()

reg, unreg = bpy.utils.register_classes_factory(clss)

def register():
    reg()


def unregister():
    unreg()

