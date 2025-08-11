import re
from typing import List, Callable
import pathlib
from PySide6 import QtCore

from progress import ProgressLog
from magic_actions.utils import getCommandSignature


class Processor:
    def __init__(
        self,
        rpde_path: str,
        progress_log_widget: ProgressLog = None,
        on_success: Callable = None,
        on_failure: Callable = None,
        on_cancel: Callable = None,
    ):
        self.rpde_path: str = str(pathlib.Path(rpde_path))
        self.progress_widget = progress_log_widget

        self.was_successful = False
        self.was_cancelled = False

        # optional callbacks - functions with no arguments
        self.on_success = on_success
        self.on_failure = on_failure
        self.on_cancel = on_cancel

        self.signatureToolInfo : str = ""

    def runCommand(self, cmd_args: List[str]):
        signature = getCommandSignature(self.rpde_path, cmd_args)
        cmdArgsArray = ["--signature", signature]
        if self.signatureToolInfo:
            cmdArgsArray.append(self.signatureToolInfo)
        cmd_args += cmdArgsArray

        print(f"Application: {self.rpde_path}")
        print(f"Arguments: {cmd_args}")

        procEnv = QtCore.QProcessEnvironment().systemEnvironment()

        plugins_path = str(pathlib.Path(self.rpde_path).parent / "usd")
        print("plugins_path: " + plugins_path)
        procEnv.insert("RPD_USD_PLUGINS", plugins_path)

        hoops_path = str(pathlib.Path(self.rpde_path).parent / "hoops")
        print("hoops_path: " + hoops_path)
        procEnv.insert("RPD_HOOPS_DIR", hoops_path)

        self.process = QtCore.QProcess()
        self.process.setProcessEnvironment(procEnv)
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.parseOutput)
        self.process.readyReadStandardError.connect(self.parseOutput)
        self.process.finished.connect(self.processFinished)

        self.process.start(self.rpde_path, cmd_args)
        self.progress_widget.appendLog("Started process...")

    def parseOutput(self):
        # get all output lines for parsing
        process_output = self.process.readAll()
        try:
            process_output = bytes(process_output).decode("utf8")
        except UnicodeDecodeError:
            process_output = bytes(process_output).decode("latin1", errors="ignore")

        # parse progress from output line, if any
        progress_value = self.getProgressValue()
        for output_line in process_output.replace("\r", "\n").split("\n"):
            if not output_line:
                continue
            # if we manage to identify a progress message, parse value and update widget
            regex = re.match(r"(\d+)%(.)\[(_|x)+", output_line.lstrip())
            if regex is not None:
                progress_value = int(regex[1])
            else:
                if output_line.startswith("ERROR"):
                    self.appendError(output_line)
                elif output_line.startswith("WARNING"):
                    self.appendWarning(output_line)
                else:
                    self.appendLog(output_line)

        self.setProgressValue(progress_value)

    def appendLog(self, log_line: str):
        if not self.progress_widget:
            return
        self.progress_widget.appendLog(log_line)

    def appendWarning(self, log_line: str):
        if not self.progress_widget:
            return
        self.progress_widget.appendWarning(log_line)

    def appendError(self, log_line: str):
        if not self.progress_widget:
            return
        self.progress_widget.appendError(log_line)

    def setProgressValue(self, value: int):
        if not self.progress_widget:
            return
        self.progress_widget.setProgressValue(value)

    def getProgressValue(self) -> int:
        if not self.progress_widget:
            return 0
        return self.progress_widget.getProgressValue()

    def cancelProcess(self):
        self.progress_widget.appendWarning("Cancelling process...")
        self.was_cancelled = True
        self.process.terminate()
        self.process.kill()
        self.process.waitForFinished()

    def processFinished(self):
        if self.was_cancelled:
            warn_msg = "The RapidPipeline 3D Processor execution was cancelled."
            self.progress_widget.appendWarning(warn_msg)
            if self.on_cancel:
                self.on_cancel()
            return

        exit_msg = f"Process finished - Exit Code: {self.process.exitCode()}."
        if self.process.exitCode() == 0:
            self.progress_widget.appendLog(exit_msg)
            self.was_successful = True
        else:
            self.progress_widget.appendError(exit_msg)

        # check if the process finished successfully and the file is in place
        if not self.was_successful:
            error_msg = "The RapidPipeline 3D Processor didn't finish running successfully."
            self.progress_widget.appendError(error_msg)
            if self.on_failure:
                self.on_failure()
            return

        if self.on_success:
            self.on_success()

        # finished successfully, display a msg to the user
        success_msg = "The RapidPipeline 3D Processor finished running successfully."
        self.progress_widget.appendLog(success_msg)
