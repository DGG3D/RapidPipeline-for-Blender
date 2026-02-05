import os
from typing import Callable, List
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    PYSIDE_VERSION = 2

COMMONS_ROOT = os.path.dirname(os.path.dirname(__file__))
ICONS_ROOT = os.path.join(COMMONS_ROOT, "assets", "icons")
LOGO_ROOT = os.path.join(COMMONS_ROOT, "assets", "logo")

# define max/min float and int values
int_validator = QtGui.QIntValidator()
MAX_INT = int_validator.top()
MIN_INT = int_validator.bottom()  # note: this is negative
float_validator = QtGui.QDoubleValidator()
MAX_FLOAT = float_validator.top()
MIN_FLOAT = float_validator.bottom()  # note: this is negative

def getFullLogoLabel(width: int = -1, height: int = -1) -> QtWidgets.QLabel:
    """
    Loads logo image and creates QLabel.
    """
    logo_label = QtWidgets.QLabel()
    img = QtGui.QImage(os.path.join(LOGO_ROOT, "logo_white.svg"))

    # scale by width or height
    if width > 0:
        img = img.scaledToWidth(width, QtCore.Qt.SmoothTransformation)
    elif height > 0:
        img = img.scaledToHeight(height, QtCore.Qt.SmoothTransformation)

    pixmap = QtGui.QPixmap(img)
    logo_label.setPixmap(pixmap)
    return logo_label

def getLogoLabel(width: int = 400) -> QtWidgets.QLabel:
    """
    Loads logo image and creates QLabel.
    """
    logo_label = QtWidgets.QLabel()
    img = QtGui.QImage(os.path.join(ICONS_ROOT, "rpd_icon.svg"))
    pixmap = QtGui.QPixmap(img.scaledToWidth(width, QtCore.Qt.SmoothTransformation))
    logo_label.setPixmap(pixmap)
    return logo_label

def getIconLabel(icon_name:str, width: int = 16) -> QtWidgets.QLabel:
    """
    Loads logo image and creates QLabel.
    """
    logo_label = QtWidgets.QLabel()
    img = QtGui.QImage(os.path.join(ICONS_ROOT, f"{icon_name}.svg"))
    pixmap = QtGui.QPixmap(img.scaledToWidth(width, QtCore.Qt.SmoothTransformation))
    logo_label.setPixmap(pixmap)
    return logo_label

def getLogoIcon() -> QtGui.QIcon:
    return QtGui.QIcon(os.path.join(ICONS_ROOT, "rpd_icon.svg"))

def getIcon(icon_id:str) -> QtGui.QIcon:
    return QtGui.QIcon(os.path.join(ICONS_ROOT, f"{icon_id}.svg"))

class IconButton(QtWidgets.QPushButton):
    def __init__(self, name: str = "", icon_name: str = "", tooltip: str = "", icon_path:str = ""):
        super().__init__()

        # keep original button palette
        self.__default_palette = self.palette()
        self.__default_color = self.__default_palette.color(QtGui.QPalette.Button)
        self.__light_color = self.__default_palette.color(QtGui.QPalette.Light)
        if name:
            self.setText(name)

        if icon_name:
            icon_path = os.path.join(ICONS_ROOT, f"{icon_name}.svg")

        if icon_path:
            self.setIcon(QtGui.QIcon(icon_path))
            self.setIconSize(QtCore.QSize(20, 20))

        if tooltip:
            self.setToolTip(tooltip)

    def setButtonText(self, name:str):
        self.setText(name)

    def setNewIcon(self, icon_name: str = "", icon_path: str = ""):
        if icon_name:
            icon_path = os.path.join(ICONS_ROOT, f"{icon_name}.svg")

        if icon_path:
            self.setIcon(QtGui.QIcon(icon_path))
            self.setIconSize(QtCore.QSize(16, 16))

    def setRPDButtonHighlight(self):
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#22cb83"))
        palette.setColor(QtGui.QPalette.Light, QtGui.QColor("#22cb83").lighter()) # button pressed background
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#000000"))
        palette.setColor(QtGui.QPalette.Midlight, QtGui.QColor("#000000")) # button pressed text
        self.setPalette(palette)
        self.update()

    def setRPDDefaultPalette(self):
        palette = QtGui.QPalette(self.__default_palette)
        palette.setColor(QtGui.QPalette.Light, QtGui.QColor("#22cb83").lighter()) # button pressed background
        palette.setColor(QtGui.QPalette.Midlight, QtGui.QColor("#000000")) # button pressed text
        self.setPalette(palette)
        self.update()

    def setCustomColor(self, color:QtGui.QColor):
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Button, color)
        self.setPalette(palette)
        self.update()

    def setDefaultPalette(self):
        self.setPalette(self.__default_palette)
        self.update()

    def setDefaultColor(self):
        self.setCustomColor(self.__default_color)

    def getDefaultColor(self) -> QtGui.QColor:
        return self.__default_color

    def getDefaultLightColor(self) -> QtGui.QColor:
        return self.__light_color

    def setCustomHighlightColor(self, color:QtGui.QColor):
        palette = self.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, color)
        self.setPalette(palette)

class Chevron(QtWidgets.QWidget):
    def __init__(self, name:str, toggle_function:Callable, start_state:bool = False):
        """
        Clickable button-like widget with Chevron icons representing its toggled state.
        Requires a toggle-function to be passed - it's expected that the function has
        only a booled argument representing the state (on/off) of the Chevron. When
        the chevron receives a click event, it's state is toggled.

        - When start_state is False, Chevron starts pointing Right.
        - When start_state is True, Chevron starts pointing Down.
        """
        super().__init__()
        self.main_layout = QtWidgets.QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.icon_label = QtWidgets.QLabel()
        self.main_layout.addWidget(self.icon_label, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.main_layout.addSpacing(2)
        self.name_label = QtWidgets.QLabel(name)
        self.name_label.setStyleSheet('font-size: 10pt;font-weight:bold')
        self.main_layout.addWidget(self.name_label, alignment=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.right_icon = QtGui.QImage(os.path.join(ICONS_ROOT, "chevron-right.svg"))
        self.pixmap_right = QtGui.QPixmap(self.right_icon.scaledToWidth(12, QtCore.Qt.SmoothTransformation))
        self.down_icon = QtGui.QImage(os.path.join(ICONS_ROOT, "chevron-down.svg"))
        self.pixmap_down = QtGui.QPixmap(self.down_icon.scaledToWidth(12, QtCore.Qt.SmoothTransformation))

        self.is_checked : bool = not start_state
        self.toggle_function = toggle_function
        self.buttonPressed()

    def buttonPressed(self):
        self.is_checked = not self.is_checked
        if self.is_checked:
            self.icon_label.setPixmap(self.pixmap_down)
        else:
            self.icon_label.setPixmap(self.pixmap_right)
        self.toggle_function(self.is_checked)

    def mousePressEvent(self, event:QtGui.QMouseEvent):
        self.buttonPressed()

class LabelDivider(QtWidgets.QWidget):
    def __init__(self, name: str) -> None:
        """
        Creates horizontal divider with a label.
        """
        super().__init__()
        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout.addWidget(QtWidgets.QLabel(name))

        self.line = QtWidgets.QFrame()
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Raised)
        # self.main_layout.addSpacing(-5)
        self.main_layout.addWidget(self.line)

    def sizeHint(self) -> QtCore.QSize:
        return self.minimumSizeHint()

class Gif(QtWidgets.QLabel):
    def __init__(self, file_path:str, size:QtCore.QSize):
        super().__init__()
        self.video_movie = QtGui.QMovie(file_path)
        self.video_movie.setScaledSize(size)
        self.setMovie(self.video_movie)
        self.video_movie.start()
        self.__video_is_paused = False

    def mousePressEvent(self, event:QtGui.QMouseEvent):
        self.__video_is_paused = not self.__video_is_paused
        self.video_movie.setPaused(self.__video_is_paused)

class LinkLabel(QtWidgets.QLabel):
    def __init__(self, text:str, address:str, callback:Callable, tooltip:str = ""):
        super().__init__(text=f"<a href=\"{address}\">{text}</a>")
        self.linkActivated.connect(callback)
        if tooltip:
            self.setToolTip(tooltip)

class MainMenu(QtWidgets.QWidget):
    def __init__(self, action_versions:List[str]):
        super().__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Maximum) #vertically, only grow as large as needed

        self.main_layout  = QtWidgets.QHBoxLayout()
        self.title_layout = QtWidgets.QHBoxLayout()
        self.tool_layout  = QtWidgets.QHBoxLayout()

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.key_button      = IconButton("", "key", "License Key settings.")
        self.settings_button = IconButton("", "settings", "Change Plugin settings.")
        self.help_button     = IconButton("", "help", "Help & About the Plugin.")

        self.title_layout.addWidget(getFullLogoLabel(height=20), alignment=QtCore.Qt.AlignLeft)

        fixedSizeButtonStyle = """
            QPushButton {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                margin: 0px;
                border: 0px;
                background: transparent;
            }
            QPushButton::menu-indicator {
                width: 0px;
                height: 0px;
                subcontrol-position: center bottom;
                subcontrol-origin: content;
                margin-left: 0px;
            }
        """

        self.key_button.setStyleSheet(fixedSizeButtonStyle)
        self.settings_button.setStyleSheet(fixedSizeButtonStyle)
        self.help_button.setStyleSheet(fixedSizeButtonStyle)

        self.tool_layout.addWidget(self.key_button)
        self.tool_layout.addWidget(self.settings_button)
        self.tool_layout.addWidget(self.help_button)

        self.__action_versions = action_versions
        self.version_dropdown = QtWidgets.QComboBox()
        self.version_dropdown.addItems(self.__action_versions)
        self.version_dropdown.setMinimumWidth(50)
        self.version_dropdown.setFixedHeight(28)
        self.tool_layout.addWidget(self.version_dropdown, alignment=QtCore.Qt.AlignRight)

        self.main_layout.addLayout(self.title_layout)
        self.main_layout.addStretch()
        self.main_layout.addLayout(self.tool_layout)


class ProcessingMenu(QtWidgets.QWidget):
    def __init__(self, is_cad_version:bool):
        super().__init__()
        self.header_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.header_layout)
        self.import_button = IconButton(icon_name="import")
        self.export_button = IconButton("Export 3D File", "export", "Export current node selection as a 3D file.")
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.addWidget(self.import_button, alignment=QtCore.Qt.AlignLeft)
        self.header_layout.addWidget(self.export_button, alignment=QtCore.Qt.AlignLeft)
        self.header_layout.addStretch() # stretch as much as possible

        if is_cad_version:
            self.import_button.setText("Import 3D or CAD File")
            self.import_button.setToolTip("Import 3D or CAD file into the DCC.")
        else:
            self.import_button.setText("Import 3D File")
            self.import_button.setToolTip("Import 3D file into the DCC.")


class ImporterProcessingMenu(QtWidgets.QWidget):
    def __init__(self, is_cad_version:bool):
        super().__init__()
        self.header_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.header_layout)
        self.import_button = IconButton(icon_name="import")
        self.import_button.setMinimumWidth(160)
        self.import_button.setMinimumHeight(28)
        self.file_path_display = QtWidgets.QLineEdit()
        self.file_path_display.setPlaceholderText("Please select a file")
        self.file_path_display.setReadOnly(True)
        self.file_path_display.setMinimumWidth(250)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.addWidget(self.import_button, alignment=QtCore.Qt.AlignLeft)
        self.header_layout.setSpacing(10)
        self.header_layout.addWidget(self.file_path_display)

        if is_cad_version:
            self.import_button.setText("Select 3D or CAD File...")
            self.import_button.setToolTip("Select 3D or CAD file to be imported.")
        else:
            self.import_button.setText("Select 3D File...")
            self.import_button.setToolTip("Select 3D file to be imported.")

class Footer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.footer_layout = QtWidgets.QHBoxLayout()
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.footer_layout)

        # run button is a special case
        self.run_button = IconButton()
        self.setRunButton(True)

        self.footer_layout.addWidget(self.run_button)

    def setRunButton(self, run_flag:bool):
        """
        Toggle run button states between "Run" and "Cancel".
        """
        if run_flag:
            self.run_button.setButtonText("Run")
            self.run_button.setNewIcon("run")
            self.run_button.setMinimumHeight(28)
            self.run_button.setToolTip("Run magic action with the currently selected settings.")
            palette = self.run_button.palette()
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#22cb83"))
            palette.setColor(QtGui.QPalette.Light, QtGui.QColor("#22cb83").lighter()) # button pressed background
            palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#000000"))
            palette.setColor(QtGui.QPalette.Midlight, QtGui.QColor("#000000")) # button pressed text
            self.run_button.setPalette(palette)
        else:
            self.run_button.setButtonText("Cancel")
            self.run_button.setNewIcon("cancel")
            self.run_button.setToolTip("Cancel current process.")
            palette = self.run_button.palette()
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#cb2222"))
            palette.setColor(QtGui.QPalette.Light, QtGui.QColor("#cb2222").lighter()) # button pressed background
            palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#ffffff"))
            palette.setColor(QtGui.QPalette.Midlight, QtGui.QColor("#ffffff")) # button pressed text
            self.run_button.setPalette(palette)
        self.run_button.update()
        self.run_button.repaint()

class FlowLayout(QtWidgets.QLayout):
    """
    # Copyright (C) 2013 Riverbank Computing Limited.
    # Copyright (C) 2022 The Qt Company Ltd.
    # SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
    source: https://doc.qt.io/qtforpython-6/examples/example_widgets_layouts_flowlayout.html
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))

        self.__widget_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.__widget_list.append(item)

    def count(self):
        return len(self.__widget_list)

    def itemAt(self, index):
        if (index >= 0) and (index < self.count()):
            return self.__widget_list[index]
        return None

    def takeAt(self, index):
        if (index >= 0) and (index < self.count()):
            return self.__widget_list.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()

        for item in self.__widget_list:
            size = size.expandedTo(item.minimumSize())

        size += QtCore.QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        app_instance = QtWidgets.QApplication.instance()
        style = app_instance.style()
        layout_spacing_x = style.layoutSpacing(
            QtWidgets.QSizePolicy.ControlType.PushButton, QtWidgets.QSizePolicy.ControlType.PushButton,
            QtCore.Qt.Orientation.Horizontal
        )
        layout_spacing_y = style.layoutSpacing(
            QtWidgets.QSizePolicy.ControlType.PushButton, QtWidgets.QSizePolicy.ControlType.PushButton,
            QtCore.Qt.Orientation.Vertical
        )
        space_x = spacing + layout_spacing_x
        space_y = spacing + layout_spacing_y

        for item in self.__widget_list:
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()

def getSupportedInputFiles(is_cad_version:bool) -> list[str]:
    """
    Hard-coded list of supported input file types by RPDE when CAD version is present.
    """

    base_str = """
    GLTF (*.gltf)
    GLTF Binary (*.glb)
    VRM (*.vrm)
    Wavefront OBJ (*.obj)
    PLY - Polygon File Format (*.ply)
    STL (*.stl)
    OpenCTM (*.ctm)
    Universal Scene Description Zipped (*.usdz)
    Universal Scene Description (*.usd *.usda *.usdc)
    FBX (*.fbx)
    """

    # if we have the cad version, append the cad files
    if is_cad_version:
        base_str += """
        STEP (*.step *.stp *.stpx *.stpxz *.stpz)
        IGES (*.iges *.igs)
        JT (*.jt)
        Drawing Interchange Format (*.dxf)
        Design Web Format (*.dwf *.dwfx)
        DWG (*.dwg)
        Inventor (*.iam *.ipt)
        Revit (*.rfa *.rvt)
        3DS (*.3ds)
        Autodesk Navisworks (*.nwd)
        U3D (*.u3d)
        SolidWorks (*.sldasm *.sldprt)
        CATIA (*.3dxml *.catdrawing *.catpart *.catproduct *.catshape *.cgr *.dlv *.exp *.model *.session)
        ACIS (*.sab *.sat)
        Solid Edge (*.asm *.par *.psm *.pwd)
        Creo (*.asm *.neu *.prt *.xas *.xpr)
        Parasolid (*.x_b *.x_t *.xmt *.xmt_txt)
        DGN (Design) (*.dgn)
        Virtual Reality Modeling Language (*.vmrl *.wrl)
        COLLADA (*.dae)
        3D Manufacturing Format (*.3mf)
        Rhino3D (*.3dm)
        I-deas (*.arc *.mf1 *.pkg *.unv)
        IFC (*.ifc *.ifczip)
        VDA-FS (*.vda)
        PRC (*.prc)
        """

    # we need to perform some cleanup to avoid multiple 'all files (*)'
    # entries due to whitespaces

    # cleanup/formatting: apply map of strip to splitted string list
    file_types     = [line for line in map(lambda s : s.strip(), base_str.split("\n")) if line]
    file_types_str = ";;".join(file_types)

    # prepend general entry for all supported formats (default selection)
    file_extensions = [line for line in map(lambda s : s[s.find("(") + 1 : s.find(")")].strip(), base_str.split("\n"))]
    file_extensions = list(filter(lambda s : s != "", file_extensions))
    file_types_str  = "Supported Formats (" + " ".join(file_extensions) + ");;" + file_types_str

    return file_types_str

def getSupportedOutputFiles() -> list[str]:
    base_str = """
    GLTF - GL Transmission Format (*.gltf)
    GLB (*.glb)
    Wavefront OBJ (*.obj)
    PLY - Polygon File Format (*.ply)
    STL (*.stl)
    OpenCTM (*.ctm)
    USDZ - Universal Scene Description (Zip) (*.usdz)
    USD - Universal Scene Description (*.usd *.usda *.usdc)
    FBX (*.fbx)
    """
    # we need to perform some cleanup to avoid multiple 'all files (*)'
    # entries due to whitespaces

    # cleanup/formatting: apply map of strip to splitted string list
    file_types = [line for line in map(lambda s : s.strip(), base_str.split("\n")) if line]

    # join the strings back with ';;'
    return ";;".join(file_types)
