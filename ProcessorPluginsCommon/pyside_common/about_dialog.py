import os
import webbrowser
from PySide6 import QtWidgets, QtCore, QtGui

from pyside_common import utils as pyside_utils
from magic_actions import utils as action_utils

class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, tool:str, plugin_version:str, plugin_root:str):
        super().__init__(parent)

        # set window icon and title
        self.setWindowIcon(pyside_utils.getLogoIcon())
        self.setWindowTitle("About the Plugin & Open Source Licenses")

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)

        self.main_layout.addWidget(pyside_utils.getFullLogoLabel(width=200), alignment=QtCore.Qt.AlignCenter)
        self.main_layout.addSpacing(5)

        name_label = QtWidgets.QLabel(f"The RapidPipeline Plugin for {tool} v{plugin_version}")
        name_label.setStyleSheet('font-size: 16px;')
        self.main_layout.addWidget(name_label, alignment=QtCore.Qt.AlignCenter)
        self.main_layout.addSpacing(5)

        # add DGG copyright msg with e-mail link
        copyright_email = "support@dgg3d.com"
        copyright_str = f"Copyright (c) 2025 Darmstadt Graphics Group GmbH &lt;<a href=\"{copyright_email}\">{copyright_email}</a>&gt;"
        copyright_label = QtWidgets.QLabel(copyright_str)
        copyright_label.linkActivated.connect(lambda:webbrowser.open(rf"mailto:{copyright_email}"))
        self.main_layout.addWidget(copyright_label, alignment=QtCore.Qt.AlignCenter)
        self.main_layout.addSpacing(5)

        license_str = f"The RapidPipeline Plugin for {tool} is licensed\nunder the MIT License (excluding the RapidPipeline engine).\n"
        license_str += "Uses PySide6 libraries, licensed as LGPLv3, and Tabler Icons, licensed as MIT.\nFull licenses below."
        license_label = QtWidgets.QLabel(license_str, alignment=QtCore.Qt.AlignCenter)
        license_label.setWordWrap(True)
        self.main_layout.addWidget(license_label, alignment=QtCore.Qt.AlignCenter)
        self.main_layout.addSpacing(5)

        self.main_layout.addWidget(pyside_utils.LabelDivider("Open Source Software Licenses"))

        # create and add log view to main layout
        self.license_view = QtWidgets.QTextEdit(self)
        self.license_view.setReadOnly(True)
        self.license_view.setFixedSize(400, 250)
        self.license_view.setWordWrapMode(QtGui.QTextOption.WrapMode.NoWrap)
        self.license_view.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse)
        self.main_layout.addWidget(self.license_view, alignment=QtCore.Qt.AlignCenter)

        self.addOSSLicense("The RapidPipeline 3D Processor Engine CLI - License Disclaimer", os.path.join(plugin_root, "rpd_plugins_common", "licenses", "RPDE.md"))
        self.addOSSLicense(f"The RapidPipeline Plugin for {tool}", os.path.join(plugin_root, "LICENSE.md"))
        self.addOSSLicense("The RapidPipeline Plugin Commons", os.path.join(plugin_root, "rpd_plugins_common", "LICENSE.md"))
        self.addOSSLicense("The RapidPipeline Magic Actions", os.path.join(plugin_root, "magic-actions", "LICENSE.md"))
        self.addOSSLicense("PySide6", os.path.join(plugin_root, "rpd_plugins_common", "licenses", "PYSIDE6.md"))
        self.addOSSLicense("Tabler Icons", os.path.join(plugin_root, "rpd_plugins_common", "licenses", "TABLER.md"))

        self.setFixedWidth(420)

    def showEvent(self, event):
        """
        Moves license view to the start before showing dialog.
        """
        self.license_view.moveCursor(QtGui.QTextCursor.Start)
        super().showEvent(event)

    def addOSSLicense(self, license_name: str, license_file: str):
        """
        Appends an extra Open Source Software license to our list of licenses.
        """
        # license header
        self.license_view.append("".center(50, "="))
        self.license_view.append(license_name)
        self.license_view.append("".center(50, "="))

        # license body
        license_text = "".join(action_utils.parseTextFile(license_file)) + "\n\n"
        self.license_view.append(license_text)
