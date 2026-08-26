from __future__ import annotations

import inspect
import unittest

from src.platform.display_project_config import DisplayProjectConfigWindow


class _FakeCanvas:
    def __init__(self) -> None:
        self.calls = []

    def yview_scroll(self, units, mode) -> None:
        self.calls.append((units, mode))


class _Widget:
    def __init__(self, master=None) -> None:
        self.master = master


class _Event:
    def __init__(self, widget, delta=0, num=None) -> None:
        self.widget = widget
        self.delta = delta
        self.num = num


class DisplayProjectConfigScrollTests(unittest.TestCase):
    def test_painel_direito_usa_canvas_e_scrollbar_vertical(self):
        source = inspect.getsource(DisplayProjectConfigWindow.__init__)
        self.assertIn("right_scrollbar = tk.Scrollbar", source)
        self.assertIn("right_canvas = tk.Canvas", source)
        self.assertIn("yscrollcommand=right_scrollbar.set", source)
        self.assertIn("right_canvas.create_window", source)
        self.assertIn("scrollregion=right_canvas.bbox", source)

    def test_roda_do_mouse_rola_apenas_conteudo_do_painel_direito(self):
        window = DisplayProjectConfigWindow.__new__(DisplayProjectConfigWindow)
        canvas = _FakeCanvas()
        content = _Widget()
        child = _Widget(content)
        outside = _Widget()
        window._project_scroll_canvas = canvas
        window._project_scroll_content = content

        result = window._scroll_project_content(_Event(child, delta=-120))
        self.assertEqual("break", result)
        self.assertEqual([(1, "units")], canvas.calls)

        result = window._scroll_project_content(_Event(outside, delta=-120))
        self.assertIsNone(result)
        self.assertEqual([(1, "units")], canvas.calls)

    def test_linux_button_4_e_5_tambem_sao_suportados(self):
        window = DisplayProjectConfigWindow.__new__(DisplayProjectConfigWindow)
        canvas = _FakeCanvas()
        content = _Widget()
        child = _Widget(content)
        window._project_scroll_canvas = canvas
        window._project_scroll_content = content

        window._scroll_project_content(_Event(child, num=4))
        window._scroll_project_content(_Event(child, num=5))
        self.assertEqual([(-3, "units"), (3, "units")], canvas.calls)


if __name__ == "__main__":
    unittest.main()
