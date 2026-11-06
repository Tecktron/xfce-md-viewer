"""Choice of GTK's renderer (GSK_RENDERER). Free of GTK so it can be unit-tested."""

from __future__ import annotations

from collections.abc import MutableMapping

# GTK 4.19 renamed the OpenGL renderer from "ngl" to "gl" ("gl" used to name the
# old, since removed, renderer; "ngl" still works but logs a warning).
GL_RENAMED_IN = (4, 19)


def prefer_gl_renderer(environ: MutableMapping[str, str], gtk_version: tuple[int, int]) -> None:
    """Make GTK use its OpenGL renderer unless the user chose a renderer.

    Without hardware OpenGL (e.g. a VM without 3D acceleration) GTK 4.22 picked
    Vulkan, which there means Mesa's software driver lavapipe; it segfaulted in
    libvulkan_lvp.so (Ubuntu 26.04, Mesa 26.0). Software OpenGL (llvmpipe) is
    stable, and a document viewer gains nothing from Vulkan.

    Must run before the first window is created: GTK reads GSK_RENDERER when it
    creates the first renderer.
    """
    if "GSK_RENDERER" not in environ:
        environ["GSK_RENDERER"] = "gl" if gtk_version >= GL_RENAMED_IN else "ngl"
