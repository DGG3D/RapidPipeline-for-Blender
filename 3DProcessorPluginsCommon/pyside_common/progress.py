from PySide6 import QtCore, QtWidgets, QtGui
from abc import abstractmethod

from utils import Chevron, IconButton, getIconLabel

class ProgressLog(QtWidgets.QWidget):
    """
    Abstract class for progress log widgets.
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def appendLog(self, log_line:str):
        pass

    @abstractmethod
    def appendWarning(self, log_line:str):
        pass

    @abstractmethod
    def appendError(self, log_line:str):
        pass

    @abstractmethod
    def setProgressValue(self, value:int):
        pass

    @abstractmethod
    def getProgressValue(self):
        pass

class ProcessProgressLog(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # create progress bar
        self.min_progress = 0
        self.max_progress = 100
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setMaximum(self.max_progress)
        self.progress_bar.setMinimum(self.min_progress)
        self.progress_bar.setValue(0)

        # create log view
        self.log_view = QtWidgets.QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setWordWrapMode(QtGui.QTextOption.WrapMode.NoWrap)
        self.log_view.setFixedHeight(120)

        # set background and text color
        log_palette = self.log_view.palette()
        log_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#2B2B2B"))
        log_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#C8C8C8"))
        self.log_view.setPalette(log_palette)

        # show chevron + status icons
        self.show_widget = QtWidgets.QWidget()
        self.show_layout = QtWidgets.QHBoxLayout()
        self.show_layout.setContentsMargins(0, 0, 0, 0)
        self.show_widget.setLayout(self.show_layout)

        # create chevron button and setup callback
        self.show_button = Chevron("Process Log", toggle_function=self.showLog, start_state=True)
        self.show_layout.addWidget(self.show_button, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # add icosn to show widget
        self.warning_icon = getIconLabel(icon_name="warning", width=12)
        self.error_icon = getIconLabel(icon_name="error", width=12)
        self.show_layout.addStretch()
        self.show_button.main_layout.insertWidget(1, self.warning_icon, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.show_button.main_layout.insertWidget(1, self.error_icon,  alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.warning_icon.setHidden(True)
        self.error_icon.setHidden(True)

        self.warning_icon.setToolTip("Warnings identified in the RapidPipeline execution.")
        self.error_icon.setToolTip("Errors identified in the RapidPipeline execution.")

        # add widgets
        self.main_layout.addWidget(self.show_widget, alignment=QtCore.Qt.AlignLeft)
        self.main_layout.addWidget(self.log_view)
        self.main_layout.addSpacing(5)
        self.main_layout.addWidget(self.progress_bar)

        # progress bar starts hidden
        self.progress_bar.setHidden(True)

    def showLog(self, show_flag:bool):
        self.log_view.setHidden(not show_flag)

    def appendLog(self, log_line:str):
        self.log_view.append(log_line)

    def appendWarning(self, log_line:str):
        log_line = log_line.removeprefix("WARNING: ")
        warning_format = '<span style="color:#F1E582;">WARNING: {}</span>'
        self.log_view.append(warning_format.format(log_line))
        if self.error_icon.isHidden() and self.warning_icon.isHidden():
            self.warning_icon.setHidden(False)

    def appendError(self, log_line:str):
        log_line = log_line.removeprefix("ERROR: ")
        error_format = '<span style="color:#CF212E;">ERROR: {}</span>'
        self.log_view.append(error_format.format(log_line))
        if self.error_icon.isHidden():
            self.warning_icon.setHidden(True)
            self.error_icon.setHidden(False)

    def setProgressValue(self, value:int):
        self.progress_bar.setValue(value)

    def getProgressValue(self):
        return self.progress_bar.value()