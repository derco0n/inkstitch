import inkex
import re
import json
from copy import deepcopy
from collections import MutableMapping
from stringcase import snakecase

from ..svg.tags import SVG_GROUP_TAG, INKSCAPE_GROUPMODE, SVG_DEFS_TAG, EMBROIDERABLE_TAGS, SVG_POLYLINE_TAG
from ..elements import AutoFill, Fill, Stroke, SatinColumn, Polyline, EmbroideryElement
from ..commands import is_command, layer_commands
from ..i18n import _


SVG_METADATA_TAG = inkex.addNS("metadata", "svg")


def strip_namespace(tag):
    """Remove xml namespace from a tag name.

    >>> {http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}namedview
    <<< namedview
    """

    match = re.match('^\{[^}]+\}(.+)$', tag)

    if match:
        return match.group(1)
    else:
        return tag


class InkStitchMetadata(MutableMapping):
    """Helper class to get and set inkstitch-specific metadata attributes.

    Operates on a document and acts like a dict.  Setting an item adds or
    updates a metadata element in the document.  Getting an item retrieves
    a metadata element's text contents or None if an element by that name
    doesn't exist.
    """

    def __init__(self, document):
        self.document = document
        self.metadata = self._get_or_create_metadata()

    def _get_or_create_metadata(self):
        metadata = self.document.find(SVG_METADATA_TAG)

        if metadata is None:
            metadata = inkex.etree.SubElement(self.document.getroot(), SVG_METADATA_TAG)

            # move it so that it goes right after the first element, sodipodi:namedview
            self.document.getroot().remove(metadata)
            self.document.getroot().insert(1, metadata)

        return metadata

    # Because this class inherints from MutableMapping, all we have to do is
    # implement these five methods and we get a full dict-like interface.

    def __setitem__(self, name, value):
        item = self._find_item(name)
        item.text = json.dumps(value)

    def _find_item(self, name, create=True):
        tag = inkex.addNS(name, "inkstitch")
        item = self.metadata.find(tag)
        if item is None and create:
            item = inkex.etree.SubElement(self.metadata, tag)

        return item

    def __getitem__(self, name):
        item = self._find_item(name)

        try:
            return json.loads(item.text)
        except (ValueError, TypeError):
            return None

    def __delitem__(self, name):
        item = self._find_item(name, create=False)

        if item is not None:
            self.metadata.remove(item)

    def __iter__(self):
        for child in self.metadata:
            if child.prefix == "inkstitch":
                yield strip_namespace(child.tag)

    def __len__(self):
        i = 0
        for i, item in enumerate(self):
            pass

        return i + 1


class InkstitchExtension(inkex.Effect):
    """Base class for Inkstitch extensions.  Not intended for direct use."""

    @classmethod
    def name(cls):
        return snakecase(cls.__name__)

    def hide_all_layers(self):
        for g in self.document.getroot().findall(SVG_GROUP_TAG):
            if g.get(INKSCAPE_GROUPMODE) == "layer":
                g.set("style", "display:none")

    def no_elements_error(self):
        if self.selected:
            inkex.errormsg(_("No embroiderable paths selected."))
        else:
            inkex.errormsg(_("No embroiderable paths found in document."))
        inkex.errormsg(_("Tip: use Path -> Object to Path to convert non-paths."))

    def descendants(self, node, selected=False):
        nodes = []
        element = EmbroideryElement(node)

        if element.has_command('ignore_object'):
            return []

        if node.tag == SVG_GROUP_TAG and node.get(INKSCAPE_GROUPMODE) == "layer":
            if len(list(layer_commands(node, "ignore_layer"))):
                return []

        if element.has_style('display') and element.get_style('display') is None:
            return []

        if node.tag == SVG_DEFS_TAG:
            return []

        if self.selected:
            if node.get("id") in self.selected:
                selected = True
        else:
            # if the user didn't select anything that means we process everything
            selected = True

        for child in node:
            nodes.extend(self.descendants(child, selected))

        if selected and node.tag in EMBROIDERABLE_TAGS:
            nodes.append(node)

        return nodes

    def get_nodes(self):
        return self.descendants(self.document.getroot())

    def detect_classes(self, node):
        if node.tag == SVG_POLYLINE_TAG:
            return [Polyline]
        else:
            element = EmbroideryElement(node)

            if element.get_boolean_param("satin_column"):
                return [SatinColumn]
            else:
                classes = []

                if element.get_style("fill", "black"):
                    if element.get_boolean_param("auto_fill", True):
                        classes.append(AutoFill)
                    else:
                        classes.append(Fill)

                if element.get_style("stroke"):
                    if not is_command(element.node):
                        classes.append(Stroke)

                if element.get_boolean_param("stroke_first", False):
                    classes.reverse()

                return classes

    def get_elements(self):
        self.elements = []
        for node in self.get_nodes():
            classes = self.detect_classes(node)
            self.elements.extend(cls(node) for cls in classes)

        if self.elements:
            return True
        else:
            self.no_elements_error()
            return False

    def elements_to_patches(self, elements):
        patches = []
        for element in elements:
            if patches:
                last_patch = patches[-1]
            else:
                last_patch = None

            patches.extend(element.embroider(last_patch))

        return patches

    def get_inkstitch_metadata(self):
        return InkStitchMetadata(self.document)

    def get_base_file_name(self):
        svg_filename = self.document.getroot().get(inkex.addNS('docname', 'sodipodi'), "embroidery.svg")

        if svg_filename.endswith('.svg'):
            svg_filename = svg_filename[:-4]

        return svg_filename

    def uniqueId(self, prefix, make_new_id=True):
        """Override inkex.Effect.uniqueId with a nicer naming scheme."""
        i = 1
        while True:
            new_id = "%s%d" % (prefix, i)
            if new_id not in self.doc_ids:
                break
            i += 1
        self.doc_ids[new_id] = 1

        return new_id

    def parse(self):
        """Override inkex.Effect.parse to add Ink/Stitch xml namespace"""

        # SVG parsers don't actually look for anything at this URL.  They just
        # care that it's unique.  That defines a "namespace" of element and
        # attribute names to disambiguate conflicts with element and
        # attribute names other XML namespaces.
        #
        # Updating inkex.NSS here allows us to pass 'inkstitch' into
        # inkex.addNS().
        inkex.NSS['inkstitch'] = 'http://inkstitch.org/namespace'

        # call the superclass's method first
        inkex.Effect.parse(self)

        # This is the only way I could find to add a namespace to an existing
        # element tree at the top without getting ugly prefixes like "ns0".
        inkex.etree.cleanup_namespaces(self.document,
                                       top_nsmap=inkex.NSS,
                                       keep_ns_prefixes=inkex.NSS.keys())
        self.original_document = deepcopy(self.document)
