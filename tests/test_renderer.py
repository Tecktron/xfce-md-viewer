from md_viewer.renderer import prefer_gl_renderer


def test_old_gtk_uses_ngl():
    env = {}
    prefer_gl_renderer(env, (4, 14))  # Ubuntu 24.04
    assert env["GSK_RENDERER"] == "ngl"


def test_renamed_gtk_uses_gl():
    for version in ((4, 19), (4, 22)):
        env = {}
        prefer_gl_renderer(env, version)
        assert env["GSK_RENDERER"] == "gl"


def test_user_choice_is_kept():
    env = {"GSK_RENDERER": "vulkan"}
    prefer_gl_renderer(env, (4, 22))
    assert env["GSK_RENDERER"] == "vulkan"
