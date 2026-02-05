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

from .main import MainData
from .ProcessorPluginsCommon.magic_actions.utils import MagicAction as CommonMagicAction
from .ProcessorPluginsCommon.magic_actions.utils import import_magic_actions
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

class MagicAction(CommonMagicAction):
    ui_prio = 0
    action_options:list[MagicActionOption] = []
    action_link:str = ""

    def __init__(self,
                 name:str,
                 description:str,
                 action_config:dict,
                 action_meta:dict,
                 version:str,
                 action_image:str = "",
                 icon_dark:str = ""):
        super().__init__(name=name, version=version, description=description, action_config=action_config,
                         action_meta=action_meta, action_video="", action_gif=action_image, icon_dark=icon_dark, 
                         icon_light="")
        self.ui_prio = self.ui_prio_hints['blender']
        self.action_options = self.set_options()
        self.action_link = self.meta.get("read_more", "")

    def set_options(self) -> list[MagicActionOption]:
        action_options = []
        exposed_options:list[dict] = self.meta["exposed_options"]
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

def set_magic_actions(type:str, version_str) -> list[MagicAction]:
    commons_actions:list[CommonMagicAction] = [] #import_magic_actions(dirname)[global_magic_action_version][type]
    main_data = MainData()
    import_actions, process_actions, export_actions = main_data.getActionsByVersion(version_str)
    if type == 'processing':
        commons_actions:list[CommonMagicAction] = process_actions
    if type == 'import':
        commons_actions:list[CommonMagicAction] = import_actions
    if type == 'export':
        commons_actions:list[CommonMagicAction] = export_actions

    blender_actions:list[MagicAction] = []
    for commons_action in commons_actions:
        path = commons_action.gif_path.split(r"\video.gif")[0]
        image_path = os.path.join(path, "image.png")
        blender_action = MagicAction(commons_action.name, commons_action.description, commons_action.config,
                                     commons_action.meta, commons_action.version, image_path, commons_action.icon_dark_path)
        blender_actions.append(blender_action)

    return blender_actions

# initialize the newest version of magic actions:
dirname = os.path.dirname(__file__)
action_versions = os.listdir(os.path.join(dirname, 'magic-actions', 'actions'))
action_versions.sort()
global_magic_action_version = action_versions[-1]

global_magic_actions = []
global_import_actions = []
global_export_actions = []

for version in action_versions:
    global_magic_actions.extend(set_magic_actions("processing", version))
    global_import_actions = (set_magic_actions("import", action_versions[-1]))
    global_export_actions = (set_magic_actions("export", action_versions[-1]))

def set_version(version:str=None):
    global global_magic_action_version
    global global_magic_actions
    global global_import_actions
    global global_export_actions
    if version:
        global_magic_action_version = version
    # set magic actions for that version
    global_magic_actions = set_magic_actions("processing", global_magic_action_version)
    global_import_actions = set_magic_actions("import", global_magic_action_version)
    global_export_actions = set_magic_actions("export", global_magic_action_version)

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

def get_magic_actions_sorted(action:list) -> list[MagicAction]:
#    print("get magic action soted")
#    print(main_data.process_actions)
#    magic_action_sorted = list(filter(lambda x: x.ui_prio != -1, global_magic_action))
#    magic_action_sorted.sort(key=lambda x: x.ui_prio, reverse=False)
#    print(f"there after sort: {magic_action_sorted}")
    return action #NOTE actions from common are already sorted #TODO delete this function

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
                                                  if action.name == self.magic_action_str
                                                  and action.version == get_version()), None)

        # reset settings when magic action is selected
        resetSettingsToDefault(context)

        # sets all values of config and also activates all parents and sets oneofs for the options
        setValue(context, magic_action.config)

        self.toggle_action_options(context)
        return {'FINISHED'}

    def toggle_action_options(self, context:bpy.types.Context):
        magic_action:MagicAction = next((action for action in get_all_actions()
                                    if action.name == self.magic_action_str
                                    and action.version == get_version()), None)
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
