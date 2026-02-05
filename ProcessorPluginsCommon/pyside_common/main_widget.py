import shutil
from abc import abstractmethod
import os
from sys import platform
import subprocess
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    PYSIDE_VERSION = 2

if PYSIDE_VERSION == 6:
    from PySide6.QtGui import QAction as QAction
else:
    from PySide2.QtWidgets import QAction as QAction

import webbrowser
from typing import Callable, List, Tuple, Dict
from pathlib import Path

from pyside_common import utils as pyside_utils
from pyside_common.progress import ProcessProgressLog
from pyside_common.processor import Processor
from actions_widget import ActionsContainer
from magic_actions import utils as action_utils
from import_dialog import ImportDialog, ExportDialog
from license_dialog import LicenseDialog
from magic_actions.licensing import ProcessorLicense
from about_dialog import AboutDialog
from common.main_widget_common import MainWidgetBase

if platform == "darwin":
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

COMMONS_ROOT = os.path.dirname(os.path.dirname(__file__))

# type defs
ACTION_LIST = List[action_utils.MagicAction]

class MainWidget(MainWidgetBase, QtWidgets.QWidget):
    # for MainWidgetBase
    ProcessorLicense = ProcessorLicense
    def __init__(self, tool: str, plugin_root: str, version:str = "0.0.0"):
        """
        Initializes the main plugin widget with the 3D DCC tool name, plugin root directory for source files etc., and plugin version.
        """
        super().__init__(tool=tool, plugin_root=plugin_root, version=version)
        self.__show_preview = True
        self.__skip_temp_file_dialog = False

        # NOTE: these flags will only take effect once
        self.__first_show = True
        self.__first_run  = True

        # setup main widget layout
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(16, 8, 16, 16)
        self.main_layout.setAlignment(QtGui.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)

        # about dialog is created only once
        self.about_dialog = AboutDialog(self, self.tool, self.version, self.plugin_root)

        self.main_layout.addSpacing(12)

        # logo and tool name
        self.main_menu = pyside_utils.MainMenu(self.action_versions)
        self.main_layout.addWidget(self.main_menu, alignment=QtCore.Qt.AlignTop)

        self.main_menu.key_button.clicked.connect(self.overrideLicense)
        self.main_menu.settings_button.clicked.connect(self.onSettingsPressed)
        self.main_menu.help_button.clicked.connect(self.onHelpPressed)
        self.main_menu.version_dropdown.currentTextChanged.connect(self.onVersionSelected)

        # create action container before help menu
        buttons_column_count = self.getButtonsColumnCount()
        self.actions_container = ActionsContainer(use_scrollable=False, column_count=buttons_column_count)

        # Create help menu and assign it to button
        self.settings_menu, self.settings_actions = self.createSettingsMenu()
        self.main_menu.settings_button.setMenu(self.settings_menu)
        self.help_menu, self.help_actions = self.createHelpMenu()
        self.main_menu.help_button.setMenu(self.help_menu)

        self.main_layout.addSpacing(12)

        # import/export widget
        self.setupProcessingMenu()

        self.main_layout.addSpacing(12)

        self.main_layout.addWidget(self.actions_container)
        # self.actions_container.setCustomSizePolicy()
        self.actions_container.populateContainer(self.schema, self.process_actions)

        self.main_layout.addSpacing(7)

        # create divider line
        self.divider_line = QtWidgets.QFrame()
        self.divider_line.setFrameShape(QtWidgets.QFrame.HLine)
        self.divider_line.setFrameShadow(QtWidgets.QFrame.Raised)
        self.main_layout.addWidget(self.divider_line)
        self.main_layout.addSpacing(5)

        self.progress_widget = ProcessProgressLog()
        self.main_layout.addWidget(self.progress_widget, alignment=QtCore.Qt.AlignTop)

        self.main_layout.addSpacing(12)
        self.main_layout.addStretch()

        self.footer_widget = pyside_utils.Footer()
        self.main_layout.addWidget(self.footer_widget, alignment=QtCore.Qt.AlignBottom)
        self.footer_widget.run_button.clicked.connect(self.runButtonPressed)

        self.process: Processor = None
        self.__is_running = False
        self.__is_import_run = False

    def getButtonsColumnCount(self):
        return 2

    def setupProcessingMenu(self):
        self.processing_menu = pyside_utils.ProcessingMenu(self._is_cad_version)
        self.main_layout.addWidget(self.processing_menu, alignment=QtCore.Qt.AlignTop)
        self.processing_menu.import_button.clicked.connect(self.importPressed)
        self.processing_menu.export_button.clicked.connect(self.exportPressed)

    def showEvent(self, event: QtGui.QShowEvent):
        """
        Reacts to a QShowEvent, providing a chance to execute custom code on dialog launch.
        """
        self.doLicenseCheck()
        if self.__first_show and not self.actions_container.isEmpty():
            self.actions_container.actionChanged(0)
            self.__first_show = False

    #############################################
    # ======== UI Functions & Callbacks =========
    #############################################

    def importDialogWidth(self) -> int:
        return 550

    def setActionsDisabledState(self, flag:bool):
        """
        Controls the disabled flag of the "magic actions" container.
        """
        self.actions_container.setDisabled(flag)


    def warnAboutScenePath(self) -> bool:
        """
        Issues a warning about lack of a "scene path" (relevant for DCCs where imported resources are referenced live from the tool).
        """
        # print warning to log view
        def warning_skip():
            self.progress_widget.appendWarning("Canceling processing, saving of temp files to the plugin folder is disabled.")
            self.progress_widget.appendWarning("Please, save your scene or change your settings in the Settings menu.")

        if self.settings_actions["skip"].isChecked():
            if not self.__skip_temp_file_dialog:
                warning_skip()
                return False
            return True

        if self.scenePath != "":
            return True

        warning_text  = "There is no scene folder to store the optimized result in as the current scene has not yet been saved. "
        warning_text += "If you proceed, optimized results will be stored in the folder the plugin was installed to. Do you want to proceed?"

        checkbox = QtWidgets.QCheckBox("Don't ask again.")
        checkbox.toggled.connect(self.settings_actions["skip"].setChecked)
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle("Warning")
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg_box.setText(warning_text)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
        msg_box.setCheckBox(checkbox)
        clicked_button = msg_box.exec()

        # if checkbox is true, set flag to true
        if checkbox.isChecked():
            self.settings_actions["skip"].setDisabled(False)
            self.settings_actions["skip"].setChecked(True)

        if clicked_button == QtWidgets.QMessageBox.Yes:
            if checkbox.isChecked():
                self.__skip_temp_file_dialog = True
            return True
        else:
            if checkbox.isChecked():
                self.__skip_temp_file_dialog = False
                warning_skip()
            else:
                self.progress_widget.appendWarning("The processing operation was cancelled.")
            return False

    def selectImportFile(self):
        """
        Selects a file to be imported, using a file selection dialog.
        """
        dialog_title = "Import 3D or CAD file" if self._is_cad_version else "Import 3D File"
        dialog_filter = pyside_utils.getSupportedInputFiles(self._is_cad_version)
        self.dialog_file = QtWidgets.QFileDialog.getOpenFileName(self, dialog_title, self.getFolderForFileDialog(), dialog_filter)[0]
        if self.dialog_file != "":
            self._last_valid_file = self.dialog_file

    def importPressed(self):
        """
        Default import button behavior, triggering a file import dialog.
        """
        self.processing_menu.import_button.setDown(False)
        self.scenePath = self.getScenePath()
        if not self.warnAboutScenePath():
            return

        self.__is_import_run = True
        self.setActionsDisabledState(True)

        self.selectImportFile()

        # if no valid file was selected, cancel
        if not self.dialog_file or not os.path.isfile(self.dialog_file):
            self.progress_widget.appendWarning("No valid file selected, cancelling import operation.")
            self.postProcess()
            return

        #  open the separate import dialog, so the user can select an import action
        import_dialog = ImportDialog(self, self.schema, self.import_actions, False, self.importDialogWidth())
        clicked_btn = import_dialog.exec()
        if clicked_btn < 0:
            self.progress_widget.appendWarning("Import operation cancelled.")
            self.postProcess()
            return
        elif clicked_btn > 0:
            # get setting dict from input and UI, and save it out
            self.progress_widget.appendLog("Using Import Action config...")
            input_config = import_dialog.actions_container.getSettingsFromCurrentAction()
            action_utils.overrideExports(input_config, self.getOptimizedFormat())
            self.overrideExportConfigForRun(input_config)
        else:
            if self._is_cad_version:
                self.progress_widget.appendLog("Importing 3D or CAD file with default config...")
            else:
                self.progress_widget.appendLog("Importing 3D file with default config...")
            input_config = action_utils.getDefaultConversionConfig("scene_file", self.getOptimizedFormat())
        print(input_config)
        action_utils.saveJSON(input_config, self.getConfigFilePath())

        import_dialog = None

        optimized_folder = self.getOptimizedFolder()
        optimized_file = self.getOptimizedFilePath(optimized_folder)

        # callback definitions
        def on_success():
            self.processSuccess(optimized_file)

        def on_failure():
            self.processFailure(optimized_file)

        def on_cancel():
            self.processCanceled(optimized_file)

        # run processor with saved out settings file
        self.runProcessor(self.dialog_file, optimized_folder, on_success, on_failure, on_cancel)

    def getFolderForFileDialog(self) -> str:
        """
        Try to get the last folder the user interacted with. If none is available,
        try to get the scene folder. If that's also not available, return the Desktop folder,
        if available, on windows. In all other cases, return the user's home folder.
        """
        if self._last_valid_file and os.path.isdir(os.path.dirname(self._last_valid_file)):
            return os.path.dirname(self.dialog_file)
        elif self.scenePath and os.path.isdir(os.path.dirname(self.scenePath)):
            return os.path.dirname(self.scenePath)
        elif os.name == "nt":
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            if os.path.isdir(desktop):
                return desktop
            else:
                return os.environ['USERPROFILE']
        else:
            return str(os.path.expanduser("~"))

    def exportPressed(self):
        """
        Default export button behavior, triggering a file export dialog.
        """
        self.processing_menu.export_button.setDown(False)
        self.__is_import_run = False
        if not self.canExport():
            return
        self.setActionsDisabledState(True)
        dialog_title = "Export as 3D file"
        dialog_filter = pyside_utils.getSupportedOutputFiles()
        self.dialog_file = QtWidgets.QFileDialog.getSaveFileName(self, dialog_title, self.getFolderForFileDialog(), dialog_filter)[0]

        # if no valid file was select, cancel
        if not self.dialog_file:
            self.progress_widget.appendWarning("No valid file selected, cancelling export operation.")
            self.postProcess()
            return
        self._last_valid_file = self.dialog_file
        dialog_path = Path(self.dialog_file)
        export_name = dialog_path.stem

        # export unoptimized file
        unoptimized_file = self.getUnOptimizedFilePath()
        unoptimized_file = str(Path(unoptimized_file).with_stem(export_name))
        if os.path.isfile(unoptimized_file):
            os.remove(unoptimized_file)

        # get config to convert file to certain export format
        export_extension = dialog_path.suffix[1:]

        #  open the separate import dialog, so the user can select an import action
        export_dialog = ExportDialog(self, self.schema, self.export_actions, export_extension, False, self.importDialogWidth())
        clicked_btn = export_dialog.exec()
        if clicked_btn < 0:
            self.progress_widget.appendWarning("Export operation cancelled.")
            self.postProcess()
            return
        elif clicked_btn > 0:
            # get setting dict from input and UI, and save it out
            self.progress_widget.appendLog("Using Export Action config...")
            export_config = export_dialog.actions_container.getSettingsFromCurrentAction()
        else:
            self.progress_widget.appendLog("Export 3D file with default config...")
            export_config = action_utils.getDefaultConversionConfig(export_name, self.getOptimizedFormat())
            action_utils.overrideExports(export_config, export_extension)

        # we already set the proper name to the rpde input file (i.e. unoptimized file)
        action_utils.removeSettingFromPath(export_config, "export.fileName", "export.fileName")
        print(export_config)
        action_utils.saveJSON(export_config, self.getConfigFilePath())

        # effectively exports the file: has to be after export dialog
        self.exportModel(unoptimized_file)
        if not os.path.isfile(unoptimized_file):
            error_msg = f"ERROR: The file {unoptimized_file} can't be found. Likely an error on {self.tool} export."
            self.progress_widget.appendError(error_msg)
            self.postProcess()
            return

        # get folder for optimized file
        optimized_folder = self.getOptimizedFolder()
        optimized_file = self.getOptimizedFilePath(optimized_folder, export_extension)

        def on_success():
            # RPDE results are placed in a certain subfolder, so we copy it over to the location
            # move file and textures to specific output location
            shutil.copytree(os.path.dirname(optimized_file), os.path.dirname(self.dialog_file), dirs_exist_ok=True)
            self.progress_widget.appendLog("Finished executing the export operation.")
            self.postProcess()

        def on_failure():
            self.progress_widget.appendError("The export operation failed.")
            self.postProcess()

        def on_cancel():
            self.progress_widget.appendWarning("The export operation was cancelled.")
            self.postProcess()

        # run processor with saved out settings file
        self.runProcessor(unoptimized_file, optimized_folder, on_success, on_failure, on_cancel)


    def runButtonPressed(self):
        """
        Triggers, if all requirements are met, a processing run OR cancelation of it.
        """
        self.footer_widget.run_button.setDown(False)

        self.__is_import_run = False
        if not self.canExport():
            return

        self.scenePath = self.getScenePath()
        if not self.warnAboutScenePath():
            return

        self.setActionsDisabledState(True)

        # if no process is running, start one
        # otherwise, cancel it
        if not self.__is_running:
            self.onRun()
        else:
            self.onCancel()


    def onCancel(self):
        """
        Cancels a processing run.
        """
        self.process.cancelProcess()


    def preRunExportPass(self, unoptimized_file):
        """
        Callback to execute an export step from the DCC before a processing run,
        if applicable. For some workflows, this might not be needed.
        """
        if os.path.isfile(unoptimized_file):
            os.remove(unoptimized_file)
        self.exportModel(unoptimized_file)


    def onRun(self):
        """
        Callback executed on triggering of a 3D processing run, performing an I/O loop through the RapidPipeline 3D processing engine.
        """
        unoptimized_file = self.getUnOptimizedFilePath()

        # export unoptimized file for processing
        self.preRunExportPass(unoptimized_file)

        if not os.path.isfile(unoptimized_file):
            error_msg = f"ERROR: The file {unoptimized_file} can't be found. Likely an error on {self.tool} export."
            self.progress_widget.appendError(error_msg)
            self.postProcess()
            return

        # get setting dict from input and UI, and save it out
        input_config = self.actions_container.getSettingsFromCurrentAction()
        action_utils.overrideExports(input_config, self.getOptimizedFormat())
        self.overrideExportConfigForRun(input_config)

        action_utils.saveJSON(input_config, self.getConfigFilePath())

        optimized_folder = self.getOptimizedFolder()
        optimized_file = self.getOptimizedFilePath(optimized_folder)

        # callback definitions
        def on_success():
            self.processSuccess(optimized_file)

        def on_failure():
            self.processFailure(optimized_file)

        def on_cancel():
            self.processCanceled(optimized_file)

        # run processor with saved out settings file
        self.runProcessor(unoptimized_file, optimized_folder, on_success, on_failure, on_cancel)


    def onSavePreset(self):
        """
        Saves out a RapidPipeline 3D processor engine preset JSON file, using the latest settings used.
        """
        self.setActionsDisabledState(True)
        dialog_title = "Save RapidPipeline Preset File"
        dialog_filter = "json Files (*.json)"
        self.dialog_file = QtWidgets.QFileDialog.getSaveFileName(self, dialog_title, self.getFolderForFileDialog(), dialog_filter)[0]

        # if the user canceled, return
        if not self.dialog_file:
            self.progress_widget.appendWarning("Unable to save RapidPipeline preset, operation cancelled.")
            self.setActionsDisabledState(False)
            return

        self._last_valid_file = self.dialog_file

        # get setting dict from input and UI, and save it out
        input_config = self.actions_container.getSettingsFromCurrentAction()
        action_utils.overrideExports(input_config, self.getOptimizedFormat())

        action_utils.saveJSON(input_config, self.dialog_file)
        self.progress_widget.appendLog(f"RapidPipeline preset file saved successfully at: {self.dialog_file}")

        self.setActionsDisabledState(False)


    #############################################
    # ============ RPDE Subprocess ==============
    #############################################

    def runProcessor(
            self,
            input_file: str,
            output_folder: str,
            success_callback:Callable = None,
            failure_callback:Callable = None,
            cancel_callback:Callable = None,
        ):
        """
        Runs the RapidPipeline 3D processor engine (RPDE) on a specific
        input 3D file. Note that this can either be the file exported
        from the DCC for optimization, or e.g. a CAD or 3D file that
        the user selected for import. At this point, the config file
        (JSON preset) should already exist on disk.
        """
        if not self.doLicenseCheck():
            return

        # show progress bar
        self.progress_widget.progress_bar.setHidden(False)

        rpde_path = os.path.join(self.plugin_root, "rpde") #incomplete at this point, OS-dependent addition see below

        if 'darwin' == platform:
            if self.__first_run:
                print("Detected MacOS platform")
                self.removeQuarantineFlagOnMac(rpde_path)
                self.setupUnixExecutable(rpde_path)
                self.__first_run = False
            rpde_path = os.path.join(rpde_path, "rpde")
        elif 'linux' == platform:
            if self.__first_run:
                print("Detected Linux platform")
                self.setupUnixExecutable(rpde_path)
                self.__first_run = False
            rpde_path = os.path.join(rpde_path, "rpde")
        else:
            rpde_path = os.path.join(rpde_path, "rpde.exe")

        config_path = self.getConfigFilePath()

        # configure and start process
        self.process = Processor(rpde_path, self.progress_widget, success_callback, failure_callback, cancel_callback)
        cmd_args = ["--read_config", str(Path(config_path)), "-i", str(Path(input_file)), "-o", str(Path(output_folder)), "--run"]
        if self.signatureToolInfo:
            self.process.signatureToolInfo = self.signatureToolInfo
        self.process.runCommand(cmd_args)

        # toggle running state and button state
        self.__is_running = True
        self.footer_widget.setRunButton(False)


    #############################################
    # =========== Process Callbacks =============
    #############################################

    def postProcess(self):
        """
        General post process callback, used in success, failure and cancel scenarios.
        """
        self.progress_widget.progress_bar.setHidden(True)
        self.__is_running = False
        self.footer_widget.run_button.setDown(False)
        self.footer_widget.setRunButton(True)
        self.setActionsDisabledState(False)


    def processSuccess(self, output_file: str):
        """
        Callback for successful process executions.
        """
        # move temporary files
        output_path = Path(output_file)
        shutil.copytree(output_path.parent, output_path.parent.parent, dirs_exist_ok=True)
        shutil.rmtree(output_path.parent)

        # new file path
        file_to_import = str(Path(output_path.parent.parent, output_path.name))

        self.importModel(file_to_import)
        self.postProcess()

    def processFailure(self, output_file: str):
        """
        Callback for failed process executions.
        """
        # delete temporary files if any
        output_path = Path(output_file)
        if output_path.parent.is_dir():
            shutil.rmtree(output_path.parent)

        self.postProcess()

    def processCanceled(self, output_file: str):
        """
        Callback when user cancels execution.
        """
        # delete temporary files if any
        output_path = Path(output_file)
        if output_path.parent.is_dir():
            shutil.rmtree(output_path.parent)

        self.postProcess()

    #############################################
    # =================== I/O ===================
    #############################################

    @abstractmethod
    def exportModel(self, file_path: str) -> bool:
        """
        Abstract method to be implemented by the DCC specific code, exporting a 3D file to the given file path.
        """
        pass


    @abstractmethod
    def importModel(self, file_path: str) -> bool:
        """
        Abstract method to be implemented by the DCC specific code, importing a 3D file from the given file path.
        """
        pass


    def overrideExportConfigForRun(self, config):
        """
        Provides an option to temporarily override the DCC's export config for a 3D processing run (e.g., for specific I/O cases).
        """
        pass


    def getScenePath(self) -> str:
        """
        Provides an option to provide a customized scene path (for DCCs that make use of a live scene concept).
        """
        return ""


    def canExport(self) -> bool:
        """
        Returns true if export of a scene is possible.
        Implementing DCCs may override this method to indicate situations where export isn't possible,
        such as when the current scene is empty.
        """
        return True


    def hideOldNodes(self) -> bool:
        """
        Returns true if the implementing DCC is expected to hide old nodes upon
        importing an optimized file.

        By default, we will hide old nodes when the run is not importing.
        When importing, new nodes are added but nothing is hidden away.
        Implementing DCCs may override this method when sensible for their workflows.
        """
        return not self.__is_import_run


    #############################################
    # ============== Other Features =============
    #############################################

    def openRPDDocs(self):
        """
        Opens the documentation in the user's browser
        """
        self.progress_widget.appendLog("Opening RapidPipeline docs in your default browser...")
        webbrowser.open(r"https://docs.rapidpipeline.com/")


    def overrideLicense(self):
        """
        Opens the licensing dialog, where the user can specify their licensing auth token.
        """
        self.main_menu.key_button.setDown(False)
        LicenseDialog(self).exec()

        self.main_menu.key_button.clearFocus()

        if ProcessorLicense.hasLicense():
            self.setActionsDisabledState(False)

    def doLicenseCheck(self) -> bool:
        """
        Performs a license check - if no license present, the user is presented with a license dialog.
        """
        if ProcessorLicense.hasLicense():
            self.setActionsDisabledState(False)
            return True
        # if user has no license, provide license dialog
        rpd_str = f"the RapidPipeline for {self.tool} plugin"
        warning_msg = f"No license was found when initiating {rpd_str}."
        self.progress_widget.appendWarning(warning_msg)
        LicenseDialog(self).exec()
        # check again after dialog finished
        if not ProcessorLicense.hasLicense():
            error_msg = f"Unable to continue, license token for {rpd_str} could not be found."
            self.progress_widget.appendError(error_msg)
            self.setActionsDisabledState(True)
            return False
        else:
            self.setActionsDisabledState(False)
            return True

    def onVersionSelected(self):
        """
        Callback on version selection inside the UI.
        """
        version_str = self.main_menu.version_dropdown.currentText()
        if version_str != self.current_version:
            self.current_version = version_str
            self.import_actions, self.process_actions, self.export_actions = self.getActionsByVersion(version_str)
            self.actions_container.populateContainer(self.schema, self.process_actions)
            self.actions_container.setShowPreview(self.__show_preview)

    def onHelpPressed(self):
        """
        Callback on help button selection inside the UI.
        """
        self.main_menu.help_button.showMenu()

    def onSettingsPressed(self):
        """
        Callback on help button selection inside the UI.
        """
        self.main_menu.settings_button.showMenu()

    def onFeedbackPressed(self):
        """
        Callback to open Feedback in the user's default browser.
        """
        feedback_url = "https://webforms.pipedrive.com/f/6q9NnMBNx3wtPNn2wJ49483fTonnF3e7jPK61JL64YqVui7VCxNV15tW9aznGyL3UL"
        self.progress_widget.appendLog("Opening RapidPipeline Plugin Feedback in your default browser...")
        webbrowser.open(feedback_url)

    def onTogglePreview(self, checked:bool):
        self.__show_preview = checked
        self.actions_container.setShowPreview(checked)

    def onToggleSkipAction(self, checked:bool):
        """
        We never want to let the user re-check the skip checkbox after they unchecked it.
        After it's been unchecked, we disable the checkbox so that it can only
        be reenabled and re-checked by the dialog interaction.
        """
        if not checked:
            self.settings_actions["skip"].setDisabled(True)
            self.__skip_temp_file_dialog = False

    def createSettingsMenu(self) -> Tuple[QtWidgets.QMenu, Dict[str, QAction]]:
        """
        Creates the help menu that pops up once the help button is used.
        """
        settings_menu = QtWidgets.QMenu()
        settings_actions = {}

        preview_action = QAction("Show Actions Preview", settings_menu)
        preview_action.setToolTip("Shows or hides previews/gifs of actions.")
        preview_action.toggled.connect(self.onTogglePreview)
        preview_action.setCheckable(True)
        preview_action.setChecked(self.__show_preview)
        settings_actions["preview"] = preview_action
        settings_menu.addAction(preview_action)

        settings_menu.addSection("Temporary File Settings")

        skip_action = QAction("Skip Confirmation Dialog", settings_menu)
        skip_action.setToolTip("Skips confirmation dialog asking about temporary files. This can only be enabled through the confirmation dialog.")
        skip_action.setCheckable(True)
        skip_action.toggled.connect(self.onToggleSkipAction)
        skip_action.setChecked(self.__skip_temp_file_dialog)
        skip_action.setDisabled(not self.__skip_temp_file_dialog)
        settings_actions["skip"] = skip_action
        settings_menu.addAction(skip_action)

        settings_menu.aboutToHide.connect(self.main_menu.settings_button.clearFocus)

        return settings_menu, settings_actions

    def createHelpMenu(self) -> Tuple[QtWidgets.QMenu, Dict[str, QAction]]:
        """
        Creates the help menu that pops up once the help button is used.
        """
        help_menu = QtWidgets.QMenu()
        help_actions = {}

        docs_action = QAction(pyside_utils.getIcon("doc"), "Plugin Documentation", help_menu)
        docs_action.setToolTip("Opens the RapidPipeline documentation in your webbrowser.")
        docs_action.triggered.connect(self.openRPDDocs)
        help_actions["docs"] = docs_action
        help_menu.addAction(docs_action)

        feedback_action = QAction(pyside_utils.getIcon("feedback"), "Feedback", help_menu)
        feedback_action.setToolTip("Provide feedback about your plugin usage.")
        feedback_action.triggered.connect(self.onFeedbackPressed)
        help_actions["feedback"] = feedback_action
        help_menu.addAction(feedback_action)

        support_action = QAction(pyside_utils.getIcon("support"), "Contact Support", help_menu)
        support_action.setToolTip("Contact support about any issues you might have with the plugin.")
        support_action.triggered.connect(self.onSupportPressed)
        help_actions["support"] = support_action
        help_menu.addAction(support_action)

        about_action = QAction(pyside_utils.getIcon("info"), "About the Plugin", help_menu)
        about_action.setToolTip("About the Plugin and Open Source License Information.")
        about_action.triggered.connect(self.about_dialog.exec)
        help_actions["about"] = about_action
        help_menu.addAction(about_action)

        help_menu.aboutToHide.connect(self.main_menu.help_button.clearFocus)

        return help_menu, help_actions


    def onAboutClicked(self):
        """
        Shows the "About" dialog.
        """
        self.about_dialog.exec()


class ImporterMainWidget(MainWidget):
    def __init__(self, tool: str, plugin_root: str, version:str = "0.0.0"):
        super().__init__(tool=tool, plugin_root=plugin_root, version=version)
        # initially, all actions are disabled, but enabled after file selection
        #TODO: make it work
        self.setActionsDisabledState(True)
        self.footer_widget.run_button.setDisabled(True)


    def getButtonsColumnCount(self):
        return 1


    def setActionsDisabledState(self, flag:bool):
        # do really only enable action selection if a file has been selected
        if not flag and self.dialog_file == "":
            pass
        else:
            super().setActionsDisabledState(flag)


    def setupProcessingMenu(self):
        self.processing_menu = pyside_utils.ImporterProcessingMenu(self._is_cad_version)
        self.main_layout.addWidget(self.processing_menu, alignment=QtCore.Qt.AlignTop)
        self.processing_menu.import_button.clicked.connect(self.importPressed)


    def importPressed(self):
        # for the import variant, don't run the processing yet,
        # instead just select a file and show its path in the UI
        self.selectImportFile()
        # if user cancels, fall back to last valid file
        if self.dialog_file == "":
            self.dialog_file = self._last_valid_file
        disabled_state = (self.dialog_file == "")
        self.setActionsDisabledState(disabled_state)
        self.footer_widget.run_button.setDisabled(disabled_state)
        self.processing_menu.file_path_display.setText(self.dialog_file)


    def getUnOptimizedFilePath(self) -> str:
        return self.dialog_file


    def preRunExportPass(self, unoptimized_file):
        # here we'd have the option to export sth. for processing,
        # but in this case we assume an "import-only workflow",
        # therefore nothing needs to be exported
        # (the 3D processor directly operates on the selected input file)
        pass


    def getActionsByVersion(self, version:str) -> ACTION_LIST:
        """
        Returns, in order, lists of Import, Processing and Export actions.

        As this variant of the main dialog only cares about the Import actions,
        we return them in place of the Processing actions. They will then have
        effect into the main dialog. The other action lists will be empty.
        """
        import_actions, _, _ = super().getActionsByVersion(version)
        return [], import_actions, []
