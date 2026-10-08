extends Camera2D
# Follows the rocket (parent). Zoom comes from Settings.camera_zoom, so it survives level restarts;
# the mouse wheel changes it in flight.

const WHEEL_STEP := 1.15

func _ready() -> void:
	# Keep reacting to the wheel while the tree is paused between scripted steps.
	process_mode = Node.PROCESS_MODE_ALWAYS
	# Keep the space backdrop at its normal size (and covering the screen) at every zoom.
	var bg := get_tree().current_scene.get_node_or_null("ParallaxBackground")
	if bg != null:
		bg.follow_viewport_enabled = false
		bg.scroll_ignore_camera_zoom = true
		for layer in bg.get_children():
			if layer is ParallaxLayer:
				_tile_forever(layer)
	_apply()

static func _tile_forever(layer: ParallaxLayer) -> void:
	# Repeat the layer's sprite edge to edge in both directions: the mirroring interval must be the sprite's
	# exact on-layer size (some levels used a larger interval, which left gaps between copies).
	for child in layer.get_children():
		if child is Sprite2D and child.texture != null:
			layer.motion_mirroring = child.texture.get_size() * child.scale.abs()
			return

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			Settings.camera_zoom *= WHEEL_STEP
			_apply()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			Settings.camera_zoom /= WHEEL_STEP
			_apply()

func _apply() -> void:
	zoom = Vector2.ONE * Settings.camera_zoom
