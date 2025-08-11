import os
from PySide6 import QtWidgets, QtCore
import webbrowser

from magic_actions.licensing import ProcessorLicense
from pyside_common import utils as pyside_utils

class LicenseDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)

        # set window icon and title
        self.setWindowIcon(pyside_utils.getLogoIcon())
        self.setWindowTitle("Set RapidPipeline Auth Token")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)

        token_str = "Please insert your Auth Token. By default, it will be valid for the current session only."
        self.token_label = QtWidgets.QLabel(token_str, wordWrap=True)
        self.main_layout.addWidget(self.token_label)
        self.token_input = QtWidgets.QLineEdit(ProcessorLicense.getAPIToken())
        self.main_layout.addWidget(self.token_input)

        self.keep_checkbox = QtWidgets.QCheckBox("Use Token for Future Sessions.")
        self.keep_checkbox.setToolTip("If checked, the current Auth Token will be saved to disk for future usage.")
        self.keep_checkbox.setChecked(False)
        self.main_layout.addWidget(self.keep_checkbox)

        # create terms and conditions widget
        self.terms_widget = QtWidgets.QWidget()
        self.terms_layout = QtWidgets.QHBoxLayout()
        self.terms_layout.setContentsMargins(0, 0, 0, 0)
        self.terms_widget.setLayout(self.terms_layout)
        self.main_layout.addWidget(self.terms_widget)
        terms_str = "the Rapid Pipeline Terms and Conditions."
        terms_link = r"https://rapidpipeline.com/en/general-terms-and-conditions/"
        self.terms_checkbox = QtWidgets.QCheckBox()
        self.terms_checkbox.setChecked(False)
        self.terms_checkbox.stateChanged.connect(self.onAcceptTerms)
        self.terms_label = QtWidgets.QLabel(f"I have read and agree to <a href=\"{terms_link}\">{terms_str}</a>")
        self.terms_label.linkActivated.connect(self.onViewTerms)
        self.terms_label.setToolTip("Opens the Terms & Conditions in the RapidPipeline website.")
        self.terms_layout.addWidget(self.terms_checkbox)
        self.terms_layout.addWidget(self.terms_label)

        # create button widget
        self.button_widget = QtWidgets.QWidget()
        self.button_layout = QtWidgets.QGridLayout()
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_widget.setLayout(self.button_layout)
        self.main_layout.addWidget(self.button_widget)

        # create and add buttons
        self.select_btn = QtWidgets.QPushButton("OK")
        self.button_layout.addWidget(self.select_btn, 0, self.button_layout.columnCount())
        self.select_btn.pressed.connect(self.onSelect)
        self.select_btn.setDisabled(True)

        self.create_btn = QtWidgets.QPushButton("Create Auth Token")
        self.create_btn.setToolTip("Opens the RapidPipeline website to create a token.")
        self.button_layout.addWidget(self.create_btn, 0, self.button_layout.columnCount())
        self.create_btn.pressed.connect(self.onCreate)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.button_layout.addWidget(self.cancel_btn, 0, self.button_layout.columnCount())
        self.cancel_btn.pressed.connect(self.onCancel)

        self.token_input.textChanged.connect(self.onAcceptTerms)

        self.__clicked_btn = -1

    def onAcceptTerms(self):
        """
        User can only accept if they both insert a token and if the terms checkbox is checked.
        """
        self.select_btn.setDisabled((not self.token_input.text()) or not self.terms_checkbox.isChecked())

    def onViewTerms(self):
        webbrowser.open(r"https://rapidpipeline.com/en/general-terms-and-conditions/")

    def onSelect(self):
        self.__clicked_btn = 1
        is_temp = not self.keep_checkbox.isChecked()
        account_file = ProcessorLicense.createLicenseFile(self.token_input.text(), is_temp)
        if account_file is not None:
            os.environ["RPD_ACCOUNTFILE"] = account_file
        self.close()

    def onCreate(self):
        webbrowser.open(r"https://app.rapidpipeline.com/api_tokens")

    def onCancel(self):
        self.__clicked_btn = -1
        self.close()

    def exec(self):
        super().exec()
        return self.__clicked_btn
