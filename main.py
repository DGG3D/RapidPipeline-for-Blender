import os

try:
    import tomllib
except ModuleNotFoundError:
    pass

from .license_manager import ProcessorLicense
from .ProcessorPluginsCommon.common.main_widget_common import MainWidgetBase


class MainData(MainWidgetBase):
    # needed for MainWidgetBase functions
    ProcessorLicense = ProcessorLicense
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MainData, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    __tool = "blender"
    __dirname = os.path.dirname(__file__)
    __blender_manifest = os.path.join(__dirname, 'blender_manifest.toml')
    __plugin_version = ""
    try:
        with open(__blender_manifest, 'rb') as f:
            __blender_manifest = tomllib.load(f)
        __plugin_version = __blender_manifest['version']
    except Exception:
        import traceback
        traceback.print_exc()
        __plugin_version = "?.?.?"

    def getUnOptimizedFormat(self) -> str:
        return "glb"

    def getOptimizedFormat(self) -> str:
        return os.environ.get("RPDP_PROCESSOR_DCC_OUTPUT", "glb")

    def __init__(self, **kwargs):
        super().__init__(self.__tool, self.__dirname, self.__plugin_version, **kwargs)
