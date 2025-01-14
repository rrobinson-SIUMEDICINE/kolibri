"""
Kolibri Webpack hooks
---------------------

To manage assets, we use the webpack format. In order to have assets bundled in,
you should put them in ``yourapp/assets/src``.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import codecs
import io
import json
import logging
import os
import re
import time
from functools import partial

from django.conf import settings
from django.contrib.staticfiles.finders import find as find_staticfiles
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.cache import caches
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.six.moves.urllib.request import url2pathname
from django.utils.translation import get_language
from django.utils.translation import get_language_info
from django.utils.translation import to_locale
from pkg_resources import resource_filename
from six import text_type

from kolibri.plugins import hooks

# Use the cache specifically for built files
# Only reference the specific cache inside methods
# to allow this file to be imported without initiating
# Django settings configuration.
CACHE_NAMESPACE = "built_files"

IGNORE_PATTERNS = (re.compile(I) for I in [r".+\.hot-update.js", r".+\.map"])


class BundleNotFound(Exception):
    pass


class WebpackError(EnvironmentError):
    pass


logger = logging.getLogger(__name__)


def filter_by_bidi(bidi, chunk):
    if chunk["name"].split(".")[-1] != "css":
        return True
    if bidi:
        return chunk["name"].split(".")[-2] == "rtl"
    else:
        return chunk["name"].split(".")[-2] != "rtl"


class WebpackBundleHook(hooks.KolibriHook):
    """
    This is the abstract hook class that all plugins that wish to load any
    assets into the front end must implement, in order for them to be part of
    the webpack asset loading pipeline.
    """

    # : You should set a human readable name that is unique within the
    # : plugin in which this is defined.
    bundle_id = ""

    # : When being included for synchronous loading, should the source files
    # : for this be inlined?
    inline = False

    # : A mapping of key to JSON serializable value.
    # : This plugin_data will be bootstrapped into a global object on window
    # : with a key of the unique_id as a Javascript object
    plugin_data = {}

    def __init__(self, *args, **kwargs):
        super(WebpackBundleHook, self).__init__(*args, **kwargs)

        # Verify the uniqueness of the unique_id
        # It can be '0' in the parent class constructor
        assert (
            len([x for x in self.registered_hooks if x.unique_id == self.unique_id])
            <= 1
        ), "Non-unique id found: '{}'".format(self.unique_id)

    @hooks.abstract_method
    def get_by_unique_id(self, unique_id):
        """
        Fetch a registered hook instance by its unique_id
        """
        for hook in self.registered_hooks:

            if hook.unique_id == unique_id:
                return hook
        raise BundleNotFound("No bundle with that name is loaded: {}".format(unique_id))

    @cached_property
    @hooks.registered_method
    def _stats_file_content(self):
        """
        :returns: A dict of the data contained in the JSON files which are
          written by Webpack.
        """
        cache_key = "json_stats_file_cache_{unique_id}".format(unique_id=self.unique_id)
        try:
            stats_file_content = caches[CACHE_NAMESPACE].get(cache_key)
            if not stats_file_content or getattr(settings, "DEVELOPER_MODE", False):
                with io.open(self._stats_file, mode="r", encoding="utf-8") as f:
                    stats = json.load(f)
                if getattr(settings, "DEVELOPER_MODE", False):
                    timeout = 0
                    while stats["status"] == "compiling":
                        time.sleep(0.1)
                        timeout += 0.1
                        with io.open(self._stats_file, mode="r", encoding="utf-8") as f:
                            stats = json.load(f)
                        if timeout >= 5:
                            raise WebpackError("Webpack compilation still in progress")
                    if stats["status"] == "error":
                        raise WebpackError("Webpack compilation has errored")
                stats_file_content = {
                    "files": stats.get("chunks", {}).get(self.unique_id, []),
                    "hasMessages": stats.get("messages", False),
                }
                # Don't invalidate during runtime.
                # Might need to change this if we move to a different cache backend.
                caches[CACHE_NAMESPACE].set(cache_key, stats_file_content, None)
            return stats_file_content
        except IOError as e:
            if hasattr(e, "filename"):
                problem = "Problems loading: {file}".format(file=e.filename)
            else:
                problem = "Not file-related."
            raise WebpackError(
                "Webpack build file missing, front-end assets cannot be loaded. {problem}".format(
                    problem=problem
                )
            )

    @property
    @hooks.registered_method
    def bundle(self):
        """
        :returns: a generator yielding dict objects with properties of the built
          asset, most notably its URL.
        """
        for f in self._stats_file_content["files"]:
            filename = f["name"]
            if not getattr(settings, "DEVELOPER_MODE", False):
                if any(list(regex.match(filename) for regex in IGNORE_PATTERNS)):
                    continue
            relpath = "{0}/{1}".format(self.unique_id, filename)
            if getattr(settings, "DEVELOPER_MODE", False):
                try:
                    f["url"] = f["publicPath"]
                except KeyError:
                    f["url"] = staticfiles_storage.url(relpath)
            else:
                f["url"] = staticfiles_storage.url(relpath)
            yield f

    @property
    def unique_id(self):
        """
        Returns a globally unique id for the frontend module bundle.
        This is created by appending the locally unique bundle_id to the
        Python module path. This should give a globally unique id for the module
        and prevent accidental or malicious collisions.
        """
        return "{}.{}".format(self._module_path, self.bundle_id)

    @property
    def _module_path(self):
        return ".".join(self.__module__.split(".")[:-1])

    @property
    def _build_path(self):
        """
        An auto-generated path to where the build-time files are stored,
        containing information about the built bundles.
        """
        return resource_filename(self._module_path, "build")

    @property
    def _stats_file(self):
        """
        An auto-generated path to where the build-time files are stored,
        containing information about the built bundles.
        """
        return os.path.join(
            self._build_path, "{plugin}_stats.json".format(plugin=self.unique_id)
        )

    @property
    def _module_file_path(self):
        """
        Returns the path of the class inheriting this classmethod.
        """
        return os.path.dirname(self._build_path)

    def frontend_message_file(self, lang_code):
        message_file_name = "{name}-messages.json".format(name=self.unique_id)
        for path in getattr(settings, "LOCALE_PATHS", []):
            file_path = os.path.join(
                path, to_locale(lang_code), "LC_MESSAGES", message_file_name
            )
            if os.path.exists(file_path):
                return file_path

    def frontend_messages(self):
        lang_code = get_language()
        cache_key = "json_message_file_cache_{unique_id}_{lang}".format(
            unique_id=self.unique_id, lang=lang_code
        )
        message_file_content = caches[CACHE_NAMESPACE].get(cache_key, {})
        if not message_file_content or getattr(settings, "DEVELOPER_MODE", False):
            frontend_message_file = self.frontend_message_file(lang_code)
            if frontend_message_file:
                with io.open(frontend_message_file, mode="r", encoding="utf-8") as f:
                    message_file_content = json.load(f)
                caches[CACHE_NAMESPACE].set(cache_key, message_file_content, None)
        return message_file_content

    def sorted_chunks(self):
        bidi = get_language_info(get_language())["bidi"]
        return sorted(
            filter(partial(filter_by_bidi, bidi), self.bundle),
            key=lambda x: x["name"].split(".")[-1],
        )

    def js_and_css_tags(self):
        js_tag = '<script type="text/javascript" src="{url}"></script>'
        css_tag = '<link type="text/css" href="{url}" rel="stylesheet"/>'
        inline_js_tag = '<script type="text/javascript">{src}</script>'
        inline_css_tag = "<style>{src}</style>"
        # Sorted to load css before js
        for chunk in self.sorted_chunks():
            src = None
            if chunk["name"].endswith(".js"):
                if self.inline:
                    # During development, we do not write built files to disk
                    # Because of this, this call might return None
                    src = self.get_filecontent(chunk["url"])
                if src is not None:
                    # If it is not None, then we can inline it
                    yield inline_js_tag.format(src=src)
                else:
                    # If src is None, either this is not something we should be inlining
                    # or we are in development mode and need to fetch the file from the
                    # development server, not the disk
                    yield js_tag.format(url=chunk["url"])
            elif chunk["name"].endswith(".css"):
                if self.inline:
                    # During development, we do not write built files to disk
                    # Because of this, this call might return None
                    src = self.get_filecontent(chunk["url"])
                if src is not None:
                    # If it is not None, then we can inline it
                    yield inline_css_tag.format(src=src)
                else:
                    # If src is None, either this is not something we should be inlining
                    # or we are in development mode and need to fetch the file from the
                    # development server, not the disk
                    yield css_tag.format(url=chunk["url"])

    def frontend_message_tag(self):
        if self.frontend_messages():
            return [
                '<script>{kolibri_name}.registerLanguageAssets("{bundle}", "{lang_code}", {messages});</script>'.format(
                    kolibri_name="kolibriCoreAppGlobal",
                    bundle=self.unique_id,
                    lang_code=get_language(),
                    messages=json.dumps(
                        self.frontend_messages(), separators=(",", ":")
                    ),
                )
            ]
        else:
            return []

    def plugin_data_tag(self):
        if self.plugin_data:
            return [
                """
                <script>
                    window["{name}"] = window["{name}"] || {{}};
                    window["{name}"]["{bundle}"] = JSON.parse('{plugin_data}');
                </script>
                """.format(
                    name="kolibriPluginDataGlobal",
                    bundle=self.unique_id,
                    plugin_data=json.dumps(
                        self.plugin_data, separators=(",", ":")
                    ).replace("'", "\\'"),
                )
            ]
        else:
            return []

    def get_basename(self, url):
        """
        Takes full path to a static file (eg. "/static/css/style.css") and
        returns path with storage's base url removed (eg. "css/style.css").
        """
        base_url = staticfiles_storage.base_url

        # Cast ``base_url`` to a string to allow it to be
        # a string-alike object to e.g. add ``SCRIPT_NAME``
        # WSGI param as a *path prefix* to the output URL.
        # See https://code.djangoproject.com/ticket/25598.
        base_url = text_type(base_url)

        if not url.startswith(base_url):
            return None

        basename = url.replace(base_url, "", 1)
        # drop the querystring, which is used for non-compressed cache-busting.
        return basename.split("?", 1)[0]

    def get_filename(self, basename):
        """
        Returns full path to a file, for example:

        get_filename('css/one.css') -> '/full/path/to/static/css/one.css'
        """
        filename = None
        # First try finding the file using the storage class.
        # This is skipped in DEVELOPER_MODE mode as files might be outdated
        # Or may not even be on disk.
        if not getattr(settings, "DEVELOPER_MODE", False):
            filename = staticfiles_storage.path(basename)
            if not staticfiles_storage.exists(basename):
                filename = None
        # secondly try to find it with staticfiles
        if not filename:
            filename = find_staticfiles(url2pathname(basename))
        return filename

    def get_filecontent(self, url):
        """
        Reads file contents using given `charset` and returns it as text.
        """
        cache_key = "inline_static_file_content_{url}".format(url=url)
        content = caches[CACHE_NAMESPACE].get(cache_key)
        if content is None:
            # Removes Byte Oorder Mark
            charset = "utf-8-sig"
            basename = self.get_basename(url)

            if basename is None:
                return None

            filename = self.get_filename(basename)

            if filename is None:
                return None

            with codecs.open(filename, "r", charset) as fd:
                content = fd.read()
            # Cache this forever, as URLs will update for new files
            caches[CACHE_NAMESPACE].set(cache_key, content, None)
        return content

    def render_to_page_load_sync_html(self):
        """
        Generates the appropriate script tags for the bundle, be they JS or CSS
        files.

        :param bundle_data: The data returned from
        :return: HTML of script tags for insertion into a page.
        """
        tags = (
            self.plugin_data_tag()
            + self.frontend_message_tag()
            + list(self.js_and_css_tags())
        )

        return mark_safe("\n".join(tags))

    def render_to_page_load_async_html(self):
        """
        Generates script tag containing Javascript to register an
        asynchronously loading Javascript FrontEnd plugin against the core
        front-end Kolibri app. It passes in the events that would trigger
        loading the plugin, both multi-time firing events (events) and one time
        firing events (once).

        It also passes in information about the methods that the events should
        be delegated to once the plugin has loaded.

        TODO: What do we do with the extension parameter here?

        :returns: HTML of a script tag to insert into a page.
        """
        urls = [chunk["url"] for chunk in self.sorted_chunks()]
        tags = (
            self.plugin_data_tag()
            + self.frontend_message_tag()
            + [
                '<script>{kolibri_name}.registerKolibriModuleAsync("{bundle}", ["{urls}"]);</script>'.format(
                    kolibri_name="kolibriCoreAppGlobal",
                    bundle=self.unique_id,
                    urls='","'.join(urls),
                )
            ]
        )
        return mark_safe("\n".join(tags))

    class Meta:
        abstract = True


class WebpackInclusionHook(hooks.KolibriHook):
    """
    To define an asset target of inclusing in some html template, you must
    define an inheritor of ``WebpackBundleHook`` for the asset files themselves
    and then a ``WebpackInclusionHook`` to define where the inclusion takes
    place.

    This abstract hook does nothing, it's just the universal inclusion hook, and
    no templates intend to include ALL assets at once.
    """

    #: Should define an instance of ``WebpackBundleHook``, likely abstract
    bundle_class = None

    def __init__(self, *args, **kwargs):
        super(WebpackInclusionHook, self).__init__(*args, **kwargs)
        if not self._meta.abstract:
            assert (
                self.bundle_class is not None
            ), "Must specify bundle_class property, this one did not: {} ({})".format(
                type(self), type(self.bundle_class)
            )

    def render_to_page_load_sync_html(self):
        html = ""
        bundle = self.bundle_class()
        if not bundle._meta.abstract:
            html = bundle.render_to_page_load_sync_html()
        else:
            for hook in bundle.registered_hooks:
                html += hook.render_to_page_load_sync_html()
        return mark_safe(html)

    def render_to_page_load_async_html(self):
        html = ""
        bundle = self.bundle_class()
        if not bundle._meta.abstract:
            html = bundle.render_to_page_load_async_html()
        else:
            for hook in bundle.registered_hooks:
                html += hook.render_to_page_load_async_html()
        return mark_safe(html)

    class Meta:
        abstract = True


class FrontEndBaseSyncHook(WebpackInclusionHook):
    """
    Inherit a hook defining assets to be loaded in kolibri/base.html, that means
    ALL pages. Use with care.
    """

    class Meta:
        abstract = True


class FrontEndBaseASyncHook(WebpackInclusionHook):
    """
    Inherit a hook defining assets to be loaded in kolibri/base.html, that means
    ALL pages. Use with care.
    """

    class Meta:
        abstract = True
