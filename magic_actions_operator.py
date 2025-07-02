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

import json
import os

import bpy  # type: ignore

from .basic_elements import UIElement
from .scene_utils import get_ui_element
from .settings_operator import resetSettingsToDefault, setValue
from .json_utils import JSonUtils

preview_collections = {}


class MagicActionOption():
    option_path = set()
    option_name = ""
    option_description = ""
    ui_element:UIElement = None

    def __init__(self, path:set, name:str="", description:str=""):
        self.option_path = path
        self.option_name = name
        self.option_description = description
        self.ui_element = get_ui_element(path)

magic_actions_options:list[MagicActionOption] = []

class MagicAction():
    action_name = ""
    action_description = ""
    path = ""
    action_config = {}

    def __init__(self, name:str, description:str, action_config:dict, path:str):
        self.action_name = name
        self.action_description = description
        self.action_config = action_config
        self.path = path

class MagicActionProperties(bpy.types.PropertyGroup):
    magic_actions:list[MagicAction] = []
    dirname = os.path.dirname(__file__)
    magic_action_folder = os.path.join(dirname, 'magic-actions', 'actions')

    warning_msg: bpy.props.StringProperty(default="") # type: ignore

    if os.path.isdir(magic_action_folder):
        for magic_action in os.listdir(magic_action_folder):
            if os.path.isdir(os.path.join(magic_action_folder, magic_action)):
                magic_action_meta_path = os.path.join(magic_action_folder, magic_action, "meta.json")
                magic_action_config_path = os.path.join(magic_action_folder, magic_action, "rpd_config.json")
                magic_action_meta = JSonUtils.loadJSON(magic_action_meta_path)
                magic_action_config = JSonUtils.loadJSON(magic_action_config_path)
                name = magic_action_meta.get("name", magic_action_meta.get("title", ""))
                description = magic_action_meta.get("description", "")
                # do not displac magic actions that include cad import
                if "is_import_action" in magic_action_meta and magic_action_meta["is_import_action"]:
                    continue
                action = MagicAction(
                    name,
                    description,
                    magic_action_config,
                    os.path.join(magic_action_folder, magic_action))
                magic_actions.append(action)
    else:
        print("Warning: Could not find magic actions folder!")

    def update_action(self, context:bpy.types.Context):
        selected_option = self.dropdown_selection
        self.warning_msg = "Please choose a valid option"
        magic_actions_options.clear()

        for magic_action in self.magic_actions:
            if selected_option == magic_action.action_name:
                # reset settings when magic action is selected
                resetSettingsToDefault(context)

                setValue(context, magic_action.action_config)
                # create settings based on "exposed_options" as props
                magic_action_meta_path = os.path.join(magic_action.path, "meta.json")
                magic_action_meta = JSonUtils.loadJSON(magic_action_meta_path)
                exposed_options:list[dict] = magic_action_meta["exposed_options"]
                for option in exposed_options:
                    if 'path' in option:
                        option_path:str = option["path"]
                        # if option has no name we take the last part of the path for now
                        #TODO search name and description in schema if no short title given
                        option_name = option.get("shortTitle", option_path.split('.')[-1])
                        option_description = option.get("description", "")
                        path_set = set(option_path.split('.'))
                        # dont display import options
                        if "import" in path_set:
                            continue
                        option = MagicActionOption(path_set, option_name, option_description)
                        magic_actions_options.append(option)
                        option.ui_element.activateAllParents()
                break

    def enum_items(self, context:bpy.types.Context) -> list:
        enum_items = []
        enum_items.append(("Choose a Magic Action", "Choose a Magic Action", "Choose a Magic Action"))
        for idx, magic_action in enumerate(self.magic_actions):
            enum_items.append(
                (self.magic_actions[idx].action_name,
                 self.magic_actions[idx].action_name,
                 self.magic_actions[idx].action_description,
                 getattr(context.scene, f"magic_action_{os.path.basename(magic_action.path)}").icon_id, idx+1))
        return enum_items

    dropdown_selection: bpy.props.EnumProperty(
        name="",
        description="Choose a Magic Action",
        items=enum_items,
        default=0,
        update = update_action
    ) # type: ignore


class ActivateMagicActionOperator(bpy.types.Operator):
    bl_idname = "processor.magic_enable"
    bl_description = "Enables magic action"
    bl_label = "magic_action_enable"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set:
        bpy.types.Scene.rpde_magicAction = True
        return {'FINISHED'}

class DeactivateMagicActionOperator(bpy.types.Operator):
    bl_idname = "processor.magic_action_disable"
    bl_description = "Enables manual settings"
    bl_label = "magic_action_disable"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set:
        bpy.types.Scene.rpde_magicAction = False
        return {'FINISHED'}

def register():
    reg()

    pcoll = bpy.utils.previews.new()
    dirname = os.path.dirname(__file__)
    if os.path.isdir(os.path.join(dirname, 'magic-actions')):
        magic_action_folder = os.path.join(dirname, 'magic-actions', 'actions')
        for magic_action in os.listdir(magic_action_folder):
            if os.path.isdir(os.path.join(magic_action_folder, magic_action)):
                icon_dir = os.path.join(magic_action_folder, magic_action, 'icon-dark.svg')
                pcoll.load(f"magic_action_{magic_action}", icon_dir, 'IMAGE')

    preview_collections["main"] = pcoll
    bpy.types.Scene.magic_action_property = bpy.props.PointerProperty(type=MagicActionProperties)

def unregister():
    unreg()

clss = (MagicActionProperties, ActivateMagicActionOperator, DeactivateMagicActionOperator,
        )

reg, unreg = bpy.utils.register_classes_factory(clss)
