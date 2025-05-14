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
import queue
import shutil
import subprocess
import textwrap
import traceback
import webbrowser
from abc import abstractmethod
from sys import platform
from typing import Any, List

import bpy  # type: ignore
import bpy.utils.previews  # type: ignore

# defines user appdata folder for the plugin
base_dcc_data_folder = os.path.join(os.path.expanduser("~"), 'Documents') if 'darwin' in platform else os.getenv("LOCALAPPDATA")
os.environ["RPDP_PROCESSOR_DCC_DATA"] = os.path.join(base_dcc_data_folder, "RapidPipeline 3D Processor Plugins")

from .about_dialog import AboutDialog, AboutDialogPanel
from .basic_elements import (
    BooleanPropertyGroup,
    ColorPropertyGroup,
    FloatPropertyGroup,
    GroupWidgetPropertyGroup,
    IntegerPropertyGroup,
    StringPropertyGroup,
)
from .cad_import import CADImportOperator
from .compound_elements import GroupPanel, SimpleContainer, TabElement, get_ui_elements_dict, init_ui_element
from .gui_commons import ProcessorPlugin, SettingsValidator, UIElement, UserDialog
from .json_utils import JSonUtils
from .license_manager import ProcessorLicense
from .progress_dialog import ProgressDialog
from .run_rpde import RunPipeline
from .scene_utils import (
    blend_scene_getattr,
    blend_scene_init_setattr,
    blend_scene_setattr,
    blend_scene_setattr_enum,
    get_uuid,
    set_uuid,
)

preview_collections = {}
uuid_paths = {} #key: uuid value: paths of schema

execution_queue = queue.Queue()
rpde_status = None

def enum(**enums:dict[str,str]) -> type:
    return type('Enum', (), enums)

class Tabs:
    tabs = enum(IMPORT = "Import",
                SCENEGRAPHFLATTENING = "Scene Graph Flatting",
                EDIT = "3D Edit",
                MESHCULLING = "Mesh Culling",
                OPTIMIZE = "Optimize",
                MODIFIER = "Modifier",
                EXPORT = "Export"
                )

class LevelOperator(bpy.types.Operator):
    bl_idname = "processor.level"
    bl_description = "Choose the level of settings shown"
    bl_label = "level"
    bl_options = {'REGISTER', 'UNDO'}

    level: bpy.props.StringProperty(options={'HIDDEN'}) # type: ignore

    def execute(self, context:bpy.types.Context) -> set[str]:
        print(f"Scene level is now: {self.level}")
        context.scene.level = self.level
        return {'FINISHED'}

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
        if not MainPanel.validator.validate(dialog_file):
            print(f"Settings file was invalid: {dialog_file}.")
            retry_label = "The settings file provided failed validation by the RapidPipeline 3D Processor."
            self.layout.label(text="The settings file provided failed validation by the RapidPipeline 3D Processor.",
                              icon="ERROR")
            dialog_file = None
            return

        # load settings file into dict
        settings = JSonUtils.loadJSON(dialog_file)
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

#        # apply loaded settings to the UI - will automatically toggle them on
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

        if not MainPanel.validator.validate(dialog_file):
            critical_label = "The exported settings file failed settings validation, the plugin will now close."
            UserDialog.critical(self, "Critical Error", critical_label, self.validator.getLogLines())
#                self.main_application.quit()

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

class HelpOperator(bpy.types.Operator):
    bl_idname = "processor.help"
    bl_description = "Open the RapidPipeline Documentation Website"
    bl_label = "help"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        self.helpLink()
        return {'FINISHED'}

    def helpLink(self):
        webbrowser.open(r"https://docs.rapidpipeline.com/docs/3dProcessor-Tutorials/blender-plugin-tutorials")

class RPDEPanel (bpy.types.Panel):
    bl_idname = "VIEW3D_PT_processor"
    bl_description = "processor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_label = "processor_output"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context:bpy.types.Context) -> bool:
        return context.scene.rpde_running and not context.scene.rpde_error

    def draw(self, context:bpy.types.Context):
        self.layout.prop(context.scene, "rpde_percentage", text="Progress", slider=True)
        self.layout.label(text=context.scene.rpde_output)

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
#        unregister()
#        register()
        return {'FINISHED'}


class RunOperator(bpy.types.Operator):
    bl_idname = "processor.run"
    bl_description = "Run RapidPipeline 3D Processor with the selected settings"
    bl_label = "run"
    bl_options = {'REGISTER', 'UNDO'}

    output_cmd: bpy.props.StringProperty() # type: ignore

    # define file paths
    extension = os.environ.get("RPDP_PROCESSOR_DCC_OUTPUT", "glb")
    import_extension = "glb"
    output_folder: str = os.environ["RPDP_PROCESSOR_DCC_DATA"]
    output_filename = ""

    def execute(self, context:bpy.types.Context) -> set[str]:
        if context.scene.rpde_running:
            bpy.types.Scene.rpde_running = False
            self.processFinished()
        else:
            print("execute run")
            self.chooseFolderAndRunPipeline(context)
        return {'FINISHED'}

    def chooseFolderAndRunPipeline(self, context:bpy.types.Context):
        """
        Disables elements, and starts RapidPipeline process with the current UI settings.
        A file with the current settings is exported and validated.
        """
        # build settings from current UI input
        current_settings = root_element.getSettings()
        current_settings["export"] = [
            {
                "fileName": "",
                "textureMapFilePrefix": "",
                "discard": {},
                "format": {
                    "glb": {
                    "pbrMaterial": {}
                    }
                }
            }
        ]

        # make sure to get the correct filename
        current_name = current_settings["export"][0].get("fileName", "")
        if not current_name:
            self.output_filename = "rpde_file"
        else:
            self.output_filename = current_name

        json_path = self.getOutputJSonPath()
        if not JSonUtils.saveJSON(current_settings, json_path):
            error_message = "Unable to save temporary settings file for RapidPipeline execution."
            UserDialog.critical(self, "Unable to Run RapidPipeline", error_message)
#            self.main_application.quit()
        print(f"Exported Settings: {json_path}")

        # exports model to predefined file location
        input_file = self.getProcessorInputFile()
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        copied_nodes = self.exportModel(input_file)
        if not os.path.isfile(input_file):
            print(f"ERROR: File {input_file} not found.")
            error_label = "Unable to process file with RapidPipeline 3D Processor, input file not found. "
            error_label += "This is likely an error with the DCC export."
            UserDialog.critical(self, "File Not Found", error_label)
            return

        output_json_path = self.getOutputJSonPath()
        RunPipeline.runPipeline(input_file, output_json_path, self.output_folder, copied_nodes)


    def getOutputJSonPath(self) -> str:
        return os.path.join(self.getExecutionOutputFolder(), "rpdp_dcc_plugin_settings.json")

    def getExecutionInputFolder(self) -> str:
        return os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "0_glb")


    def getProcessorInputFile(self) -> str:
        return os.path.join(self.getExecutionOutputFolder(), f"{self.output_filename}.{self.extension}")

    def getExecutionOutputFolder(self) -> str:
        return os.path.join(self.output_folder, f"0_{self.extension}")

    @abstractmethod
    def exportModel(self, file_path: str) -> list:
        """
        Exports model to be run by the RapidPipeline 3D Processor Engine
        """
        export_path = os.path.dirname(file_path)
        os.makedirs(export_path, exist_ok=True)

        window = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window = window):
            export_selection = bpy.context.selected_objects

            if (len(export_selection) == 0):    # No objects selected -> select all objects
                for o in list(bpy.data.objects):
                    o.select_set(True)
                    export_selection.append(o)

            #NOTE We need to copy the object since we apply modifiers before the export step
            # duplicate nodes (duplicated nodes are now selected):
            bpy.ops.object.duplicate()
            copied_nodes = bpy.context.selected_objects
            bpy.ops.object.select_all(action='DESELECT')

            for idx, o in enumerate(copied_nodes):
                # When only child is selected the duplicated child will then stay a child of the existing parent.
                if o.parent not in copied_nodes:
                    parented_wm = o.matrix_world.copy()
                    o.parent = None
                    o.matrix_world = parented_wm

                o.name = export_selection[idx].name + "_processed"

                if o.type == 'MESH':
                    for _, m in enumerate(o.modifiers):
                        try:
                            bpy.ops.object.modifier_apply(modifier=m.name)
                        except Exception:
                            print("Error in applying modifiers.")

            for original_node in export_selection:
                original_node.select_set(False)
                if original_node.type == 'MESH':
                    original_node.hide_set(True)

            # select all copied nodes and export
            for object in copied_nodes:
                object.select_set(True)
            try:
                bpy.ops.export_scene.gltf(
                    export_format='GLB', use_active_scene=True, use_selection=True, filepath=file_path)
            except Exception:
                print(f"Could not export glb file: {file_path}")
                print(traceback.format_exc())

        return copied_nodes

    @abstractmethod
    def importModel(self, file_path: str):
        """
        Reimports model run by the RapidPipeline 3D Processor Engine
        """
        # create parent relations for collections
        parent = dict()
        for c in bpy.data.collections:
            parent[c] = None
        for c in bpy.data.collections:
            for ch in c.children:
                parent[ch] = c

        # deleting existing meshes
        window = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window = window):
            objects_collections = {}    # dict(node_name : collection)
            selection = bpy.context.selected_objects
            bpy.ops.object.select_all(action='DESELECT')
            for o in selection:
                objects_collections[o.name] = (o.users_collection)    # retaining collections
                o.select_set(True)
                bpy.ops.object.delete()

            # Workaround for a missing feature in the blender API
            # see: https://blender.stackexchange.com/questions/202675/python-hide-collection-turn-off-the-eyeball-icon-of-collection-in-outliner
            def search_collection(parent:bpy.types.Collection, name:str) -> bpy.types.Collection:
                if parent.name == name:
                    return parent
                for c in parent.children:
                    coll = search_collection(c, name)
                    if coll:
                        return coll
                return None

            # if all nodes of a collection are hidden, unhide nodes and hide collection instead
            used_collections = [x for xs in objects_collections.values() for x in xs] # get all used collections
            try:
                for collection in used_collections:
                    vlayer = bpy.context.scene.view_layers['ViewLayer']
                    all_nodes_hidden = True
                    for node in collection.all_objects:
                        if not node.hide_get() and "_processed" not in node.name:
                            all_nodes_hidden = False
                            break
                    if all_nodes_hidden:
                        found_collection = search_collection(vlayer.layer_collection, collection.name)
                        if found_collection:
                            found_collection.hide_viewport = True    #hide the collection
                            for node in collection.all_objects:
                                node.hide_set(False)
            except Exception:
                print("Warning: could not hide collection")

            # import glb
            try:
                bpy.ops.import_scene.gltf(filepath=file_path)
            except Exception:
                print(f"Could not import glb file: {file_path}")
                print(traceback.format_exc())

            scene_collection = bpy.data.scenes["Scene"].collection
            objects_in_scene = bpy.data.objects

            # case for CAD import
            if not objects_collections:
                if "_CAD_import" not in bpy.data.collections:
                    cad_collection = bpy.data.collections.new("_CAD_import")
                    bpy.context.scene.collection.children.link(cad_collection)
                else:
                    cad_collection = bpy.data.collections["_CAD_import"]

                #unhide _CAD_import collection
                vlayer = bpy.context.scene.view_layers['ViewLayer']
                processing_collection_viewport = search_collection(vlayer.layer_collection, cad_collection.name)
                processing_collection_viewport.hide_viewport = False

                for node in objects_in_scene:
                    try:
                        scene_collection.objects.unlink(node)
                        cad_collection.objects.link(node)
                    except:  # noqa: S112, E722
                        continue
            else:
                if "_processed" not in bpy.data.collections:
                    processing_collection = bpy.data.collections.new("_processed")
                    bpy.context.scene.collection.children.link(processing_collection)
                else:
                    processing_collection = bpy.data.collections["_processed"]

                #unhide _processed collection
                vlayer = bpy.context.scene.view_layers['ViewLayer']
                processing_collection_viewport = search_collection(vlayer.layer_collection, processing_collection.name)
                processing_collection_viewport.hide_viewport = False

                # Move nodes back into collection
                for node_name,collections in objects_collections.items():
                    try:
                        scene_collection = bpy.data.scenes["Scene"].collection
                        for collection in collections:
                            collection_copy = self.moveCollectionIntoProcessed(collection, processing_collection, parent, True)
                            if node_name in objects_in_scene:
                                collection_copy.objects.link(objects_in_scene[node_name])
                        if node_name in objects_in_scene:
                            scene_collection.objects.unlink(objects_in_scene[node_name])
                    except Exception:
                        print("Warning: original node names or collections could not be found.")
                        print("Placing node in 'Scene Collection' instead.")

    # Take any collection as an input, find all its parents and then move all the parents an itself to the
    # _processed collection. Returns a copy of the input collection in its correct hierachy
    def moveCollectionIntoProcessed(
            self,
            collection:bpy.types.Collection,
            processing_collection:bpy.types.Collection,
            parent: dict,
            initial_call = False) -> bpy.types.Collection:

        scene_collection = bpy.data.scenes["Scene"].collection
        collections_names = [collection.name for collection in bpy.data.collections]
        coll_processed_name = collection.name + "_processed"

        if collection == scene_collection:
            return processing_collection
        #if (coll_processed_name) not in collections_names:
        if initial_call or (coll_processed_name) not in collections_names:
            collection_copy = bpy.data.collections.new(coll_processed_name)
        else:
            return bpy.data.collections[(coll_processed_name)] # collection was already moved

        # If collection on lowest level, move "<collection>_processed" into "_processed"
        if collection in list(scene_collection.children):
            bpy.data.collections[processing_collection.name].children.link(bpy.data.collections[collection_copy.name])
        else:
            if parent[collection]:  # get all parent collections...
                parent_collection = self.moveCollectionIntoProcessed(parent[collection], processing_collection, parent)
                try:
                    bpy.data.collections[parent_collection.name].children.link(bpy.data.collections[collection_copy.name])
                except Exception:
                    print(f"{collection_copy.name} already in {parent_collection.name}")
        return collection_copy

    def processFinished(self):
        current_settings = root_element.getSettings()
        current_settings["export"] = [
            {
                "fileName": "",
                "textureMapFilePrefix": "",
                "discard": {},
                "format": {
                    "glb": {
                    "pbrMaterial": {}
                    }
                }
            }
        ]

        current_name = current_settings["export"][0].get("fileName", "")
        if not current_name:
            self.output_filename = "rpde_file"
        else:
            self.output_filename = current_name

        input_file = self.getInputFilePath()

        self.importModel(input_file)

        # removes temporary input tree
        shutil.rmtree(self.getExecutionInputFolder())

        # finished successfully, display a msg to the user
        confirm_label = "The RapidPipeline 3D Processor finished running successfully."
        UserDialog.okInfo(self, "Process Successful", confirm_label)

        print("Process Successful")

    def getOutputFilePath(self) -> str:
        return os.path.join(self.getExecutionOutputFolder(), f"{self.output_filename}.{self.extension}")

    def getInputFilePath(self) -> str:
        return os.path.join(self.getExecutionInputFolder(), f"{self.output_filename}.{self.import_extension}")

def execute_queued_functions() -> float:
    while not execution_queue.empty():
        function = execution_queue.get()
        function()
    return 1.0

def get_children(parent:UIElement) -> list[UIElement]:
    child_nodes = [parent]
    if hasattr(parent, 'child_elements'):
        for child in parent.child_elements:
            child_nodes.extend(get_children(child))
    return child_nodes

def resetSettingsToDefault(context:bpy.types.Context):
    """
    Resets all the UI element settings to their default values.
    """
    for element in root_children:
        element.setDefaultValue(context)

def unpackdict(settings:dict, output_list:list[tuple[str, Any, str]], path:list) -> list[tuple[str, Any, str]]:
    copy_path = path.copy()
    for key, value in settings.items():
        if key == 'export':
            continue
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

def setValue(context:bpy.types.Context, settings:dict):
    list_of_settings: list[tuple[str, Any, str]] = unpackdict(settings, [], [])

    for (_, value, path) in list_of_settings:
        ui_element:UIElement = get_ui_elements_dict()[get_uuid(uuid_paths, path)]

        # set Oneof to correct value
        ui_element.setValue(value, context)

# loads metadata file
processor_plugin = ProcessorPlugin()
processor_plugin.loadPluginMetadata()

# reset widgets, load schema and UI rules
processor_plugin.reset()
processor_plugin.loadSchema()
processor_plugin.loadUIRules()
schema = processor_plugin.getSolvedSchema()

root_element:TabElement = init_ui_element("", "", uuid_dict=uuid_paths, schema=schema)

root_children = list(get_children(root_element))

class ButtonPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_Buttons"
    bl_label = "RapidPipeline Button"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context:bpy.types.Context) -> bool:
        return not context.scene.rpde_running and context.scene.has_license and not context.scene.rpde_UI_error

    def draw(self, context:bpy.types.Context):
        pcoll = preview_collections["main"]
        help_icon = pcoll["help"]
        about_icon = pcoll["about"]
        bottom_layout = self.layout.row()
        bottom_layout.scale_y = 1.4
        bottom_layout.operator(HelpOperator.bl_idname, icon_value=help_icon.icon_id, text="Help")
        bottom_layout.operator(AboutDialog.bl_idname, icon_value=about_icon.icon_id, text="About")

class MainPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_RapidPipeline"
    bl_label = "RapidPipeline Processor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RapidPipeline"

    # height variables for scroll area
    height_diff = 0

    was_successful: bool = False
    was_cancelled: bool = False


    # variables for progress
    progress_dialog: ProgressDialog = None

    validator = SettingsValidator()

    def draw_header(self, context: bpy.types.Context):
        pcoll = preview_collections["main"]
        rapidpipeline_icon: bpy.types.Icons = pcoll["rapidPipeline"]
        self.layout.template_icon(icon_value=rapidpipeline_icon.icon_id, scale=1.2)

    def draw(self, context: bpy.types.Context):
        if context.scene.rpde_UI_error:
            drawUIError(self, context)
            return
        try:
            if context.scene.rpde_running or not context.scene.has_license:
                if context.scene.rpde_running and not context.scene.rpde_error:
                    running_layout = self.layout.row()
                    running_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
                if context.scene.rpde_error:
                    error_layout = self.layout.row()
                    error_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
                    error_layout.operator(RetryProcessorOperator.bl_idname, text="Retry")
                    rpde_output = context.scene.rpde_output
                    error_layout = self.layout.row()
                    prettyPrint(self, rpde_output, context)
                return

            def getExecutionButtons(layout:bpy.types.UILayout) -> None:
                pcoll = preview_collections["main"]
                load_icon = pcoll["load"]
                save_icon = pcoll["save"]
                defaults_icon = pcoll["defaults"]
                layout.scale_y = 1
                layout.operator(LoadOperator.bl_idname, icon_value=load_icon.icon_id, text="Load Preset")
                layout.operator(SaveOperator.bl_idname, icon_value=save_icon.icon_id, text="Save Preset")
                layout.operator(DefaultsOperator.bl_idname, icon_value=defaults_icon.icon_id, text="Defaults")

            pcoll = preview_collections["main"]
            import_icon = pcoll["import"]
            #NOTE only activate when CAD import is enabled in rpde version
            cad_import_layout = self.layout.row()
            cad_import_layout.scale_y = 1
            cad_import_layout.operator(CADImportOperator.bl_idname, icon_value=import_icon.icon_id, text="CAD Import")
            button_layout = self.layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
            getExecutionButtons(button_layout)
            run_layout = self.layout.row()
            pcoll = preview_collections["main"]
            run_icon = pcoll["run"]
            run_layout.scale_y = 1.6
            run_layout.operator(RunOperator.bl_idname, icon_value=run_icon.icon_id, text="Run")

            _ = self.layout.row()

            _ = self.layout.row()

            main_layout = self.layout.row()

            # loads, creates logo label
            self.logo_label = ProcessorPlugin.getLogoLabel()
            #TODO add logo lable to main layout

            # add widget for level selection
            main_layout.label(text="Level selection: ")
            self.level_widget = self.getLevelSelection(main_layout, context)
            main_layout = self.layout.row()

            _ = self.layout.row()

            _ = self.layout.row()

            tab_layout = self.layout.row()

            for _, child in enumerate(root_children):
                if isinstance(child, SimpleContainer):
                    child.draw_on_panel(tab_layout, context, self)

            _ = self.layout.row()

        except Exception:
            print("ERROR: Could not draw UI Components of RapidPipeline Blender Plugin.")
            bpy.types.Scene.rpde_UI_error = True

    def getLevelSelection(self, main_layout: bpy.types.UILayout, context:bpy.types.Context):
        """
        Radio button group, selecting the settings level to be displayed.
        """

        main_layout.scale_y = 1.3

        basic_level = main_layout.operator(
            LevelOperator.bl_idname,
            text="Basic",
            depress=bpy.context.scene.level == 'basic')
        basic_level.level = 'basic'
        advanced_level = main_layout.operator(
            LevelOperator.bl_idname,
            text="Advanced",
            depress=bpy.context.scene.level == 'advanced')
        advanced_level.level = 'advanced'
        expert_level = main_layout.operator(
            LevelOperator.bl_idname,
            text="Expert",
            depress=bpy.context.scene.level == 'expert')
        expert_level.level = 'expert'


    def levelButtonChanged(self):
        """
        Callback to hide or display elements according to their setting level, and update elements.
        """

        def levelToIndex(lvl_str: str) -> int:
            if lvl_str not in ProcessorPlugin.LEVELS:
                lvl_str = ProcessorPlugin.LEVELS[0]
            return ProcessorPlugin.LEVELS.index(lvl_str)

    def onDestroy(self):
        print("Cleaning up resources...")
        if os.path.isfile(ProcessorLicense.TEMP_LICENSE_FILE):
            os.remove(ProcessorLicense.TEMP_LICENSE_FILE)


clss = (MainPanel, BooleanPropertyGroup,
        IntegerPropertyGroup, FloatPropertyGroup, LevelOperator, ColorPropertyGroup,
        LoadOperator, SaveOperator, DefaultsOperator, HelpOperator, RunOperator,
        StringPropertyGroup, RPDEPanel,
        GroupWidgetPropertyGroup, CancelProcessorOperator, RetryProcessorOperator,
        RestartUIOperator,
        )

late_reg_clss = (ButtonPanel, AboutDialogPanel)

reg, unreg = bpy.utils.register_classes_factory(clss)
late_reg, late_unreg = bpy.utils.register_classes_factory(late_reg_clss)


def drawUIError(panel, context):
        error_layout = panel.layout.row()
        error_msg = """ERROR: Could not draw UI Components of RapidPipeline Blender Plugin. \n
        Please try to restart the RapidPipeline Plugin or contact Customer Support."""

        prettyPrint(panel, error_msg, context)
        error_layout.operator(RestartUIOperator.bl_idname, text="Restart")

#https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
def prettyPrint(panel, text:str, context:bpy.types.Context):
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            break
    for region in area.regions:
        if region.type == 'UI':
            panel_width = region.width
            break

    # Calculate the maximum width of the label
    uifontscale = 9 * context.preferences.view.ui_scale
    max_label_width = int(panel_width // uifontscale)

    # Split the text into lines and format each line
    for line in text.splitlines():
        # Remove leading and trailing whitespace
        line = line.strip()

        # Split the line into chunks that fit within the maximum label width
        for chunk in textwrap.wrap(line, width=max_label_width):
            panel.layout.label(text=chunk)

def create_subpanel(path:List[str], parent_panel:str, schema:dict, display_header:bool) -> GroupPanel:
    set_uuid(uuid_paths, set(path))
    id = f"VIEW3D_PT_Subpanel{get_uuid(uuid_paths, path).replace('-', '')}"
    header = {'HIDE_HEADER'} if not display_header else set()
    if id:
        if not hasattr(bpy.types, id):
            new_panel = type(id,
                (GroupPanel, bpy.types.Panel, ),
                {"bl_idname" : id, "bl_label" : schema.get("title", ""),
                    "bl_parent_id": parent_panel, "UI_elements": [],
                    "bl_options": header})
            if not hasattr(bpy.types, new_panel.bl_idname):
                bpy.utils.register_class(new_panel)
            return new_panel
        else:
            return getattr(bpy.types, id)
    return None

def add_ui_element_to_panel(path:List[str], panel:GroupPanel):
    if panel.bl_idname != "VIEW3D_PT_RapidPipeline":
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(uuid_paths, path)]
        except Exception:
            ui_element:UIElement = None
        if ui_element:
            if not isinstance(ui_element, SimpleContainer):
                panel.UI_elements.append(ui_element)
                ui_element.panel = panel

def add_parent_to_panel(in_path:List[str], panel:GroupPanel, schema_key:str):
    if schema_key:
        path = in_path.copy()
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(uuid_paths, path)]
        except Exception:
            print("Error could not find ui element to add to panel")
            ui_element:UIElement = None
        if ui_element:
            panel.parent_element = ui_element
    else:
        print("Error: could not find schema key for adding parent to panel")
        print(f"For Path: {in_path} and panel: {panel.bl_label}")

def setup_properties(schema: dict,
                     parent: dict = None,
                     path: List[str] = [],
                     schema_key:str = "",
                     parent_panel:str = ""):

    if isinstance(parent, dict) and parent.get('settingid', None) is not None:
        if schema_key:
            path.append(schema_key)

    if not parent_panel:
        parent_panel = create_subpanel(path, MainPanel.bl_idname, schema, display_header=False)
#        add_parent_to_panel(path, parent_panel, schema_key)
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
                                        schema_key=sub_schema, parent_panel=parent_panel)

        if not schema_key:
            continue

        if key == 'type':
            if schema['type'] == 'boolean':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=BooleanPropertyGroup, path=path,
                    value_function=bpy.props.BoolProperty(
                        default=schema['default'], description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'integer':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=IntegerPropertyGroup, path=path,
                    value_function=bpy.props.IntProperty(
                        default=schema['default'], min=schema.get('minimum', 0.0),
                        max=schema.get('maximum', 1_000_000), description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'string':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=StringPropertyGroup, path=path,
                    value_function=bpy.props.StringProperty(
                        default=schema['default'], description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'object':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id,
                    property_group=GroupWidgetPropertyGroup, path=path,
                    value_function=bpy.props.BoolProperty(default=False, description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)

            if schema['type'] == 'number':
                if 'percentage' in parent:
                        blend_scene_init_setattr(
                            bpy.types.Scene, attribute_id,
                            property_group=FloatPropertyGroup, path=path,
                            value_function=
                                bpy.props.FloatProperty(
                                    min=schema['minimum'],
                                    max=schema['maximum'],
                                    default=schema['default'],
                                    subtype='PERCENTAGE',
                                    description=schema.get("description", "")),
                                    uuid_dict=uuid_paths,
                                    value=schema['default'],
                                    toggable=('toggleable' in schema))
                        add_ui_element_to_panel(path, parent_panel)
                else:
                    if 'maximum' in schema:
                        value_function = bpy.props.FloatProperty(
                                min=schema.get('minimum', 0.0), max=schema['maximum'],
                                default=schema.get('default', 0.0), description=schema.get("description", ""))
                    else:
                        value_function = bpy.props.FloatProperty(
                                    min=schema.get('minimum', 0.0), default=schema.get('default', 0.0),
                                    description=schema.get("description", ""))
                    blend_scene_init_setattr(
                        bpy.types.Scene, attribute_id,
                        property_group=FloatPropertyGroup, path=path,
                        value_function=value_function, uuid_dict=uuid_paths,
                        toggable=('toggleable' in schema))
                    add_ui_element_to_panel(path, parent_panel)

            if schema['type'] == 'array' and 'default' in schema:
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=ColorPropertyGroup, path=path,
                    value_function=bpy.props.FloatVectorProperty(
                        default = (schema['default'][:3]), min=0.0, max=1.0, subtype='COLOR',
                        description=schema.get("description", "")),
                        uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)

        if key == 'enum':
            enum_options = []
            for element in schema['enum']:
                enum_options.append((element,)*3)
            blend_scene_setattr_enum(bpy.types.Scene, attribute_id, uuid_dict=uuid_paths,
                    property=bpy.props.EnumProperty(items=enum_options, description=schema.get("description", "")),
                    path=path)
            add_ui_element_to_panel(path, parent_panel)

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
            blend_scene_setattr_enum(bpy.types.Scene, attribute_id, uuid_dict=uuid_paths,
                    property=bpy.props.EnumProperty(items=oneof_elements, description=schema.get("description", "")),
                    path=path_oneof)
            add_ui_element_to_panel(path_oneof, parent_panel)

            path_tmp = path.copy()
            for oneof_sub_schema in schema['oneOf']:
                if isinstance(oneof_sub_schema, dict):
                    setup_properties(schema=oneof_sub_schema,
                                        parent=schema.copy(),
                                        path=path_tmp, schema_key= None,
                                        parent_panel=parent_panel)
                path=path_tmp

        path= temp_path



def setup_icons():
    pcoll = bpy.utils.previews.new()
    dirname = os.path.dirname(__file__)
    rapid_pipeline_icon_dir = os.path.join(dirname, 'resources', 'images', 'Icon_solid_green.png')
    edit_icon_dir =           os.path.join(dirname, 'resources', 'images', '3dEdit.svg')
    import_icon_dir =         os.path.join(dirname, 'resources', 'images', 'import.svg')
    scene_graph_icon_dir =    os.path.join(dirname, 'resources', 'images', 'sceneGraphFlattening.svg')
    mesh_culling_icon_dir =   os.path.join(dirname, 'resources', 'images', 'meshCulling.svg')
    optimize_icon_dir =       os.path.join(dirname, 'resources', 'images', 'optimize.svg')
    modifier_icon_dir =       os.path.join(dirname, 'resources', 'images', 'outcomeModifier.svg')
    export_icon_dir =         os.path.join(dirname, 'resources', 'images', 'exportArray.svg')
    load_icon_dir =           os.path.join(dirname, 'resources', 'images', 'load.svg')
    save_icon_dir =           os.path.join(dirname, 'resources', 'images', 'save.svg')
    defaults_icon_dir =       os.path.join(dirname, 'resources', 'images', 'restore.svg')
    help_icon_dir =           os.path.join(dirname, 'resources', 'images', 'help.svg')
    about_icon_dir =          os.path.join(dirname, 'resources', 'images', 'info.svg')
    run_icon_dir =            os.path.join(dirname, 'resources', 'images', 'run.svg')

    pcoll.load("rapidPipeline", rapid_pipeline_icon_dir, 'IMAGE')
    pcoll.load("edit", edit_icon_dir, 'IMAGE')
    pcoll.load("import", import_icon_dir, 'IMAGE')
    pcoll.load("sceneGraphFlattening", scene_graph_icon_dir, 'IMAGE')
    pcoll.load("meshCulling", mesh_culling_icon_dir, 'IMAGE')
    pcoll.load("optimize", optimize_icon_dir, 'IMAGE')
    pcoll.load("modifier", modifier_icon_dir, 'IMAGE')
    pcoll.load("export", export_icon_dir, 'IMAGE')

    pcoll.load("load", load_icon_dir, 'IMAGE')
    pcoll.load("save", save_icon_dir, 'IMAGE')
    pcoll.load("defaults", defaults_icon_dir, 'IMAGE')
    pcoll.load("help", help_icon_dir, 'IMAGE')
    pcoll.load("about", about_icon_dir, 'IMAGE')
    pcoll.load("run", run_icon_dir, 'IMAGE')

    preview_collections["main"] = pcoll

    pcoll = preview_collections["main"]
    bpy.types.Scene.icon_import = pcoll["import"]
    bpy.types.Scene.icon_3dEdit = pcoll["edit"]
    bpy.types.Scene.icon_sceneGraphFlattening = pcoll["sceneGraphFlattening"]
    bpy.types.Scene.icon_meshCulling = pcoll["meshCulling"]
    bpy.types.Scene.icon_optimize = pcoll["optimize"]
    bpy.types.Scene.icon_outcomeModifier = pcoll["modifier"]
    bpy.types.Scene.icon_export = pcoll["export"]


def register():
    reg()

    # if the temp license file is in the folder, remove it before continuing
    if os.path.isfile(ProcessorLicense.TEMP_LICENSE_FILE):
        os.remove(ProcessorLicense.TEMP_LICENSE_FILE)

    ProcessorPlugin.loadSchema()
    schema = ProcessorPlugin.getSolvedSchema()

    # load_post is only called on blender startup
    # timers.register is used in case the plugin is installed without a blender restart
    # we can not rely only on timers.register since it doesnt work on loading blender scenes
    global register_worked
    register_worked = False
    def wait_for_late_register(dummy = None):
        global register_worked
        if not register_worked:
            register_worked = True
            setup_properties(schema, path=[])

    bpy.app.timers.register(wait_for_late_register, first_interval=0.1)
    bpy.app.handlers.load_post.append(wait_for_late_register)  #wait for context to be fully loaded

    setup_icons()

    #setup tab elements
    tab_elements = []
    override_rules = ProcessorPlugin.ui_rules.get("overrideUIElement", {})
    for element in override_rules.get("SimpleContainer", []):
        tab_elements.append((element, element, "description"))

    bpy.types.Scene.tabelements = bpy.props.EnumProperty(items=tab_elements)

    bpy.types.Scene.aboutdialog = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.licenses = bpy.props.StringProperty()

    #setup level
    level = [(("basic",)*3), (("advanced",)*3), (("expert",)*3)]
    bpy.types.Scene.level = bpy.props.EnumProperty(items=level)


    bpy.types.Scene.boolean_default = bpy.props.PointerProperty(type=BooleanPropertyGroup)
    bpy.types.Scene.integer_default = bpy.props.PointerProperty(type=IntegerPropertyGroup)
    bpy.types.Scene.float_default = bpy.props.PointerProperty(type=FloatPropertyGroup)
    bpy.types.Scene.enum_default = bpy.props.EnumProperty(
        items=[("default_enum", "default_name", "default_description")])
    bpy.types.Scene.color_default = bpy.props.FloatVectorProperty(
        default = (1.0, 1.0, 1.0), min=0.0, max=1.0, subtype='COLOR')

    bpy.types.Scene.rpde_output = ""
    bpy.types.Scene.rpde_percentage = bpy.props.IntProperty(default=0, min=0, max=100, step=1, subtype='PERCENTAGE')
    bpy.types.Scene.has_license = ProcessorLicense.performLicenseCheck(None)
    bpy.types.Scene.use_token_future_sessions = bpy.props.BoolProperty(
        default=False, description="If checked, the current API Token will be saved to disk for future usage.")
    bpy.types.Scene.t_and_c_agreed = bpy.props.BoolProperty(
        default=False, description="If checked, you agree to the Terms and Conditions of RapidPipeline usage.")
    bpy.types.Scene.api_token = bpy.props.StringProperty(default="")
    bpy.types.Scene.override_token = False
    bpy.types.Scene.rpde_running = False
    bpy.types.Scene.rpde_error = False
    bpy.types.Scene.rpde_cancel = False
    bpy.types.Scene.rpde_UI_error = False

    # load_post is only called on blender startup
    # timers.register is used in case the plugin is installed without a blender restart
    # we can not rely only on timers.register since it doesnt work on loading blender scenes
    global late_registered
    late_registered = False
    def wait_for_late_register(dummy = None):
        global late_registered
        if not late_registered:
            late_registered = True
            late_reg()

    bpy.app.timers.register(wait_for_late_register, first_interval=0.2)
    bpy.app.handlers.load_post.append(wait_for_late_register)  #wait for context to be fully loaded

    if 'darwin' == platform:
        print("Mac detected")
        removeQuarantineFlagOnMac()
    elif 'linux' == platform:
        setupLinux()

def removeQuarantineFlagOnMac():
    os.chdir(os.path.dirname(ProcessorPlugin.getRPDEPath()))
    command_arguments = ['xattr', '-d', 'com.apple.quarantine', "./rpde"]
    command_arguments2 = ['chmod', '+x', "./rpde"]
    print("Removing quarantine flag on Mac...")
    print(command_arguments)    

    result2 = subprocess.run(
            command_arguments2)

    result = subprocess.run(
            command_arguments)

    print(f"Subprocess result: {result}")

def setupLinux():
    os.chdir(os.path.dirname(ProcessorPlugin.getRPDEPath()))
    command_arguments = ['chmod', '+x', "./rpde"]
    result = subprocess.run(
            command_arguments)

    print(f"Subprocess result: {result}")

def unregister():
    unreg()
    # if the temp license file is in the folder, remove it before continuing
    if os.path.isfile(ProcessorLicense.TEMP_LICENSE_FILE):
        os.remove(ProcessorLicense.TEMP_LICENSE_FILE)
    late_unreg()
