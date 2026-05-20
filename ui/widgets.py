"""Premium Pygame widgets for the dashboard sidebar."""

from __future__ import annotations

import pygame

from core.constants import COLORS

pygame.font.init()
FONT_SM = pygame.font.SysFont("segoeui", 16)
FONT_MD = pygame.font.SysFont("segoeui", 20, bold=True)
FONT_LG = pygame.font.SysFont("segoeui", 30, bold=True)


# --------------------------------------------------------------------------- Button
class Button:
    def __init__(self, x, y, w, h, text, callback, accent=False):
        self.rect     = pygame.Rect(x, y, w, h)
        self.text     = text
        self.callback = callback
        self.hovered  = False
        self.active   = True
        self.accent   = accent   # accent=True → uses accent colour

    def draw(self, surface: pygame.Surface):
        if not self.active:
            bg     = (38, 42, 48)
            border = (55, 60, 68)
            fg     = COLORS["text_dim"]
        elif self.accent:
            bg     = (28, 155, 145) if not self.hovered else (35, 185, 172)
            border = (48, 196, 181)
            fg     = (255, 255, 255)
        else:
            bg     = (48, 54, 62) if not self.hovered else (62, 70, 80)
            border = (72, 80, 92)
            fg     = COLORS["text"]

        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=8)

        # Subtle top-edge highlight for 3-D effect
        if self.active:
            hi_rect = pygame.Rect(self.rect.x + 2, self.rect.y + 1, self.rect.w - 4, 1)
            pygame.draw.rect(surface, (255, 255, 255, 30), hi_rect)

        txt = FONT_MD.render(self.text, True, fg)
        surface.blit(txt, (
            self.rect.centerx - txt.get_width() // 2,
            self.rect.centery - txt.get_height() // 2,
        ))

    def handle_event(self, event) -> bool:
        if not self.active:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
                return True
        return False


# --------------------------------------------------------------------------- Dropdown
class Dropdown:
    def __init__(self, x, y, w, h, options, callback=None):
        self.rect         = pygame.Rect(x, y, w, h)
        self.options      = options
        self.selected_idx = 0
        self.callback     = callback
        self.open         = False

    @property
    def selected(self):
        return self.options[self.selected_idx]

    def draw(self, surface: pygame.Surface):
        # Main box
        bg     = (48, 54, 62) if not self.open else (38, 44, 52)
        border = COLORS["accent"] if self.open else (72, 80, 92)
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=6)

        txt = FONT_SM.render(self.selected, True, COLORS["text"])
        surface.blit(txt, (self.rect.x + 12, self.rect.centery - txt.get_height() // 2))

        arrow = "▲" if self.open else "▼"
        a_surf = FONT_SM.render(arrow, True, COLORS["text_dim"])
        surface.blit(a_surf, (self.rect.right - 22, self.rect.centery - a_surf.get_height() // 2))

        if not self.open:
            return

        # Drop-down list
        for i, opt in enumerate(self.options):
            opt_rect = pygame.Rect(
                self.rect.x, self.rect.bottom + i * (self.rect.h - 2),
                self.rect.w, self.rect.h - 2,
            )
            hov = opt_rect.collidepoint(pygame.mouse.get_pos())
            row_bg = (58, 120, 110) if hov else (32, 36, 42)
            pygame.draw.rect(surface, row_bg, opt_rect)
            pygame.draw.rect(surface, (55, 62, 72), opt_rect, width=1)
            sel_marker = "▸ " if i == self.selected_idx else "  "
            o_surf = FONT_SM.render(sel_marker + opt, True, COLORS["text"])
            surface.blit(o_surf, (opt_rect.x + 10, opt_rect.centery - o_surf.get_height() // 2))

    def handle_event(self, event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.rect.collidepoint(event.pos):
            self.open = not self.open
            return True
        if not self.open:
            return False
        for i in range(len(self.options)):
            opt_rect = pygame.Rect(
                self.rect.x, self.rect.bottom + i * (self.rect.h - 2),
                self.rect.w, self.rect.h - 2,
            )
            if opt_rect.collidepoint(event.pos):
                self.selected_idx = i
                self.open = False
                if self.callback:
                    self.callback(self.selected)
                return True
        self.open = False
        return False


# --------------------------------------------------------------------------- Checkbox
class Checkbox:
    def __init__(self, x, y, text, checked=False, callback=None):
        self.box      = pygame.Rect(x, y, 20, 20)
        self.text     = text
        self.checked  = checked
        self.callback = callback

    def draw(self, surface: pygame.Surface):
        bg = COLORS["accent"] if self.checked else (42, 48, 56)
        pygame.draw.rect(surface, bg, self.box, border_radius=4)
        pygame.draw.rect(surface, (72, 80, 92), self.box, width=1, border_radius=4)
        if self.checked:
            # Checkmark
            pygame.draw.line(surface, (255, 255, 255),
                             (self.box.x + 4, self.box.centery),
                             (self.box.centerx - 1, self.box.bottom - 4), 2)
            pygame.draw.line(surface, (255, 255, 255),
                             (self.box.centerx - 1, self.box.bottom - 4),
                             (self.box.right - 4, self.box.top + 4), 2)
        txt = FONT_SM.render(self.text, True, COLORS["text"])
        surface.blit(txt, (self.box.right + 10, self.box.centery - txt.get_height() // 2))

    def handle_event(self, event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        txt   = FONT_SM.render(self.text, True, COLORS["text"])
        full  = pygame.Rect(self.box.x, self.box.y,
                            self.box.w + 10 + txt.get_width(),
                            max(self.box.h, txt.get_height()))
        if full.collidepoint(event.pos):
            self.checked = not self.checked
            if self.callback:
                self.callback(self.checked)
            return True
        return False
