"""
Kolibri configuration data
==========================

.. warning::
    Do not load any django.conf.settings stuff here. This configuration data
    precedes loading of settings, it is not part of the settings stack.

TODO: We need to figure out our conf API. Do we store in ini/json/yaml?

 * How do we retrieve config data?
 * When should configuration files be loaded and written?

This module should be easier to document, for instance by having VARIABLES
instead of a dict.

"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import os

from django.utils.functional import SimpleLazyObject

from .compat import module_exists

logger = logging.getLogger(__name__)

#: Absolute path of the main user data directory.
#: Will be created automatically if it doesn't exist.
KOLIBRI_HOME = os.path.abspath(os.path.expanduser(os.environ["KOLIBRI_HOME"]))

# Creating KOLIBRI_HOME atm. has to happen here as for instance utils.cli is not
# called through py.test. This file is the first basic entry point of
# Kolibri, although utils.cli may or may not precede it.
if not os.path.exists(KOLIBRI_HOME):
    parent = os.path.dirname(KOLIBRI_HOME)
    if not os.path.exists(parent):
        raise RuntimeError(
            "The parent of your KOLIBRI_HOME does not exist: {}".format(parent)
        )
    os.mkdir(KOLIBRI_HOME)

# Create a folder named logs inside KOLIBRI_HOME to store all the log files.
LOG_ROOT = os.path.join(KOLIBRI_HOME, "logs")
if not os.path.exists(LOG_ROOT):
    os.mkdir(LOG_ROOT)


try:
    # The default list for this is populated from build_tools/default_plugins.txt
    # in the root of the Kolibri repository. The default list is identical to the list below,
    # except that the style_guide plugin is not enabled in production builds.
    # Caveat: this list may have been changed at build time to specify a different list of plugins.
    from .build_config.default_plugins import plugins

    DEFAULT_PLUGINS = plugins
except ImportError:
    DEFAULT_PLUGINS = [
        "kolibri.plugins.facility_management",
        "kolibri.plugins.device_management",
        "kolibri.plugins.learn",
        "kolibri.plugins.document_pdf_render",
        "kolibri.plugins.html5_app_renderer",
        "kolibri.plugins.media_player",
        "kolibri.plugins.setup_wizard",
        "kolibri.plugins.coach",
        "kolibri.plugins.user",
        "kolibri_exercise_perseus_plugin",
        "kolibri.plugins.style_guide",
        "kolibri.plugins.document_epub_render",
        "kolibri.plugins.default_theme",
        "kolibri.plugins.slideshow_render",
    ]

conf_file = os.path.join(KOLIBRI_HOME, "kolibri_settings.json")


# These values are encoded on the config dict as sets
# so they need to be treated specially for serialization
# and deserialization to/from JSON
SET_KEYS = ["INSTALLED_APPS", "DISABLED_APPS"]


class ConfigDict(dict):
    def __init__(self):
        # If the settings file does not exist or does not contain
        # valid JSON then create it
        self.set_defaults()
        if os.path.isfile(conf_file):
            try:
                # Open up the config file and load settings
                # use default OS encoding
                with open(conf_file, "r") as kolibri_conf_file:
                    self.update(json.load(kolibri_conf_file))
                return
            except json.JSONDecodeError:
                logger.warn(
                    "Attempted to load kolibri_settings.json but encountered a file that could not be decoded as valid JSON."
                )
        logger.info("Initialize kolibri_settings.json..")
        self.save()

    def set_defaults(self):
        self.update(
            {
                #: Everything in this list is added to django.conf.settings.INSTALLED_APPS
                # except disabled ones below
                "INSTALLED_APPS": DEFAULT_PLUGINS,
                #: Everything in this list is removed from the list above
                "DISABLED_APPS": [],
            }
        )

    @property
    def ACTIVE_PLUGINS(self):
        return list(self["INSTALLED_APPS"] - self["DISABLED_APPS"])

    def update(self, new_values):
        """
        Updates current configuration with ``new_values``. Does not save to file.
        """
        values_copy = new_values.copy()
        for key in SET_KEYS:
            if key in values_copy:
                values_copy[key] = set(values_copy[key])
        super(ConfigDict, self).update(values_copy)

    def save(self):
        # use default OS encoding
        config_copy = self.copy()
        for key in SET_KEYS:
            if key in config_copy:
                config_copy[key] = list(config_copy[key])
        with open(conf_file, "w") as kolibri_conf_file:
            json.dump(config_copy, kolibri_conf_file, indent=2, sort_keys=True)

    def autoremove_unavailable_plugins(self):
        """
        Sanitize INSTALLED_APPS - something that should be done separately for all
        build in plugins, but we should not auto-remove plugins that are actually
        configured by the user or some other kind of hard dependency that should
        make execution stop if not loadable.
        """
        changed = False
        # Iterate over a copy of the set so that it is not modified during the loop
        for module_path in self["INSTALLED_APPS"].copy():
            if not module_exists(module_path):
                self["INSTALLED_APPS"].remove(module_path)
                logger.error(
                    (
                        "Plugin {mod} not found and disabled. To re-enable it, run:\n"
                        "   $ kolibri plugin {mod} enable"
                    ).format(mod=module_path)
                )
                changed = True
        if changed:
            self.save()

    def enable_default_plugins(self):
        """
        Enable new plugins that have been added between versions
        This will have the undesired side effect of reactivating
        default plugins that have been explicitly disabled by a user,
        in versions prior to the implementation of a plugin blacklist.
        """
        changed = False
        for module_path in DEFAULT_PLUGINS:
            if module_path not in self["INSTALLED_APPS"]:
                self["INSTALLED_APPS"].add(module_path)
                # Can be migrated to upgrade only logic
                if module_path not in self["DISABLED_APPS"]:
                    logger.warning(
                        (
                            "Default plugin {mod} not found in configuration. To re-disable it, run:\n"
                            "   $ kolibri plugin {mod} disable"
                        ).format(mod=module_path)
                    )
                changed = True

        if changed:
            self.save()

    def enable_plugin(self, module_path):
        self["INSTALLED_APPS"].add(module_path)
        try:
            self["DISABLED_APPS"].remove(module_path)
        except KeyError:
            pass

    def disable_plugin(self, module_path):
        self["DISABLED_APPS"].add(module_path)
        try:
            self["INSTALLED_APPS"].remove(module_path)
        except KeyError:
            pass


#: Set defaults before updating the dict
config = ConfigDict()


def __initialize_options():
    # read the config file options in here so they can be accessed from a standard location
    from .options import read_options_file

    return read_options_file(KOLIBRI_HOME)


OPTIONS = SimpleLazyObject(__initialize_options)
