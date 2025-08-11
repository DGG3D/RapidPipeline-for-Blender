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
import uuid
from typing import Any, Callable, List

import bpy  # type: ignore


def blend_scene_init_setattr(
        scene:bpy, id:str,
        property_group:bpy=None,
        path:List[str]=[],
        value_function:Callable=None,
        uuid_dict:dict={}, toggable:bool=False, reset:bool=False):
    if not path:
        raise Exception(f"ERROR: error in setting blend attribute. Could not find path for id: {id}!")
    if not get_uuid(path):
        if toggable:
            path_toggable = path.copy()
            path_toggable.append("toggable")
            set_uuid(set(path_toggable))
        set_uuid(set(path))
    if reset or (not hasattr(scene, get_uuid(path))):
        if property_group:
            setattr(scene, get_uuid(path), value_function)
        else:
            print("ERROR: Attribute is not settable")
            return

def blend_scene_setattr(attribute_env:bpy.types.Scene, attribute:Any, value:Any):
    try:
        setattr(attribute_env, attribute, value)
    except Exception:
        print("Warning: could not set attribute.")
        traceback.print_stack()
        traceback.print_exc()

def blend_scene_setattr_enum(scene:bpy.types.Scene, id:str, uuid_dict:dict, property:Any, path:set):
    if not get_uuid(path):
        set_uuid(set(path))
    if not hasattr(scene, get_uuid(path)):
        setattr(scene, get_uuid(path), property)
    else:
        getattr(scene, get_uuid(path))

def blend_scene_getattr(
        scene:bpy.types.Scene,
        settingid:str = "",
        type_in:str = "",
        path:set=[]) -> tuple[bpy.types.Scene, Any]:
    attribute_uuid = get_uuid(path)
    # has to search trough the correct collection property and get the property where the path matches
    try:
        if hasattr(scene, attribute_uuid):
            return (scene,  attribute_uuid)
        else:
            print(f"Warning: could not find attribute with path '{path}' in blend scene.")
            return None
    except Exception:
        print(f"Error: could not get blender attribute Path: {path}")
        print(f"Attribute UUID: {attribute_uuid}")
        print(traceback.format_exc())


def blend_create_prop(panel_layout:bpy.types.UILayout,
                      attribute_env:bpy.types.Scene,
                      attribute:Any,
                      name:str='',
                      type:str = None,
                      slider:bool = False):
    panel_layout.prop(attribute_env, attribute, text=name, slider=slider)


uuid_paths:dict = {}

def set_uuid(path:set[str]):
    if not get_uuid(path):
        uuid_paths[str(uuid.uuid4())] = set(path)

def get_uuid(path:set[str]) -> str:
    for key, value in uuid_paths.items():
        if value == set(path):
            return key
    return None

def get_path(uuid:str) -> set[str]:
    return uuid_paths[uuid]

def get_ui_element(search_path:set[str]):
    from .compound_elements import get_ui_elements_dict
    ui_element = None
    ui_elements_dict = get_ui_elements_dict()

    for path_uuid, ui_element in ui_elements_dict.items():
        if get_path(path_uuid) == search_path:
            return ui_element

    print(f"Warning, UI element could not be found with path {search_path}")
    return None
