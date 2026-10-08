extends Node2D
# Orientation ring around the rocket: the segments facing the landing pad light up (straight-line direction
# from the rocket to the pad centre). The whole ring turns green while the rocket is above the pad.

const SEGMENTS := 48
const RADIUS := 95.0
const GAP := 0.25            # fraction of each segment left dark
const BASE := Color(0.25, 0.95, 1.0, 0.12)
const LIT := Color(0.25, 0.95, 1.0)
const ON_PAD := Color(0.35, 1.0, 0.6)

# Child of the Rocket so it moves in the same frame as the rocket sprite; its own rotation cancels the
# rocket's so the ring stays aligned with the world.
@onready var rocket: RigidBody2D = get_parent()
@onready var pad: Node2D = rocket.get_parent().get_node_or_null("LandingPad")
@onready var camera: Camera2D = rocket.get_node("Camera2D")

var centre_offset := Vector2(0, -40)   # sprite centre in rocket space (same offset as the rocket sprite)

func _ready() -> void:
	if pad == null or DisplayServer.get_name() == "headless":
		visible = false
		set_process(false)
		return
	z_index = 5

func _physics_process(_delta: float) -> void:
	position = centre_offset
	rotation = -rocket.rotation

func _process(_delta: float) -> void:
	# Same size on screen at every zoom level
	scale = Vector2.ONE / camera.zoom.x
	queue_redraw()

func _draw() -> void:
	var to_pad: Vector2 = pad.global_position - rocket.global_position
	var heading := to_pad.angle()
	var on_pad: bool = pad.contains(rocket.position)
	var step := TAU / SEGMENTS
	for i in SEGMENTS:
		var a0 := i * step
		var a1 := a0 + step * (1.0 - GAP)
		var mid := (a0 + a1) / 2.0
		var color := BASE
		var width := 3.0
		if on_pad:
			color = Color(ON_PAD, 0.85)
			width = 5.0
		else:
			# Brightness falls off with the angle between the segment and the pad direction.
			var k := pow(maxf(0.0, cos(angle_difference(mid, heading))), 8.0)
			color = BASE.lerp(LIT, k)
			width = lerpf(3.0, 9.0, k)
		draw_arc(Vector2.ZERO, RADIUS, a0, a1, 4, color, width, true)
	if not on_pad:
		# Chevron just outside the ring, pointing at the pad.
		var d := Vector2.from_angle(heading)
		var n := d.orthogonal()
		var tip := d * (RADIUS + 22.0)
		var back := d * (RADIUS + 10.0)
		draw_colored_polygon(PackedVector2Array([tip, back + n * 8.0, back - n * 8.0]), LIT)
