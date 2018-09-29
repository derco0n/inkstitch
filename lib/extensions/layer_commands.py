import inkex

from .commands import CommandsExtension
from ..commands import LAYER_COMMANDS, get_command_description
from ..i18n import _
from ..svg.tags import SVG_USE_TAG, INKSCAPE_LABEL, XLINK_HREF
from ..svg import get_correction_transform


class LayerCommands(CommandsExtension):
    COMMANDS = LAYER_COMMANDS

    def ensure_current_layer(self):
        # if no layer is selected, inkex defaults to the root, which isn't
        # particularly useful
        if self.current_layer is self.document.getroot():
            try:
                self.current_layer = self.document.xpath(".//svg:g[@inkscape:groupmode='layer']", namespaces=inkex.NSS)[0]
            except IndexError:
                # No layers at all??  Fine, we'll stick with the default.
                pass

    def effect(self):
        commands = [command for command in self.COMMANDS if getattr(self.options, command)]

        if not commands:
            inkex.errormsg(_("Please choose one or more commands to add."))
            return

        self.ensure_current_layer()
        correction_transform = get_correction_transform(self.current_layer, child=True)

        for i, command in enumerate(commands):
            self.ensure_symbol(command)

            inkex.etree.SubElement(self.current_layer, SVG_USE_TAG,
                                   {
                                       "id": self.uniqueId("use"),
                                       INKSCAPE_LABEL: _("Ink/Stitch Command") + ": %s" % get_command_description(command),
                                       XLINK_HREF: "#inkstitch_%s" % command,
                                       "height": "100%",
                                       "width": "100%",
                                       "x": str(i * 20),
                                       "y": "-10",
                                       "transform": correction_transform
                                   })
