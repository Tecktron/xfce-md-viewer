"""Back/forward history."""

from md_viewer.history import History


def test_empty():
    h = History()
    assert h.current is None
    assert not h.can_go_back()
    assert not h.can_go_forward()
    assert h.back() is None
    assert h.forward() is None


def test_back_and_forward():
    h = History()
    for uri in ("a", "b", "c"):
        h.visit(uri)
    assert h.back() == "b"
    assert h.back() == "a"
    assert h.back() is None
    assert h.current == "a"
    assert h.forward() == "b"
    assert h.forward() == "c"
    assert h.forward() is None


def test_visit_truncates_forward_entries():
    h = History()
    for uri in ("a", "b", "c"):
        h.visit(uri)
    h.back()
    h.back()
    h.visit("d")
    assert h.current == "d"
    assert not h.can_go_forward()
    assert h.back() == "a"


def test_revisiting_current_is_a_no_op():
    h = History()
    h.visit("a")
    h.visit("a")
    assert not h.can_go_back()
