import simpletransform

from .units import get_viewbox_transform


def apply_transforms(path, node):
    transform = get_node_transform(node)

    # apply the combined transform to this node's path
    simpletransform.applyTransformToPath(transform, path)

    return path


def get_node_transform(node):
    # start with the identity transform
    transform = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

    # this if is because sometimes inkscape likes to create paths outside of a layer?!
    if node.getparent() is not None:
        # combine this node's transform with all parent groups' transforms
        transform = simpletransform.composeParents(node, transform)

    # add in the transform implied by the viewBox
    viewbox_transform = get_viewbox_transform(node.getroottree().getroot())
    transform = simpletransform.composeTransform(viewbox_transform, transform)

    return transform


def get_correction_transform(node, child=False):
    """Get a transform to apply to new siblings or children of this SVG node"""

    # if we want to place our new nodes in the same group/layer as this node,
    # then we'll need to factor in the effects of any transforms set on
    # the parents of this node.

    if child:
        transform = get_node_transform(node)
    else:
        # we can ignore the transform on the node itself since it won't apply
        # to the objects we add
        transform = get_node_transform(node.getparent())

    # now invert it, so that we can position our objects in absolute
    # coordinates
    transform = simpletransform.invertTransform(transform)

    return simpletransform.formatTransform(transform)


def line_strings_to_csp(line_strings):
    csp = []

    for ls in line_strings:
        subpath = []
        for point in ls.coords:
            # create a straight line as a degenerate bezier
            subpath.append((point, point, point))
        csp.append(subpath)

    return csp
