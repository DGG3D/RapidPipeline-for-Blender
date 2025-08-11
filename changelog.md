# RapidPipeline for Blender

## Changelog

### Version v1.0.0 August 07, 2025
* Magic Action release
    * Added multiple new magic actions
    * Added preview image and description for each magic action
* Added File Export using RPDE
* Added File Import using RPDE
* Fixed a bug where a node would get deleted if selected during running
* Fixed an issue that caused blender to freeze on multiple processing steps
* Updated rpde on version 7.4.1 and Schema to Version 1.4
* Improved performance of model import
* General improvements to UI responsiveness and performance 
* Updated the settings page of the plugin
* Float values are now displayed with a precision of 3 digits to avoid confusion with some default values
* Updated icons and UI layout

### Version v0.2.3 June 30, 2025
* Added Magic Actions
    * A feature to quickly select and modify commonly used presets.
        This allows for quick and easy processing without the need of in-depth knowledge of 3D processing tools 
* Added option for tessellation resolution in CAD import
* Added native CAD import file viewer
* Fixed an issue where processed CAD imports would create loose nodes
* Improvements to sorting of nodes in collections after processing 
* Processing now exports textures as png per default
* Updated schema used to match the version of other RapidPipeline Products
* General improvements to stability

### Version v0.2.2 May 22, 2025
* Plugin now able to run outside of object mode
* Fixed floating point rounding error
* Updated Labels on buttons
* Fixed collections for scene graph flattening option

### Version v0.2.1 April 24, 2025
* CAD files imported are now moved to the correct collection
* Changed position of Buttons in UI
* Updated UI for entering rpde token
* Updated Labels and tooltips on buttons
* Change to arguments on rpde call

### Version v0.2.1-1 May 02, 2025
* fixed issue of cad import deleting selection
* fixed issue of multiple runs not in the right collection
* cad import now gets moved to a collection named after the cad file

### Version v0.2.0 March 25, 2025
* Use Blender native UI instead of pyside
* Support of Mac OS 
* Complete overhall of UI scripts to adjust to Blender internal API bpy
* Removed Standalone version and pyside scripts
* Added an option to import CAD models

* Fixed naming and placemet of nodes in their collections after running
* Fixed a bug with adding a temporary token
* Added Tooltips to UI elements
* Most Input fields are now limited to a min and max value

* Tab can be enabled and disabled
* Cancel and retry button on execution
* Improved Settings export
* Minimum and Maximum limits to input fields
* general Improvements to UI


### Version v0.1.3 November 11, 2024
* Export / Import format changed to glb instead of gltf
* Output directory does not have to be defined by the user anymore
* Fixed bugs with uninstall process

### Version v0.1.2 November 07, 2024
* Updates to the schema
* Check if Blender is open during plugin installation
* Force file removal during uninstall

### Version v0.1.1 October 22, 2024

* User-defined output directory for GLTF export
* Help link now directs straight to the plugin page
* Plugin window remains in the foreground only when Blender is focused
* Improved handling of child-parent connections
* Hides collection node if all nodes within are hidden
* Verifies existence of Blender executable during installation


### Version v0.1.0 August 15th, 2024

* Enables you to use the RapidPipeline 3D Processor right from the Blender UI
* Process, optimize & simplify 3D models 100% locally
* Allows creating, saving, and loading of presets based on 3D Processor v7.x schema
