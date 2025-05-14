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
        uuid_dict:dict={}, toggable:bool=False):
    if not path:
        raise Exception(f"ERROR: error in setting blend attribute. Could not find path for id: {id}!")
    if toggable:
        path_toggable = path.copy()
        path_toggable.append("toggable")
        set_uuid(uuid_dict, set(path_toggable))
    set_uuid(uuid_dict, set(path))
    if not hasattr(scene, get_uuid(uuid_dict, path)):
        if property_group:
            setattr(scene, get_uuid(uuid_dict, path), value_function)
        else:
            print("ERROR: Attribute is not settable")
            return

def blend_scene_setattr(attribute_env:bpy.types.Scene, attribute:Any, value:Any):
    try:
        setattr(attribute_env, attribute, value)
    except Exception:
        print("Warning: could not set attribute.")
#        traceback.print_stack()
        traceback.print_exc()

def blend_scene_setattr_enum(scene:bpy.types.Scene, id:str, uuid_dict:dict, property:Any, path:set):
    if not get_uuid(uuid_dict, path):
        set_uuid(uuid_dict, set(path))
    if not hasattr(scene, get_uuid(uuid_dict, path)):
        setattr(scene, get_uuid(uuid_dict, path), property)
    else:
        getattr(scene, get_uuid(uuid_dict, path))
        print(f"Warning: Scene already has attribute: {id}, adding new element to collection")

def blend_scene_getattr(
        scene:bpy.types.Scene,
        settingid:str,
        uuid_dict:dict,
        type_in:str = None,
        path:set=[]) -> tuple[bpy.types.Scene, Any]:
    attribute_uuid = get_uuid(uuid_dict, path)
    # has to search trough the correct collection property and get the property where the path matches
    #get all type_prop values:
    try:
        if hasattr(scene, attribute_uuid):
            prop = getattr(scene, attribute_uuid)
            if isinstance(prop, bpy.types.bpy_prop_collection): #currently not in use
                # check paths:
                return (prop[0], "value_prop")
            else:
                return (scene,  attribute_uuid)
        else:
            print(f"Warning: could not find attribute '{settingid}' in blend scene. \n Using default instead.")
            return (scene, f'{type_in}_default')
    except Exception:
        print(f"Error: could not get blender attribute settingID: {settingid}, type: {type_in}, Path: {path}")
        print(f"Attribute UUID: {attribute_uuid}")
        print(traceback.format_exc())


def blend_create_prop(panel_layout:bpy.types.UILayout,
                      attribute_env:bpy.types.Scene,
                      attribute:Any,
                      name:str='',
                      type:str = None,
                      slider:bool = False):
    if 'default' in attribute:
        print("ERROR: Unexpected error, default prop is used!")
        panel_layout.prop(attribute_env, f'{type}_default', text=f"dafault {type}", slider=slider)
    else:
        panel_layout.prop(attribute_env, attribute, text=name, slider=slider)


def set_uuid(uuid_paths:dict, path:set[str]):
    if not get_uuid(uuid_paths, path):
        uuid_paths[str(uuid.uuid4())] = set(path)

def get_uuid(uuid_paths:dict, path:set[str]) -> str:
    for key, value in uuid_paths.items():
        if value == set(path):
            return key
    return None

def get_path(uuid_paths:dict, uuid:str) -> set[str]:
    return uuid_paths[uuid]
