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
import pathlib
import shutil
import traceback
from abc import abstractmethod
from sys import platform
from typing import Any

import bpy  # type: ignore

from .run_rpde import RunPipeline
from .ui_utils import deselect_all, fix_animation, select_children, set_object_mode

# defines user appdata folder for the plugin
base_dcc_data_folder = os.path.join(
    os.path.expanduser("~"), 'Documents') if 'darwin' in platform else os.getenv("LOCALAPPDATA")
os.environ["RPDP_PROCESSOR_DCC_DATA"] = os.path.join(base_dcc_data_folder, "RapidPipeline 3D Processor Plugins")

from .gui_commons import UserDialog
from .main import MainData
from .ProcessorPluginsCommon.magic_actions.utils import saveJSON


def get_export_settings(file_name:str = "") -> list[dict]:
    return [
            {
                "fileName": file_name,
                "textureMapFilePrefix": "",
                "discard": {
                    "emptyNodes": True
                },
                "format": {
                    "glb": {
                    "pbrMaterial": {
                        "textureFormat": {
                            "default": "png"
                            }
                        }
                    }
                }
            }
        ]

def get_viewlayer() -> Any:
    if "ViewLayer" in bpy.context.scene.view_layers:
        return bpy.context.scene.view_layers['ViewLayer']
    else:
        return bpy.context.scene.view_layers[0]

def node_in_collection(
        node:bpy.types.Node, collection:bpy.types.Collection, scene_collection:bpy.types.Collection = None):
    collection.objects.link(node)
    if scene_collection:
        scene_collection.objects.unlink(node)

def get_collections_in_scene() -> list:
    return [
        c.name for c in bpy.data.collections
        if bpy.context.scene.user_of_id(c)
    ]

def create_new_collection(collection_name:str, link_to_scene:bool = True) -> bpy.types.Collection:
    if collection_name not in get_collections_in_scene():
        collection = bpy.data.collections.new(collection_name)
        if link_to_scene:
            bpy.context.scene.collection.children.link(collection)
    else:
        collection = bpy.data.collections[collection_name]
    return collection

def link_collection(collection_outer:bpy.types.Collection, collection_inner:bpy.types.Collection):
    if collection_inner.name not in bpy.data.collections[collection_outer.name].children:
        bpy.data.collections[collection_outer.name].children.link(collection_inner)

def unlink_collection(collection_outer:bpy.types.Collection, collection_inner:bpy.types.Collection):
    if collection_inner.name in bpy.data.collections[collection_outer.name].children:
        bpy.data.collections[collection_outer.name].children.unlink(collection_inner)

# unhides the given collection and activates it in view Layer
# NOTE carefull, this also changes the selection in context.selected_objects
def unhide_collection(vlayer:Any, collection:bpy.types.Collection):
    collection_viewport = search_collection(
        vlayer.layer_collection, collection.name)
    collection_viewport.hide_viewport = False
    collection_viewport.exclude = False

# searches for a given name in a tree of collections
# see: https://blender.stackexchange.com/questions/202675/python-hide-collection-turn-off-the-eyeball-icon-of-collection-in-outliner
def search_collection(parent:bpy.types.Collection, name:str) -> bpy.types.Collection:
    if parent.name == name:
        return parent
    for c in parent.children:
        coll = search_collection(c, name)
        if coll:
            return coll
    return None

class RunOperator(bpy.types.Operator):
    bl_idname = "processor.run"
    bl_description = "Run RapidPipeline 3D Processor with the selected settings"
    bl_label = "run"
    bl_options = {'REGISTER', 'UNDO'}

    output_cmd: bpy.props.StringProperty(options={'HIDDEN'}) # type: ignore

    # define file paths
    main_data = MainData()
    extension = main_data.getOptimizedFormat()
    import_extension = main_data.getUnOptimizedFormat()
    output_folder: str = os.environ["RPDP_PROCESSOR_DCC_DATA"]
    output_filename = ""

    copied_nodes_global = []

    def execute(self, context:bpy.types.Context) -> set[str]:
        if context.scene.rpde_running:
            bpy.types.Scene.rpde_running = False
            if not context.scene.rpde_export:
                self.processFinished()
            else:
                self.processFinished(False)
                bpy.types.Scene.rpde_export = False
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
        from .draw_ui import root_element
        if not context.scene.rpde_export:
            current_settings = root_element.getSettings()
            current_settings["export"] = get_export_settings()

            # make sure to get the correct filename
            current_name = current_settings["export"][0].get("fileName", "")
            if not current_name:
                self.output_filename = "rpde_file"
            else:
                self.output_filename = current_name

        else:
            current_settings = root_element.getSettings()
            from .export_operator import global_export_path
            current_settings["export"]["fileName"] = pathlib.Path(global_export_path).stem

            #NOTE this is needed since export is a list in the schema
            export_settings = current_settings["export"]
            current_settings["export"] = []
            current_settings["export"].append(export_settings)

            self.output_filename = "rpde_file"

        json_path = self.getOutputJSonPath()
        if not saveJSON(current_settings, json_path):
            error_message = "Unable to save temporary settings file for RapidPipeline execution."
            UserDialog.critical(self, "Unable to Run RapidPipeline", error_message)
        print(f"Exported Settings: {json_path}")

        # set to object mode
        if bpy.context.view_layer.objects.active:
            set_object_mode()

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
        if not context.scene.rpde_export:
            RunPipeline.runPipeline(input_file, output_json_path, self.output_folder, copied_nodes)
            # make copied nodes not selectable
            try:
                for node in copied_nodes:
                    node.hide_select = True
            except Exception:  # noqa: S110
                pass

        else:
            from .export_operator import global_export_path
            RunPipeline.runPipeline(input_file, output_json_path, global_export_path, copied_nodes, True)


    def getOutputJSonPath(self) -> str:
        return os.path.join(self.getExecutionOutputFolder(), "rpdp_dcc_plugin_settings.json")

    def getExecutionInputFolder(self) -> str:
        return os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "0_glb")


    def getProcessorInputFile(self) -> str:
        return self.main_data.getOptimizedFilePath(
            self.output_folder, type_override=self.main_data.getOptimizedFormat(), file_name=self.output_filename)

    def getExecutionOutputFolder(self) -> str:
        return os.path.join(self.output_folder, f"0_{self.extension}")

    @abstractmethod
    def exportModel(self, file_path: str) -> list:
        """
        Exports model to be run by the RapidPipeline 3D Processor Engine
        """
        global copied_nodes_global
        export_path = os.path.dirname(file_path)
        os.makedirs(export_path, exist_ok=True)

        window = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window = window):
            export_selection = bpy.context.selected_objects

            # select children:
            select_children()

            if (len(export_selection) == 0):    # No objects selected -> select all objects
                view_layer = bpy.context.view_layer
                for o in list(bpy.data.objects):
                    if o.name in view_layer.objects and not o.hide_get():
                        o.select_set(True)
            export_selection = bpy.context.selected_objects

            if not bpy.context.scene.rpde_export:
                #NOTE We need to copy the object since we apply modifiers before the export step
                # duplicate nodes (duplicated nodes are now selected):
                bpy.ops.object.duplicate()
                copied_nodes = bpy.context.selected_objects
                deselect_all()

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

                deselect_all()
                for original_node in export_selection:
                    #dont hide camera and lights from the original scene
                    if original_node.type not in {'LIGHT', 'CAMERA'}:
                        original_node.hide_set(True)

                copied_nodes_global = copied_nodes.copy()
            else:
                copied_nodes = export_selection

            # select all copied nodes and export
            for object in copied_nodes:
                object.select_set(True)
            try:
                #NOTE we should not need to use "use_visible" here but it seems like blender is exporting more
                # than just selected nodes even though "use_selection" is true
                bpy.ops.export_scene.gltf(
                    export_format='GLB',
                    use_active_scene=True,
                    use_selection=True,
                    use_visible=True,
                    filepath=file_path)
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
            exported_objects_collections = {}    # dict(node_name : collection)
            selection = bpy.context.selected_objects
            deselect_all()

            try:
                for o in copied_nodes_global:
                    o.hide_select = False
                    exported_objects_collections[o.name] = (o.users_collection)    # retaining collections
                    o.select_set(True)
                bpy.ops.object.delete()

            except NameError:   # Case Import only case / no copied nodes defined
                pass
            except Exception:
                print("Warning: Could not find and delete copied nodes.")

            #get current scene
            scene = bpy.context.scene
            scene_collection = scene.collection
            objects_in_scene = bpy.data.objects

            # if all nodes of a collection are hidden, unhide nodes and hide collection instead
            used_collections = [x for xs in exported_objects_collections.values()
                                for x in xs if x is not scene_collection]

            vlayer = get_viewlayer()
            try:
                for collection in used_collections:
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


            # make sure scene collection is selected before import
            vlayer.active_layer_collection = vlayer.layer_collection

            # import glb
            try:
                bpy.ops.import_scene.gltf(filepath=file_path, merge_vertices=True)
            except Exception:
                print(f"Could not import glb file: {file_path}")
                print(traceback.format_exc())

            vlayer = get_viewlayer()

            fix_animation(bpy.context.selected_objects)

            # case for CAD import
            if not exported_objects_collections:
                cad_collection = create_new_collection("_import")
                unhide_collection(vlayer, cad_collection)

                from .run_rpde import cmd_command
                cad_file_name = cmd_command[4]
                cad_file_name = os.path.basename(cad_file_name)
                cad_file_collection = bpy.data.collections.new(cad_file_name)
                link_collection(cad_collection, cad_file_collection)

                # move imported cad model into cad_file_collection
                for node in bpy.context.selected_objects:
                    try:
                        scene_collection.objects.unlink(node)
                        cad_file_collection.objects.link(node)
                    except:  # noqa: S112, E722
                        continue
            else:
                processing_collection = create_new_collection("_processed")
                selection = bpy.context.selected_objects
                unhide_collection(vlayer, processing_collection)
                scene_graph_flatteing = False
                #case for scene flattening
                for node in selection:
                    if node.name not in exported_objects_collections.keys():
                        scene_graph_flatteing = True
                        break

                if scene_graph_flatteing:
                    flattening_collection = create_new_collection("_multi-selection-flattened", link_to_scene=False)
                    # if only one collection was used in flattening than we keep that structure
                    is_collections_flattened = len(set(exported_objects_collections.values())) > 1

                    if not is_collections_flattened:
                        collection_copy = self.moveCollectionIntoProcessed(
                            [x for x in exported_objects_collections.values()][0][0],
                            processing_collection, parent, True)
                        link_collection(collection_copy, flattening_collection)
                    else:
                        link_collection(processing_collection, flattening_collection)
                    unhide_collection(vlayer, flattening_collection)
                    for node in selection:      # move nodes into _multi-selection-flattened
                        node_in_collection(node, flattening_collection, scene_collection)

                else:
                    # Move nodes back into collection
                    collection_set = set([x for x in exported_objects_collections.values()])
                    for collections in collection_set:
                        try:
                            for collection in collections:
                                collection_copy = self.moveCollectionIntoProcessed(
                                    collection, processing_collection, parent, True)
                                for node_name in exported_objects_collections.keys():
                                    if (exported_objects_collections[node_name] == collections) and (
                                             node_name in objects_in_scene):
                                        node_in_collection(
                                            objects_in_scene[node_name], collection_copy, scene_collection)
                        except Exception:
                            traceback.print_stack()
                            traceback.print_exc()
                            print("Warning: original node names or collections could not be found.")
                            print("Placing node in 'Scene Collection' instead.")

    # Take any collection as an input, find all its parents and then move all the parents an itself to the
    # _processed collection. Returns a copy of the input collection in its correct hierachy
    def moveCollectionIntoProcessed(
            self,
            collection:bpy.types.Collection,
            processing_collection:bpy.types.Collection,
            parent: dict,
            initial_call:bool = False) -> bpy.types.Collection:

        #get current scene
        scene = bpy.context.scene
        scene_collection = scene.collection
        coll_processed_name = collection.name + "_processed"
        vlayer = get_viewlayer()

        if collection == scene_collection:
            unhide_collection(vlayer, processing_collection)
            return processing_collection
        if initial_call or not search_collection(vlayer.layer_collection, coll_processed_name):
            collection_copy = create_new_collection(coll_processed_name, False)
        else:
            unhide_collection(vlayer, bpy.data.collections[(coll_processed_name)])
            return bpy.data.collections[(coll_processed_name)] # collection was already moved

        # If collection on lowest level, move "<collection>_processed" into "_processed"
        if collection in list(scene_collection.children):
            link_collection(processing_collection, collection_copy)
        else:
            if parent[collection]:  # get all parent collections...
                parent_collection = self.moveCollectionIntoProcessed(
                    parent[collection], processing_collection, parent, False)
                try:
                    link_collection(parent_collection, collection_copy)
                except Exception:
                    print(f"{collection_copy.name} already in {parent_collection.name}")
        unhide_collection(vlayer, collection_copy)
        return collection_copy

    def processFinished(self, import_model:bool = True):
        from .draw_ui import root_element
        current_settings = root_element.getSettings()
        current_settings["export"] = get_export_settings()

        current_name = current_settings["export"][0].get("fileName", "")
        if not current_name:
            self.output_filename = "rpde_file"
        else:
            self.output_filename = current_name

        input_file = self.getInputFilePath()

        if import_model:
            self.importModel(input_file)

        else:
            from .export_operator import global_export_ext, global_export_path
            optimized_file = self.main_data.getOptimizedFilePath(global_export_path, global_export_ext.lower())
            # RPDE results are placed in a certain subfolder, so we copy it over to the location
            # move file and textures to specific output location
            shutil.copytree(os.path.dirname(optimized_file), os.path.dirname(global_export_path), dirs_exist_ok=True)
            shutil.rmtree(global_export_path)

        # removes temporary input tree
        shutil.rmtree(self.getExecutionInputFolder())

        # finished successfully, display a msg to the user
        confirm_label = "The RapidPipeline 3D Processor finished running successfully."
        UserDialog.okInfo(self, "Process Successful", confirm_label)
        self.report({'INFO'}, "Process Successful.")
        print("Process Successful")

    def getOutputFilePath(self) -> str:
        return os.path.join(self.getExecutionOutputFolder(), f"{self.output_filename}.{self.extension}")

    def getInputFilePath(self) -> str:
        return os.path.join(self.getExecutionInputFolder(), f"{self.output_filename}.{self.import_extension}")

def register():
    reg()

def unregister():
    unreg()

clss = (RunOperator,
        )

reg, unreg = bpy.utils.register_classes_factory(clss)
