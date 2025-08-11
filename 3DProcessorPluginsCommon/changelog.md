# RapidPipeline Plugin Common Library

## Changelog

### v0.9.0 - July 25th, 2025

* Support for a new variant of `MainWidget` that only contains Import actions has been added as a subclass of `MainWidget`, `ImportMainWidget`.
  * Some methods have been refactored to better support this new widget variant.
* A warning window is now displayed when the user attempts to process without having saved the scene file.
  * The user may choose to skip this warning for the remaining of this session.
* The file picker menus now take the last valid folder selected as a starting folder, if available, or the Desktop/Home folder of the user otherwise.
* Several UI adjustments as part of an ongoing redesign.
* Added new functions to validate and obtain user information from their API token.
* Add support to Export settings in Schema and Settings File parsing functions.
* Add a new optional "Read More" link as part of the actions description, obtained from an optional `"read_more"` field from the action `meta.json` file.
* `ActionContainer` can now have an arbitrary number of button columns.
* If an `ActionContainer` only has one action, the selection buttons are now hidden away.
* Several adjustments performed to the `ImportDialog`.
* Introduced a new `ExportDialog` class as a subclass of `ImportDialog`:
  * By default, this dialog only exposed one action of a given file format.
  * The name and description of the export action is not displayed in Export dialogs.
* The signature for the RPDE executable has been adjusted.
* Warning and Error icons have been added to the `ProgressLog` widget.
* The log view colors have been updated.
* The `BaseProperty` class is no longer a subclass of QWidget.
* Setting Widget classes now multi-inherit from `BaseProperty` and their respective parent widget class.
* A new `ToggleableObject` class has been added, adding initial support for toggleable options.
* New Palette and Highlight methods have been added to the `IconButton` class.
* A new `LinkLabel` class has been added for the "Read More" links.
* The `Header` class has been removed.
* The `ProcessingMenu` class has been added, containing the Import and Export buttons.
* The `MainMenu` class has been added, containing the application logo as well as the License Key button, a new Settings Menu dropdown, a Help menu dropdown, and an Action Version selection dropdown.
* New links for feedback and support have been added.
* Fixed issue in certain PySide6 environments, such as Maya, where Push buttons that interact with a modal dialog would stay in a pressed state.