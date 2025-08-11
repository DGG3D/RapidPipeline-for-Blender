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
from sys import platform
from typing import Any

import bpy  # type: ignore
import bpy.utils.previews  # type: ignore

# defines user appdata folder for the plugin
base_dcc_data_folder = os.path.join(
    os.path.expanduser("~"), 'Documents') if 'darwin' in platform else os.getenv("LOCALAPPDATA")
os.environ["RPDP_PROCESSOR_DCC_DATA"] = os.path.join(base_dcc_data_folder, "RapidPipeline 3D Processor Plugins")

from .compound_elements import OneOfWidget, get_ui_elements_dict
from .gui_commons import SettingsValidator, UIElement, UserDialog
from .json_utils import JSonUtils
from .scene_utils import get_uuid

validator = SettingsValidator()

def unpackdict(settings:dict, output_list:list[tuple[str, Any, str]], path:list) -> list[tuple[str, Any, str]]:
    copy_path = path.copy()
    for key, value in settings.items():
        if key == 'export':
            if isinstance(value, list) and len(value) > 0:
                value = value[0]    #unpack list of export settings
        path.append(key)
        if isinstance(value, list):
            output_list.append((key, value, path)) # Output list (name, value, path)
        if isinstance(value, dict):
            if len(value) == 0:
                output_list.append((key, True, path.copy())) # To activate panels
            else:
                output_list.append((key, list(value.keys())[0], path.copy())) # To activate panels
            unpackdict(value, output_list, path)
        if not isinstance(value, dict) and not isinstance(value, list):
            output_list.append((key, value, path)) # Output list (name, value, path)
        path = copy_path.copy()

    return output_list

def resetSettingsToDefault(context:bpy.types.Context):
    """
    Resets all the UI element settings to their default values.
    """
    from .draw_ui import root_children
    for element in root_children:
        element.setDefaultValue(context)

def setValue(context:bpy.types.Context, settings:dict):
    list_of_settings: list[tuple[str, Any, set]] = unpackdict(settings, [], [])

    for (_, value, path) in list_of_settings:
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(path)]
        except Exception:
            print(f"Warning, could not set config of path: {path}")
            continue

        #test: try to set ONEOF if its there
        ui_element_oneof = None
        try:
            oneof_path = set(path.copy())
            oneof_path.add("Oneof")
            ui_element_oneof:OneOfWidget = get_ui_elements_dict()[get_uuid(oneof_path)]
        except:  # noqa: E722, S110
            pass
        if ui_element_oneof:
            # set Oneof to correct value
            ui_element_oneof.setValue(value, context)

        ui_element.setValue(value, context)

def discard_settings(settings:dict, key:str) -> dict:
    for k, v in settings.items():
        if k == key:
            del settings[key]
            return settings
        if isinstance(v, dict):
            settings[k] = discard_settings(v, key)
            return settings
    return settings


class LoadOperator(bpy.types.Operator):
    bl_idname = "object.load"
    bl_description = "Load a custom .json settings file"
    bl_label = "Load JSON Preset"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH') # type: ignore

    def execute(self, context:bpy.types.Context) -> set[str]:
        if self.filepath.endswith('.json'):
            self.importSettings(self.filepath, context)
        else:
            self.report({'WARNING'}, "The selected file does not have a valid extension (.json).")
        return {'FINISHED'}

    # Define a function to trigger the file browser
    def invoke(self, context:bpy.types.Context, event:bpy.types.Event) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


    def importSettings(self, load_path:str, context:bpy.types.Context) -> None:
        dialog_file = load_path

        # if the user canceled, return
        if not dialog_file:
            return

        if not os.path.isfile(dialog_file):
            print(f"Settings file wasn't loaded successfully: {dialog_file}.")
            retry_label = "There was an error loading the settings file, or it doesn't exist."
            if not UserDialog.errorRetry(self, "Error Loading Settings", retry_label):
                return
            else:
                return self.importSettings()

        # validate settings with RPDE
        if not validator.validate(dialog_file):
            print(f"Settings file was invalid: {dialog_file}.")
            retry_label = "The settings file provided failed validation by the RapidPipeline 3D Processor."
            self.layout.label(text="The settings file provided failed validation by the RapidPipeline 3D Processor.",
                              icon="ERROR")
            dialog_file = None
            return

        # load settings file into dict
        settings = JSonUtils.loadJSON(dialog_file)

        # discard non used parts of settings (eg. import and export)
        settings = discard_settings(settings, "import")

        if not settings:
            print(f"Settings file was invalid: {dialog_file}.")
            retry_label = "The settings file provided is invalid or empty."
            if not UserDialog.errorRetry(self, "Error Loading Settings", retry_label):
                return
            else:
                return self.importSettings()

        print(f"The settings file {dialog_file} is valid.")

        # first, reset to default - important to toggle everything off
        resetSettingsToDefault(context)

        # apply loaded settings to the UI - will automatically toggle them on
        setValue(context, settings)

class SaveOperator(bpy.types.Operator):
    bl_idname = "processor.save"
    bl_description = "Save out the current settings as a .json file"
    bl_label = "Save JSON Preset"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH') # type: ignore

    def execute(self, context:bpy.types.Context) -> set[str]:
        if self.filepath:
            self.exportSettings(self.filepath, context)
        return {'FINISHED'}

    # Define a function to trigger the file browser
    def invoke(self, context:bpy.types.Context, event:bpy.types.Event) -> set[str]:
        self.filepath = ".json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def exportSettings(self, file_path:str, context:bpy.types.Context) -> None:
        print("export settings")

        dialog_file = file_path

        # if the user canceled, return
        if not dialog_file:
            return

        # build settings from current UI input
        settings_json = {}
        from .draw_ui import root_element
        settings_json = root_element.getSettings()

        os.makedirs(os.path.dirname(dialog_file), exist_ok=True)
        if not str(dialog_file).endswith('.json'):
            dialog_file += '.json'
        if not JSonUtils.saveJSON(settings_json, dialog_file):
            print(f"Settings file wasn't saved successfully: {dialog_file}.")
            confirm_label = "There was an error saving the settings file."
            if not UserDialog.errorRetry(self, "Error Saving Settings", confirm_label):
                return
            else:
                return self.exportSettings()

        if not validator.validate(dialog_file):
            critical_label = "The exported settings file failed settings validation, the plugin will now close."
            UserDialog.critical(self, "Critical Error", critical_label)

        print(f"Settings file saved successfully at: {dialog_file}.")
        confirm_label = "The settings file were saved successfully."
        UserDialog.okInfo(self, "Save Successful", confirm_label)


class DefaultsOperator(bpy.types.Operator):
    bl_idname = "processor.default"
    bl_description = "Reset all settings to their default states"
    bl_label = "default"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        self.defaultSettings(context)
        return {'FINISHED'}

    def defaultSettings(self, context:bpy.types.Context) -> None:
        """
        Callback to provide dialog to user and apply default settings, if confirmed.
        """
        #TODO ask user for confirmation

        print("Reset to defaults: ")
        resetSettingsToDefault(context)

class CancelProcessorOperator(bpy.types.Operator):
    bl_idname = "processor.cancel_processor"
    bl_description = "Cancel the current process"
    bl_label = "Cancel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        bpy.types.Scene.rpde_running = False
        bpy.types.Scene.rpde_error = False
        bpy.types.Scene.rpde_cancel = True
        return {'FINISHED'}

class RetryProcessorOperator(bpy.types.Operator):
    bl_idname = "processor.retry_processor"
    bl_description = "Retry the current process"
    bl_label = "Retry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        print("Retry RapidPipeline...")
        bpy.types.Scene.rpde_running = False
        bpy.types.Scene.rpde_error = False
        bpy.ops.processor.run()
        return {'FINISHED'}

class RestartUIOperator(bpy.types.Operator):
    bl_idname = "processor.restart_processor"
    bl_description = "restart_processor_token"
    bl_label = "Restart"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        print("Reloading UI...")
        bpy.types.Scene.rpde_UI_error = False
        return {'FINISHED'}
