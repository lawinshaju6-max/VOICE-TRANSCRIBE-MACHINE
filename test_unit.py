"""
Voice Scribe - Automated Unit Tests
Tests vector layout, font database, kerning, word-wrapping, and config loading.
"""

import unittest
import json
import os
from hershey_fonts import HERSHEY_SIMPLEX, get_glyph
from vector_compiler import VectorLayoutCompiler
from voice_scribe_engine import load_config


class TestHersheyFonts(unittest.TestCase):
    def test_uppercase_glyphs_exist(self):
        for code in range(ord('A'), ord('Z') + 1):
            char = chr(code)
            glyph = get_glyph(char)
            self.assertIsInstance(glyph, list)
            self.assertGreater(glyph[0], 0, f"Advance width for {char} must be > 0")

    def test_digit_glyphs_exist(self):
        for code in range(ord('0'), ord('9') + 1):
            char = chr(code)
            glyph = get_glyph(char)
            self.assertIsInstance(glyph, list)
            self.assertGreater(glyph[0], 0, f"Advance width for {char} must be > 0")

    def test_lowercase_glyphs_resolve(self):
        for code in range(ord('a'), ord('z') + 1):
            char = chr(code)
            glyph = get_glyph(char)
            self.assertIsInstance(glyph, list)
            self.assertGreater(glyph[0], 0, f"Advance width for {char} must be > 0")

    def test_punctuation_glyphs_exist(self):
        for punct in ['.', ',', '-', ':', ';', '?', '!', ' ']:
            glyph = get_glyph(punct)
            self.assertIsInstance(glyph, list)
            self.assertGreater(glyph[0], 0, f"Advance width for '{punct}' must be > 0")


class TestVectorCompiler(unittest.TestCase):
    def setUp(self):
        self.compiler = VectorLayoutCompiler(
            streamer=None,
            page_width=170.0,
            page_height=290.0,
            margin_left=15.0,
            start_y=270.0,
            line_spacing=9.5,
            font_scale=0.28,
        )

    def test_initial_coordinates(self):
        self.assertEqual(self.compiler.cursor_x, 15.0)
        self.assertEqual(self.compiler.cursor_y, 270.0)

    def test_newline_advancement(self):
        success = self.compiler.newline()
        self.assertTrue(success)
        self.assertEqual(self.compiler.cursor_x, 15.0)
        self.assertAlmostEqual(self.compiler.cursor_y, 270.0 - 9.5)

    def test_compute_word_width(self):
        width = self.compiler.compute_word_width("HELLO")
        self.assertGreater(width, 0.0)

    def test_dry_run_plot(self):
        # Dry-run plotting should execute without throwing exceptions
        self.compiler.plot_phrase("VOICE SCRIBE 2026!", dry_run=True)
        self.assertGreater(self.compiler.cursor_x, 15.0)

    def test_word_wrap(self):
        # A very long sentence must trigger a newline
        initial_y = self.compiler.cursor_y
        long_sentence = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG MULTIPLE TIMES ACROSS THE EXAMINATION PAPER"
        self.compiler.plot_phrase(long_sentence, dry_run=True)
        self.assertLess(self.compiler.cursor_y, initial_y, "Sentence should have caused at least one newline wrap")


class TestConfiguration(unittest.TestCase):
    def test_config_load(self):
        cfg = load_config()
        self.assertIn("serial", cfg)
        self.assertIn("motion", cfg)
        self.assertIn("geometry", cfg)
        self.assertIn("speech", cfg)
        self.assertEqual(cfg["serial"]["baud_rate"], 115200)
        self.assertEqual(cfg["motion"]["cmd_pen_up"], "M03 S90")
        self.assertEqual(cfg["motion"]["cmd_pen_down"], "M03 S0")


if __name__ == "__main__":
    unittest.main()
