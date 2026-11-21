import unittest

from ft_assistant import look


class DesktopFont(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(look.parse_font_name("'Ubuntu 10'"), ("Ubuntu", 10.0))
        self.assertEqual(look.parse_font_name("Noto Sans Bold 11"), ("Noto Sans", 11.0))
        self.assertEqual(look.parse_font_name("Cantarell 11.5"), ("Cantarell", 11.5))
        self.assertEqual(look.parse_font_name("Noto Sans,10,-1,5,50,0,0,0,0,0"), ("Noto Sans", 10.0))
        self.assertEqual(look.parse_font_name(""), (None, None))
        self.assertEqual(look.parse_font_name("Sans"), ("Sans", None))

    def fake(self, answers):
        return lambda cmd: answers.get(" ".join(cmd))

    def test_cinnamon_with_text_scaling(self):
        run = self.fake({
            "gsettings get org.cinnamon.desktop.interface font-name": "'Ubuntu 10'",
            "gsettings get org.cinnamon.desktop.interface text-scaling-factor": "1.25",
            "gsettings get org.gnome.desktop.interface font-name": "'Cantarell 11'",
        })
        self.assertEqual(look.linux_desktop_font(run, {"XDG_CURRENT_DESKTOP": "X-Cinnamon"}),
                         ("Ubuntu", 10.0, 1.25))

    def test_gnome_desktop_reads_gnome_settings(self):
        run = self.fake({
            "gsettings get org.cinnamon.desktop.interface font-name": "'Ubuntu 10'",
            "gsettings get org.gnome.desktop.interface font-name": "'Cantarell 11'",
        })
        self.assertEqual(look.linux_desktop_font(run, {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}),
                         ("Cantarell", 11.0, 1.0))

    def test_kde_and_xfce(self):
        kde = self.fake({"kreadconfig5 --file kdeglobals --group General --key font":
                         "Noto Sans,10,-1,5,50,0,0,0,0,0"})
        self.assertEqual(look.linux_desktop_font(kde, {"XDG_CURRENT_DESKTOP": "KDE"}),
                         ("Noto Sans", 10.0, 1.0))
        xfce = self.fake({"xfconf-query -c xsettings -p /Gtk/FontName": "Sans 9"})
        self.assertEqual(look.linux_desktop_font(xfce, {"XDG_CURRENT_DESKTOP": "XFCE"}),
                         ("Sans", 9.0, 1.0))

    def test_nothing_found(self):
        self.assertEqual(look.linux_desktop_font(lambda cmd: None, {}), (None, None, 1.0))

    def test_xft_dpi(self):
        self.assertEqual(look.xft_dpi(lambda cmd: "Xft.antialias:\t1\nXft.dpi:\t144\n"), 144.0)
        self.assertIsNone(look.xft_dpi(lambda cmd: None))


class Sizes(unittest.TestCase):
    def test_readable_range(self):
        self.assertEqual(look.text_points(10), 10)
        self.assertEqual(look.text_points(None), look.DEFAULT_PT)
        self.assertEqual(look.text_points(6), look.MIN_PT)             # never tiny
        self.assertEqual(look.text_points(30), look.MAX_PT)            # never gigantic
        self.assertEqual(look.text_points(10, 1.5), 15)                # accessibility scaling

    def test_headings_are_bigger(self):
        body, head, title = look.sizes(13)
        self.assertEqual(body, -13)
        self.assertLess(head, body)          # negative = pixels: more negative is bigger
        self.assertLess(title, head)

    def test_shrinking_never_below_nine_points(self):
        px_per_pt = 96 / 72
        self.assertAlmostEqual(look.shrink_floor(13, px_per_pt), 12.0)     # 9 pt
        self.assertAlmostEqual(look.shrink_floor(24, px_per_pt), 24 * look.FIT_SHRINK)


if __name__ == "__main__":
    unittest.main()
