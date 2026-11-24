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
    def test_a_little_bigger_than_the_desktop(self):
        self.assertAlmostEqual(look.text_points(10), 12)                  # 20 % for reading
        self.assertAlmostEqual(look.text_points(None), look.DEFAULT_PT * look.READING_BOOST)
        self.assertEqual(look.text_points(10, boost=1.0), 10)

    def test_readable_range(self):
        self.assertEqual(look.text_points(6, boost=1.0), look.MIN_PT)     # never tiny
        self.assertEqual(look.text_points(40), look.MAX_PT)               # never gigantic

    def test_large_text_settings_are_honoured(self):
        # Text scaling 2.0 on 10 pt, with the boost: 24 pt (it was cut to 18 before).
        self.assertAlmostEqual(look.text_points(10, 1.5), 18)
        self.assertAlmostEqual(look.text_points(10, 2.0), 24)

    def test_windows_text_size_setting(self):
        self.assertEqual(look.windows_text_scale(lambda: 150), 1.5)
        self.assertEqual(look.windows_text_scale(lambda: 100), 1.0)
        self.assertEqual(look.windows_text_scale(lambda: 900), 2.25)       # Windows' maximum
        self.assertEqual(look.windows_text_scale(lambda: 1 / 0), 1.0)     # not set: no change

    def test_windows_text_size_is_applied_once(self):
        # Windows may or may not have enlarged its interface font for "Text size" already.
        self.assertEqual(look.windows_points(9, 1.5), 13.5)               # not yet: apply it
        self.assertEqual(look.windows_points(13.5, 1.5), 13.5)            # already: keep it
        self.assertEqual(look.windows_points(12, 1.0), 12)                # a bigger font chosen
        self.assertEqual(look.windows_points(None, 1.0), look.WINDOWS_DEFAULT_PT)

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
