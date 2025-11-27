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
import webbrowser

import bpy  # type: ignore

from .json_utils import JSonUtils
from .scene_utils import blend_scene_getattr, get_ui_element
from .settings_operator import resetSettingsToDefault, setValue

preview_collections = {}

class MagicActionOption():
    option_path = set()
    option_name = ""
    option_description = ""
    option_toggled = False

    def __init__(self, path:set, name:str="", description:str="", toggled:bool = False):
        self.option_path = path
        self.option_name = name
        self.option_description = description
        self.option_toggled = toggled

    def get_option_ui_element(self):
        get_ui_element(self.option_path)

class MagicAction():
    action_name = ""
    action_description = ""
    path = ""
    action_config = {}
    action_image = ""
    action_version = ""
    ui_prio = 0
    action_options:list[MagicActionOption] = []
    action_link:str = ""

    def __init__(self,
                 name:str,
                 description:str,
                 action_config:dict,
                 path:str,
                 version:str,
                 action_image:str = "",
                 ui_prio:int = 0,
                 action_link:str = ""):
        self.action_name = name
        self.action_description = description
        self.action_config = action_config
        self.path = path
        self.action_image = action_image
        self.action_version = version
        self.ui_prio = ui_prio
        self.action_options = self.set_options()
        self.action_link = action_link

    def set_options(self) -> list[MagicActionOption]:
        action_options = []
        magic_action_meta_path = os.path.join(self.path, "meta.json")
        magic_action_meta = JSonUtils.loadJSON(magic_action_meta_path)
        exposed_options:list[dict] = magic_action_meta["exposed_options"]
        for option in exposed_options:
            if 'path' in option:
                option_path:str = option["path"]
                # if option has no name we take the last part of the path for now
                option_name = option.get("name", "")
                option_description = option.get("description", "")
                option_toggled = option.get("toggled")
                path_set = set(option_path.split('.'))
                option = MagicActionOption(path_set, option_name, option_description, option_toggled)
                action_options.append(option)
        return action_options



def set_magic_actions(type:str) -> list[MagicAction]:
    magic_actions:list[MagicAction] = []
    dirname = os.path.dirname(__file__)
    magic_action_folder = os.path.join(dirname, 'magic-actions', 'actions', global_magic_action_version, type)

    if os.path.isdir(magic_action_folder):
        for magic_action in os.listdir(magic_action_folder):
            if os.path.isdir(os.path.join(magic_action_folder, magic_action)):
                magic_action_meta_path = os.path.join(magic_action_folder, magic_action, "meta.json")
                magic_action_image_path = os.path.join(magic_action_folder, magic_action, "image.png")
                magic_action_config_path = os.path.join(magic_action_folder, magic_action, "rpd_config.json")
                magic_action_meta = JSonUtils.loadJSON(magic_action_meta_path)
                magic_action_config = JSonUtils.loadJSON(magic_action_config_path)
                name = magic_action_meta.get("button_name", magic_action_meta.get("name", ""))
                description = magic_action_meta.get("explanation", "")
                # do not displac magic actions that include cad import
                if "is_import_action" in magic_action_meta and magic_action_meta["is_import_action"]:
                    continue
                action = MagicAction(
                    name,
                    description,
                    magic_action_config,
                    os.path.join(magic_action_folder, magic_action),
                    global_magic_action_version,
                    action_image=magic_action_image_path,
                    ui_prio=magic_action_meta.get("ui_prio_hints", {}).get("blender", 0),
                    action_link=magic_action_meta.get("read_more", ""))
                magic_actions.append(action)
    return magic_actions

# initialize the newest version of magic actions:
dirname = os.path.dirname(__file__)
action_versions = os.listdir(os.path.join(dirname, 'magic-actions', 'actions'))
action_versions.sort()
global_magic_action_version = action_versions[-1]

global_magic_actions = set_magic_actions("processing")
global_import_actions = set_magic_actions("import")
global_export_actions = set_magic_actions("export")

def set_version(version:str):
    global global_magic_action_version
    global global_magic_actions
    global global_import_actions
    global global_export_actions
    global_magic_action_version = version
    # set magic actions for that version
    global_magic_actions = set_magic_actions("processing")
    global_import_actions = set_magic_actions("import")
    global_export_actions = set_magic_actions("export")

def get_all_actions() -> list[MagicAction]:
    output = []
    output.extend(get_import_actions())
    output.extend(get_magic_actions())
    output.extend(get_export_actions())
    return output

def get_magic_actions() -> list[MagicAction]:
    return get_magic_actions_sorted(global_magic_actions)

def get_import_actions() -> list[MagicAction]:
    return get_magic_actions_sorted(global_import_actions)

def get_export_actions() -> list[MagicAction]:
    return get_magic_actions_sorted(global_export_actions)

def get_magic_actions_sorted(global_magic_action:list) -> list[MagicAction]:
    magic_action_sorted = list(filter(lambda x: x.ui_prio != -1, global_magic_action))
    magic_action_sorted.sort(key=lambda x: x.ui_prio, reverse=False)
    return magic_action_sorted

def get_version() -> str:
    return global_magic_action_version

class MagicActionOperator(bpy.types.Operator):
    bl_idname = "processor.magic_action_button"
    bl_label = "magic_action_button"
    bl_description = "Select Action"

    magic_action_str: bpy.props.StringProperty() # type: ignore

    def execute(self, context:bpy.types.Context) -> set:
        self.report({'INFO'}, f"Selected Magic Action: {self.magic_action_str}")
        bpy.types.Scene.rpde_selected_action = self.magic_action_str

        magic_action:MagicAction = next((action for action in get_all_actions()
                                                  if action.action_name == self.magic_action_str
                                                  and action.action_version == get_version()), None)

        # reset settings when magic action is selected
        resetSettingsToDefault(context)

        # sets all values of config and also activates all parents and sets oneofs for the options
        setValue(context, magic_action.action_config)

        self.toggle_action_options(context)
        return {'FINISHED'}

    def toggle_action_options(self, context:bpy.types.Context):
        magic_action:MagicAction = next((action for action in get_all_actions()
                                    if action.action_name == self.magic_action_str
                                    and action.action_version == get_version()), None)
        for option in magic_action.action_options:
            if option.option_toggled is not None:
                attribute_env, attribute = blend_scene_getattr(
                                    context.scene, path=option.option_path)
                setattr(attribute_env, attribute, option.option_toggled)

class ActivateMagicActionOperator(bpy.types.Operator):
    bl_idname = "processor.magic_enable"
    bl_description = "Enables magic action"
    bl_label = "magic_action_enable"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set:
        bpy.types.Scene.rpde_detail_mode = False
        return {'FINISHED'}

class DeactivateMagicActionOperator(bpy.types.Operator):
    bl_idname = "processor.magic_action_disable"
    bl_description = "Enables manual settings"
    bl_label = "magic_action_disable"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set:
        bpy.types.Scene.rpde_detail_mode = True
        return {'FINISHED'}

class DescriptionOperator(bpy.types.Operator):
    bl_idname = "processor.magic_action_description"
    bl_description = "Read More"
    bl_label = "magic_action_description"
    bl_options = {'REGISTER', 'UNDO'}

    link: bpy.props.StringProperty()  #type: ignore

    def execute(self, context:bpy.types.Context) -> set:
        webbrowser.open(self.link)
        return {'FINISHED'}

def register():
    reg()

def unregister():
    unreg()

clss = (ActivateMagicActionOperator, DeactivateMagicActionOperator,
        MagicActionOperator, DescriptionOperator,
        )

reg, unreg = bpy.utils.register_classes_factory(clss)
