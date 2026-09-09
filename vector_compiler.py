"""
Voice Scribe - Vector Layout & Trajectory Compiler Module
Transforms text phrases into single-stroke Hershey vector toolpaths,
managing dynamic word-wrapping, margins, kerning, and line feeds.
"""

import re
from typing import Optional
from hershey_fonts import get_glyph, HERSHEY_SIMPLEX


class VectorLayoutCompiler:
    """Computes layout geometry and translates text into synchronized G-code trajectories."""

    def __init__(
        self,
        streamer=None,
        page_width: float = 170.0,
        page_height: float = 290.0,
        margin_left: float = 15.0,
        start_y: float = 270.0,
        line_spacing: float = 9.5,
        font_scale: float = 0.28,
        min_y_limit: float = 15.0,
    ):
        self.streamer = streamer
        self.page_width = page_width
        self.page_height = page_height
        self.margin_left = margin_left
        self.start_y = start_y
        self.line_spacing = line_spacing
        self.font_scale = font_scale
        self.min_y_limit = min_y_limit

        self.cursor_x = self.margin_left
        self.cursor_y = self.start_y

    def reset_origin(self):
        """Re-initializes carriage position to the top-left writing baseline."""
        self.cursor_x = self.margin_left
        self.cursor_y = self.start_y
        if self.streamer:
            self.streamer.pen_up()
            self.streamer.rapid_move(self.cursor_x, self.cursor_y)
        print(f"[*] Carriage initialized to Top-Left Margin Home: ({self.cursor_x:.2f}, {self.cursor_y:.2f})")

    def newline(self) -> bool:
        """
        Advances the carriage to the next ruled line.
        Returns False if the bottom page boundary has been reached.
        """
        self.cursor_x = self.margin_left
        self.cursor_y -= self.line_spacing

        if self.cursor_y < self.min_y_limit:
            print(f"[!] BOUNDARY REACHED: Bottom of sheet limit ({self.min_y_limit} mm) hit. Please insert new paper.")
            return False

        print(f"[*] Advanced to new line: X={self.cursor_x:.2f}, Y={self.cursor_y:.2f}")
        if self.streamer:
            self.streamer.pen_up()
            self.streamer.rapid_move(self.cursor_x, self.cursor_y)
        return True

    def compute_word_width(self, word: str) -> float:
        """Calculates total physical millimeter width for a given word."""
        width = 0.0
        for char in word:
            glyph = get_glyph(char)
            advance_units = glyph[0]
            width += (advance_units * self.font_scale) + (1.5 * self.font_scale)
        return width

    def plot_phrase(self, phrase: str, dry_run: bool = False):
        """
        Compiles and plots a text phrase using single-stroke vector trajectories.
        Handles auto word-wrap against right page boundary.
        """
        # Filter supported characters
        clean = re.sub(r'[^A-Za-z0-9 .,!?:;+\-=\'\"/()]', '', phrase)
        words = clean.split()

        space_advance = HERSHEY_SIMPLEX[' '][0] * self.font_scale
        right_boundary = self.page_width - self.margin_left

        for word in words:
            word_width = self.compute_word_width(word)

            # Auto word-wrap boundary protection
            if (self.cursor_x + word_width) > right_boundary:
                can_advance = self.newline()
                if not can_advance:
                    print(f"[!] Skipping remaining text due to page boundary: '{word}'")
                    break

            for char in word:
                glyph = get_glyph(char)
                char_advance = glyph[0] * self.font_scale
                strokes = glyph[1]

                for stroke in strokes:
                    if not stroke:
                        continue

                    # Step 1: Rapid move to stroke origin with Pen UP
                    start_px = self.cursor_x + (stroke[0][0] * self.font_scale)
                    start_py = self.cursor_y + (stroke[0][1] * self.font_scale)

                    if self.streamer and not dry_run:
                        self.streamer.rapid_move(start_px, start_py)
                        # Step 2: Drop pen onto paper
                        self.streamer.pen_down()
                    elif dry_run:
                        pass

                    # Step 3: Draw continuous linear vector segments
                    for pt in stroke[1:]:
                        px = self.cursor_x + (pt[0] * self.font_scale)
                        py = self.cursor_y + (pt[1] * self.font_scale)
                        if self.streamer and not dry_run:
                            self.streamer.linear_draw(px, py)

                    # Step 4: Retract pen before next stroke or character
                    if self.streamer and not dry_run:
                        self.streamer.pen_up()

                # Character pitch advance
                self.cursor_x += char_advance + (1.5 * self.font_scale)

            # Advance space between words
            self.cursor_x += space_advance
