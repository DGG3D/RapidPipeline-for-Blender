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


from typing import Any, Callable, List

import bpy  # type: ignore
from bpy.types import Panel

from .compound_elements import GroupPanel, SimpleContainer, get_ui_elements_dict
from .gui_commons import UIElement
from .main_widget import MainPanel
from .scene_utils import get_uuid, set_uuid


# Creates blender properties for each element in the rpde schema
# Then asigns those properties to their respective panels in the UI layout
def setup_properties(schema: dict,
                     parent: dict = None,
                     path: List[str] = [],
                     schema_key:str = "",
                     parent_panel:str = "",
                     magic_descriptions_dict:dict = {}):

    def get_description() -> str:
        if get_uuid(path) in magic_descriptions_dict:
            return magic_descriptions_dict[get_uuid(path)]
        else:
            return schema.get("description", "")

    if isinstance(parent, dict) and parent.get('settingid', None) is not None:
        if schema_key:
            path.append(schema_key)

    if not parent_panel:
        parent_panel = create_subpanel(path, MainPanel.bl_idname, schema, display_header=False)
    temp_path = path.copy()
    attribute_id = schema.get("settingid", "settingid_not_found")

    for key in schema.keys():
        if key == 'properties':
            for sub_schema in schema['properties'].keys():
                if isinstance(schema['properties'][sub_schema], dict):
                    if parent and path:
                        parent_panel = create_subpanel(path.copy(), parent_panel.bl_idname, schema, display_header=True)
                        add_parent_to_panel(path.copy(), parent_panel, sub_schema)
                    setup_properties(schema=schema['properties'][sub_schema],
                                        parent=schema.copy(), path=path.copy(),
                                        schema_key=sub_schema, parent_panel=parent_panel,
                                        magic_descriptions_dict=magic_descriptions_dict)

        if not schema_key:
            continue

        #case only for export
        if key == "items" and attribute_id == "exportArray":
            setup_properties(schema["items"], parent, path, schema_key,
                             parent_panel, magic_descriptions_dict=magic_descriptions_dict)

        if key == 'type':
            if schema['type'] == 'boolean':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.BoolProperty(
                        name="", default=schema['default'], description=get_description()),
                    toggable=('toggleable' in schema), parent_panel=parent_panel)
            if schema['type'] == 'integer':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.IntProperty(
                        name="", default=schema['default'], min=schema.get('minimum', 0.0),
                        max=schema.get('maximum', 100_000_000), description=get_description()),
                    toggable=('toggleable' in schema), parent_panel=parent_panel)
            if schema['type'] == 'string':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.StringProperty(
                        name="", default=schema.get('default', ""), description=get_description()),
                    toggable=('toggleable' in schema), parent_panel=parent_panel)
            if schema['type'] == 'object':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.BoolProperty(name="", default=False, description=get_description()),
                    toggable=('toggleable' in schema), parent_panel=parent_panel)

            if schema['type'] == 'number':
                if 'percentage' in parent:
                        blend_scene_init_setattr(
                            bpy.types.Scene, attribute_id, path=path,
                            value_function=
                                bpy.props.FloatProperty(
                                    name="",
                                    min=schema['minimum'],
                                    max=schema['maximum'],
                                    default=schema['default'],
                                    subtype='PERCENTAGE',
                                    description=get_description(), precision=3),
                                    value=schema['default'],
                                    toggable=('toggleable' in schema),
                                    parent_panel=parent_panel
                                    )
                else:
                    if 'maximum' in schema:
                        value_function = bpy.props.FloatProperty(
                                name="",
                                min=schema.get('minimum', 0.0), max=schema['maximum'],
                                default=schema.get('default', 0.0), description=get_description(),
                                precision=3)
                    else:
                        value_function = bpy.props.FloatProperty(
                                    name="",
                                    min=schema.get('minimum', 0.0), default=schema.get('default', 0.0),
                                    description=get_description(),
                                    precision=3)
                    blend_scene_init_setattr(
                        bpy.types.Scene, attribute_id, path=path,
                        value_function=value_function,
                        toggable=('toggleable' in schema), parent_panel=parent_panel)

            if schema['type'] == 'array' and 'default' in schema:
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.FloatVectorProperty(
                        name="",
                        default = (schema['default'][:3]), min=0.0, max=1.0, subtype='COLOR',
                        description=get_description()), toggable=('toggleable' in schema), parent_panel=parent_panel)

        if key == 'enum':
            enum_options = []
            for element in schema['enum']:
                enum_options.append((element,)*3)
            blend_scene_setattr_enum(bpy.types.Scene,
                    property=bpy.props.EnumProperty(name="", items=enum_options, description=get_description()),
                    path=path, parent_panel=parent_panel)

        if key == 'oneOf':
            #create panel for oneofs (needed for modifier tab)
            if list(schema.keys())[0] == "oneOf":
                sub_schema = list(schema.keys())[0]
                if parent and path:
                    parent_panel = create_subpanel(path.copy(), parent_panel.bl_idname, schema, display_header=True)
                    add_parent_to_panel(path.copy(), parent_panel, sub_schema)

            oneof_elements = []
            for oneof_sub_schema in schema['oneOf']:
                oneof_elements.append((oneof_sub_schema.get('settingid', ''),
                                        oneof_sub_schema.get('title', ''),
                                        oneof_sub_schema.get('description', '')))
            #TODO: we need to draw the child objects of oneof
            #however they dont have a different path and they dont appear in the settings
            #this would be the emptyCompoundUIElement
            #so we need to draw the children of the correct empty comound ui element
            path_oneof = path.copy()
            path_oneof.append("Oneof")
            blend_scene_setattr_enum(bpy.types.Scene,
                    property=bpy.props.EnumProperty(name="", items=oneof_elements, description=get_description()),
                    path=path_oneof, parent_panel=parent_panel)

            path_tmp = path.copy()
            for oneof_sub_schema in schema['oneOf']:
                if isinstance(oneof_sub_schema, dict):
                    setup_properties(schema=oneof_sub_schema,
                                        parent=schema.copy(),
                                        path=path_tmp, schema_key= None,
                                        parent_panel=parent_panel,
                                        magic_descriptions_dict=magic_descriptions_dict)
                path=path_tmp

        path= temp_path

def create_subpanel(path:List[str], parent_panel:str, schema:dict, display_header:bool) -> GroupPanel:
    set_uuid(set(path))
    id = f"VIEW3D_PT_Subpanel{get_uuid(path).replace('-', '')}"
    header = {'HIDE_HEADER'} if not display_header else set()
    if id:
        if not hasattr(bpy.types, id):
            new_panel = type(id,
                (GroupPanel, Panel, ),
                {"bl_idname" : id, "bl_label" : schema.get("title", ""),
                    "bl_parent_id": parent_panel, "UI_elements": [],
                    "bl_options": header})
            if not hasattr(bpy.types, new_panel.bl_idname):
                bpy.utils.register_class(new_panel)
            return new_panel
        else:
            return getattr(bpy.types, id)
    return None

def add_parent_to_panel(in_path:List[str], panel:GroupPanel, schema_key:str):
    if schema_key:
        path = in_path.copy()
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(path)]
        except Exception:
            import traceback
            traceback.print_stack()
            traceback.print_exc()

            print("Error could not find ui element to add to panel")
            ui_element:UIElement = None
        if ui_element:
            panel.parent_element = ui_element
    else:
        print("Error: could not find schema key for adding parent to panel")
        print(f"For Path: {in_path} and panel: {panel.bl_label}")

def blend_scene_init_setattr(
        scene:bpy, id:str,
        path:List[str]=[],
        value_function:Callable=None,
        toggable:bool=False, reset:bool=False,
        parent_panel:bpy.types.Panel=None) -> bool:
    if not path:
        raise Exception(f"ERROR: error in setting blend attribute. Could not find path for id: {id}!")
    if not get_uuid(path):
        if toggable:
            path_toggable = path.copy()
            path_toggable.append("toggable")
            set_uuid(set(path_toggable))
        set_uuid(set(path))
    if reset or (not hasattr(scene, get_uuid(path))):
        setattr(scene, get_uuid(path), value_function)
        add_ui_element_to_panel(path, parent_panel)
        return True
    else:
        add_ui_element_to_panel(path, parent_panel)
        return False

def add_ui_element_to_panel(path:List[str], panel:GroupPanel):
    if not panel:
        print("no panel found")
        import traceback
        traceback.print_stack()
    if panel and panel.bl_idname != "VIEW3D_PT_RapidPipeline":
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(path)]
        except Exception:
            ui_element:UIElement = None
        if ui_element:
            if not isinstance(ui_element, SimpleContainer):
                panel.UI_elements.append(ui_element)
                ui_element.panel = panel

def blend_scene_setattr_enum(scene:bpy.types.Scene, property:Any, path:set, parent_panel:bpy.types.Panel=None):
    if not get_uuid(path):
        set_uuid(set(path))
    if not hasattr(scene, get_uuid(path)):
        setattr(scene, get_uuid(path), property)
        if parent_panel:
            add_ui_element_to_panel(path, parent_panel)
    else:
        getattr(scene, get_uuid(path))
        if parent_panel:
            add_ui_element_to_panel(path, parent_panel)
