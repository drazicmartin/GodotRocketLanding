# Opt-in protocol. Legacy clients and interactive play keep their original path.
extends Node

const PROTOCOL = 1
const LEVELS = ["level_1", "level_2", "level_3", "level_4",
	"random_level_easy", "random_level_moderate", "random_level_hard"]
var enabled = "--world-model" in OS.get_cmdline_user_args()
var busy = false
var client_id = 0
var episode = null
var outcome = ""
var image_size = 128
var step_index = 0

func _ready():
	if not enabled:
		return
	process_mode = Node.PROCESS_MODE_ALWAYS
	Settings.control_mode = "script"
	Engine.physics_ticks_per_second = 30
	Engine.max_physics_steps_per_frame = 1
	Engine.physics_jitter_fix = 0.0
	Engine.max_fps = 60
	get_tree().paused = true
	var args = OS.get_cmdline_user_args()
	var port = 65000
	if "--wm-port" in args:
		port = int(args[args.find("--wm-port") + 1])
	if WebSocketServer.listen(port, "127.0.0.1") != OK:
		push_error("World model port is unavailable: %s" % port)
		get_tree().quit(2)
	WebSocketServer.message_received.connect(_on_message)
	WebSocketServer.client_disconnected.connect(_on_disconnect)

func _on_disconnect(peer_id):
	if peer_id == client_id:
		get_tree().quit()

func _reply(peer_id, request_id, data):
	data["protocol"] = PROTOCOL
	data["id"] = request_id
	if WebSocketServer.peers.has(peer_id):
		WebSocketServer.send(peer_id, JSON.stringify(data))

func _on_message(peer_id, message):
	var data = JSON.parse_string(message)
	if not data is Dictionary:
		_reply(peer_id, null, {"error": "Expected a JSON object"})
		return
	var request_id = data.get("id")
	if client_id != 0 and client_id != peer_id:
		_reply(peer_id, request_id, {"error": "One client per simulator"})
		return
	client_id = peer_id
	if busy:
		_reply(peer_id, request_id, {"error": "Previous request is still running"})
		return
	var command = data.get("command", "")
	if command == "hello":
		_reply(peer_id, request_id, {"rendering": DisplayServer.get_name() != "headless",
			"pid": OS.get_process_id(), "physics_fps": 30, "engine": Engine.get_version_info().string,
			"engine_major": Engine.get_version_info().major, "engine_minor": Engine.get_version_info().minor})
		return
	if command == "close":
		get_tree().quit()
		return
	if command == "reset":
		if data.get("level", "") not in LEVELS:
			_reply(peer_id, request_id, {"error": "Unknown level"})
			return
		var size = int(data.get("image_size", 128))
		if size < 32 or size > 640:
			_reply(peer_id, request_id, {"error": "image_size must be 32..640"})
			return
		busy = true
		image_size = size
		await _reset(data)
	elif command == "step":
		if episode == null or outcome != "":
			_reply(peer_id, request_id, {"error": "Call reset before stepping"})
			return
		var action = data.get("thrusters", [])
		if not action is Array or action.size() != 3:
			_reply(peer_id, request_id, {"error": "Expected three thrusters"})
			return
		for value in action:
			if not (value is float or value is int) or not is_finite(float(value)) or value < 0 or value > 1:
				_reply(peer_id, request_id, {"error": "Thrusters must be finite in [0, 1]"})
				return
		busy = true
		episode.Rocket.set_inputs({"main_thrust": action[0],
			"rcs_left_thrust": action[1], "rcs_right_thrust": action[2]})
		get_tree().paused = false
		await get_tree().physics_frame
		await get_tree().process_frame
		get_tree().paused = true
		# RigidBody2D node properties normally sync at the NEXT physics tick.
		# Read the completed server step now so pixels/state reflect this action.
		var rocket = episode.Rocket
		var rid = rocket.get_rid()
		rocket.transform = PhysicsServer2D.body_get_state(rid, PhysicsServer2D.BODY_STATE_TRANSFORM)
		rocket.linear_velocity = PhysicsServer2D.body_get_state(rid, PhysicsServer2D.BODY_STATE_LINEAR_VELOCITY)
		rocket.angular_velocity = PhysicsServer2D.body_get_state(rid, PhysicsServer2D.BODY_STATE_ANGULAR_VELOCITY)
		rocket.force_update_transform()
		rocket.ui_update()
		step_index += 1
	else:
		_reply(peer_id, request_id, {"error": "Unknown command"})
		return
	await _send_observation(peer_id, request_id)
	busy = false

func _reset(data):
	get_tree().paused = true
	if episode != null:
		episode.free()
	# Remove the menu once; keep autoloads and the training connection alive.
	var menu = get_tree().current_scene
	if is_instance_valid(menu):
		menu.free()
	seed(int(data["seed"]))
	outcome = ""
	step_index = 0
	episode = load("res://scenes/%s.tscn" % data["level"]).instantiate()
	get_tree().root.add_child(episode)
	episode.Rocket.simulation_finished.connect(_on_finished)
	# Use a fixed world-aligned camera; no smoothing driven by wall-clock time.
	var camera = episode.Rocket.get_node("Camera2D")
	camera.position_smoothing_enabled = false
	camera.rotation_smoothing_enabled = false
	camera.ignore_rotation = true
	# Disable stochastic particles/animations in training captures.
	for node in episode.find_children("*", "GPUParticles2D", true, false):
		node.emitting = false
		node.visible = false
	for node in episode.find_children("*", "AnimatedSprite2D", true, false):
		node.stop()
	episode.Rocket.ui_update()
	await get_tree().process_frame

func _on_finished(state):
	if outcome == "" or state.get("game_state") == "crash":
		outcome = state.get("game_state", "")

func _send_observation(peer_id, request_id):
	var camera = episode.Rocket.get_node("Camera2D")
	camera.make_current()
	camera.force_update_scroll()
	await RenderingServer.frame_post_draw
	var image = get_viewport().get_texture().get_image()
	if image == null or image.is_empty():
		_reply(peer_id, request_id, {"error": "No rendered image; use a display or Xvfb, not --headless"})
		return
	image.resize(image_size, image_size, Image.INTERPOLATE_BILINEAR)
	image.convert(Image.FORMAT_RGB8)
	var state = episode.get_state()

	# JSON has no Vector2 type; encode vectors as arrays, never Python literals.
	for key in state:
		if state[key] is Vector2:
			state[key] = [state[key].x, state[key].y]
	_reply(peer_id, request_id, {"state": state, "outcome": outcome,
		"step": step_index, "width": image_size, "height": image_size,
		"rgb": Marshalls.raw_to_base64(image.get_data())})
