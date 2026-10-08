class_name UITheme
extends RefCounted
# Shared look for the menu and the flight HUD: dark glass panels, cyan accents, chamfered corners, mono font.

const BG := Color(0.02, 0.05, 0.09, 0.78)
const BG_SOLID := Color(0.02, 0.05, 0.09, 0.92)
const ACCENT := Color(0.25, 0.95, 1.0)
const ACCENT_DIM := Color(0.25, 0.95, 1.0, 0.35)
const TEXT := Color(0.85, 0.97, 1.0)
const TEXT_DIM := Color(0.55, 0.72, 0.8)
const OK := Color(0.35, 1.0, 0.6)
const WARN := Color(1.0, 0.75, 0.2)
const DANGER := Color(1.0, 0.3, 0.35)

static var _font: Font = null

static func font() -> Font:
	if _font == null:
		var f := SystemFont.new()
		f.font_names = PackedStringArray(["JetBrains Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Monospace"])
		f.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
		_font = f
	return _font

static func panel_style(bg: Color = BG, border: Color = ACCENT_DIM) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(1)
	# corner_detail = 1 turns rounded corners into 45° chamfers
	s.set_corner_radius_all(8)
	s.corner_detail = 1
	s.content_margin_left = 10
	s.content_margin_right = 10
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s

static func build() -> Theme:
	var t := Theme.new()
	t.default_font = font()
	t.default_font_size = 12

	t.set_color("font_color", "Label", TEXT)

	var normal := panel_style(Color(0.03, 0.09, 0.14, 0.85), ACCENT_DIM)
	var hover := panel_style(Color(0.05, 0.2, 0.28, 0.95), ACCENT)
	var pressed := panel_style(Color(0.1, 0.35, 0.45, 1.0), ACCENT)
	var focus := panel_style(Color(0, 0, 0, 0), ACCENT)
	focus.draw_center = false
	for b in ["Button", "CheckButton"]:
		t.set_stylebox("normal", b, normal)
		t.set_stylebox("hover", b, hover)
		t.set_stylebox("pressed", b, pressed)
		t.set_stylebox("hover_pressed", b, pressed)
		t.set_stylebox("focus", b, focus)
		t.set_color("font_color", b, TEXT)
		t.set_color("font_hover_color", b, ACCENT)
		t.set_color("font_pressed_color", b, Color.WHITE)
		t.set_color("font_focus_color", b, TEXT)
	t.set_stylebox("panel", "PanelContainer", panel_style())

	var edit := panel_style(Color(0.0, 0.03, 0.06, 0.95), ACCENT_DIM)
	t.set_stylebox("normal", "LineEdit", edit)
	t.set_stylebox("focus", "LineEdit", panel_style(Color(0.0, 0.03, 0.06, 0.95), ACCENT))
	t.set_color("font_color", "LineEdit", ACCENT)
	t.set_color("caret_color", "LineEdit", ACCENT)
	return t

static func label(text: String, size: int = 12, color: Color = TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l
