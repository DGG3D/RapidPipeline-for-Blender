import os
import subprocess
import webbrowser
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from sys import platform
from typing import List, Tuple

from ..magic_actions import utils as action_utils

# type defs
ACTION_LIST = List[action_utils.MagicAction]

class MainWidgetBase():

    def __init__(self, tool: str, plugin_root: str, version:str = "0.0.0", **kwargs):
        super().__init__(**kwargs)

        self.scenePath = ""

        # load schema
        # TODO: we need to make sure that his is present in all plugins
        #       would it make sense to store it rather with the magic-actions (as they depend on it)?
        schema = action_utils.loadJSON(os.path.join(plugin_root, "schema.json"))
        schema_defs = action_utils.getSchemaDefs(schema)
        self.schema, _ = action_utils.solveSchemaRefs(schema, schema_defs)

        self.version = version
        self.tool = tool
        self.plugin_root = str(Path(plugin_root))
        self._is_cad_version : bool = False
        if 'darwin' == platform or 'linux' == platform:
            self._is_cad_version = os.path.isdir(os.path.join(self.plugin_root, "rpde", "lib", "hoops"))
        else:
            self._is_cad_version = os.path.isdir(os.path.join(self.plugin_root, "rpde", "hoops"))

        self.dialog_file = ""
        self._last_valid_file = "" # similar to dialog_file but will never be empty after first assignment

        # make sure to remove white spaces from the tool info
        self.signatureToolInfo = tool.replace(" ", "") + "_" + version

        # action variables
        self.import_actions = [] # for the currently selected version
        self.process_actions = [] # for the currently selected version
        self.export_actions = [] # for the currently selected version
        self.actions_by_version = {} # all versions and actions
        self.action_versions = []
        self.newest_version : str = None
        self.current_version : str = None
        self.importMagicActions()

    def importMagicActions(self):
        """
        Imports the RapidPipeline "magic actions", from a directory, for use via this UI.
        """
        # import magic actions
        self.actions_by_version = action_utils.import_magic_actions(self.plugin_root)
        if not self.actions_by_version:
            raise ValueError("Unable to find any valid magic action versions.")

        # get newest version identified
        version_keys = list(self.actions_by_version.keys())

        # "custom" allows the plugin user to provide their own magic actions
        if "Custom" in version_keys:
            version_keys.remove("Custom")
        version_keys.sort(key=lambda s: [int(u) for u in s.removeprefix("v").split('.')])
        version_keys.reverse()
        self.newest_version = next(iter(version_keys), None)

        # if we have a plugin settings file, get the setting value
        # otherwise, get the newest version
        plugin_settings = {}
        if plugin_settings and plugin_settings.get("actions_version", None):
            version = plugin_settings.get("actions_version", None)
        else:
            version = self.newest_version
        if version is None:
            raise ValueError("Unable to find any valid magic action versions.")

        # get actions with the current version
        self.current_version = version
        self.action_versions = version_keys + ["Custom"]
        self.import_actions, self.process_actions, self.export_actions = self.getActionsByVersion(version)

    #############################################
    # ======== Action/Settings Functions ========
    #############################################


    def getActionsByVersion(self, version:str) -> Tuple[ACTION_LIST, ACTION_LIST, ACTION_LIST]:
        """
        Gets the imported magic actions for the specific version, from the in-memory dictionary.

        Returns, in order, Import, Processing and Export actions.
        """
        # TODO: this part below will happen every time the user changes actions
        print(f"Loading actions with version: {version}")

        # get actions with desired version
        magic_actions = self.actions_by_version[version]

        if not magic_actions:
            raise ValueError(f"Unable to find any valid magic action with version {magic_actions}.")

        # NOTE: we don't use prio hints for export actions
        for variant in ["import", "processing"]:
            # filter out unwanted actions
            for action in list(magic_actions[variant]):
                if action.ui_prio_hints.get(self.tool, 0) == -1:
                    magic_actions[variant].remove(action)

            # sort actions based on prio hint for this tool
            magic_actions[variant].sort(key=lambda a: a.ui_prio_hints.get(self.tool, 0))

        # populate import and process actions
        import_actions  = magic_actions.get("import", [])
        process_actions = magic_actions.get("processing", [])
        export_actions = magic_actions.get("export", [])

        return import_actions, process_actions, export_actions

    def removeQuarantineFlagOnMac(self, rpde_dir):
        """
        Special treatment for MacOS, to "de-quarantine" executable
        """
        cwd = os.getcwd()
        os.chdir(os.path.dirname(rpde_dir))
        command_arguments = ['xattr', '-d', 'com.apple.quarantine', "./rpde"]
        command_arguments2 = ['chmod', '+x', "./rpde"]
        print("Removing quarantine flag on Mac ...")
        print(command_arguments)
        _      = subprocess.run(command_arguments2)
        result = subprocess.run(command_arguments)
        print(f"Setting up engine, result: {result}")
        os.chdir(cwd)


    #############################################
    # =========== File Path functions ===========
    #############################################

    @abstractmethod
    def getOptimizedFormat(self) -> str:
        """
        File format that should be the result of RPDE processing.
        This should be importable by the DCC.
        """
        pass


    def getOptimizedFolder(self) -> str:
        """
        Creates a (potentially timestamped) name for directory to save/load 3D processing results.
        """
        rootPath = self.scenePath
        if not rootPath or rootPath == "":
            rootPath = self.plugin_root

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if self.scenePath != "":
            base_folder = os.path.join(rootPath, "rpd_files")

            # we try to use a simpler indexed folder for files in the project folder
            i = 0
            while True:
                full_path = os.path.join(base_folder, f"process{str(i).zfill(3)}")
                if not os.path.isdir(full_path):
                    return full_path

                i += 1

                # if there's more than 999 processings, go back to timestamp
                if i > 999:
                    return os.path.join(base_folder, timestamp)
        else:
            return os.path.join(rootPath, "rpd_temp_files", timestamp)

    def getOptimizedFilePath(self, output_folder:str, type_override:str = "", file_name:str = "") -> str:
        """
        This function should somehow use self.getOptimizedFolder().
        E.g.: os.path.join(self.getOptimizedFolder(), "0_fbx", "scene_file.fbx")
        The format selection is left up to each DCC implementation.
        """
        if type_override:
            file_type = type_override
        else:
            file_type = self.getOptimizedFormat()
        if not file_name:
            file_name = "scene_file"
        return os.path.join(output_folder, f"0_{file_type}", f"{file_name}.{file_type}")


    @abstractmethod
    def getUnOptimizedFormat(self) -> str:
        """
        File format that should be the input of RPDE processing.
        This should be exportable by the DCC.
        """
        pass


    def getUnOptimizedFilePath(self) -> str:
        """
        Returns the path to the unprocessed 3D file to be processed.
        """
        file_format = self.getUnOptimizedFormat()
        return os.path.join(self.plugin_root, "rpd_temp_files", "input", f"input_file.{file_format}")


    def getConfigFilePath(self) -> str:
        """
        Returns the path to the temporary preset (RPDE config) to be used for the next processing run.
        """
        return os.path.join(self.plugin_root, "temp_config.json")

    def setupUnixExecutable(self, rpde_dir):
        """
        Special treatment for Linux/MacOS, to make sure run permissions are OK
        """
        cwd = os.getcwd()
        os.chdir(os.path.dirname(rpde_dir))
        command_arguments = ['chmod', '+x', "./rpde"]
        result = subprocess.run(command_arguments)
        print(f"Setting up engine, result: {result}")
        os.chdir(cwd)

    def onSupportPressed(self):
        """
        Callback to open Crisp support chat window, using user's e-mail if available.
        """
        support_url = "https://go.crisp.chat/chat/embed/?website_id=922e6bf3-2bf5-48d4-ba89-5bd58ef411e1"

        # get user's email address from token if available
        user_email = self.ProcessorLicense.getUserEmail()
        if user_email:
            user_email.replace("@", "%40")
            support_url += f"&user_email={user_email}"

        print(support_url)
        try:
            self.progress_widget.appendLog("Opening RapidPipeline Support Chat in your default browser...")
        except:
            pass
        webbrowser.open(support_url)
