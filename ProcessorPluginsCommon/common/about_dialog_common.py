class AboutDialogBase():

    tool = ""
    plugin_version = ""
    window_title = "About the Plugin & Open Source Licenses"
    plugin_info = "test"


    def __init__(self, plugin_version:str, tool:str, **kwargs):
        self.plugin_version = plugin_version
        self.tool = tool
        self.plugin_info = f"The RapidPipeline Plugin for {tool} v{plugin_version}"
        super().__init__(**kwargs)
