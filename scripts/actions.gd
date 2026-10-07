extends Node
# Single entry point for every message coming from the Python client (see docs/protocol.md).
# Control messages carry an "action" key; a message without one is a legacy step (raw thruster inputs).

var peer_id = null

# Result of the current episode ({"game_state": "victory"|"crash", ...}); empty while it is running.
# main.gd merges it into the state it replies with, so a terminal step is still a single reply.
var episode_result: Dictionary = {}

signal request_state(peer_id:int)
signal step_requested(inputs: Dictionary, frame_skip: int)

func _ready():
	# Connect signals to this scene using Callable
	WebSocketServer.connect("message_received", Callable(self, "_on_message_received"))
	WebSocketServer.connect("client_connected", Callable(self, "_on_client_connected"))
	WebSocketServer.connect("client_disconnected", Callable(self, "_on_client_disconnected"))

func handle_action(data: Dictionary):
	var action = data['action']
	if Settings.debug: print("received action : " + action)
	if action == "hello":
		_send({"ack": "hello", "protocol": Settings.PROTOCOL_VERSION})
	elif action == "step":
		step_requested.emit(data.get("inputs", {}), int(data.get("frame_skip", 1)))
	elif action == "restart_level":
		self.restart_level()
		_send({"ack": "restart_level"})
	elif action == "get_state":
		request_state.emit(self.peer_id)
	elif action == "set_scripted":
		Settings.control_mode = "script"
		Engine.max_physics_steps_per_frame = 1
		Engine.physics_jitter_fix = 0.0
		Engine.physics_ticks_per_second = 30
	elif action == "set_seed":
		# The RNG is only consumed when a level is loaded (rocket.gd _ready), so send this before restart_level.
		seed(int(data["seed"]))
	elif action == "quit":
		self.quit()
	elif action == "change_level":
		self.change_level(data['level_name'])
		_send({"ack": "change_level"})

func _send(message: Dictionary) -> void:
	if self.peer_id != null:
		WebSocketServer.send(self.peer_id, JSON.stringify(message))

func restart_level():
	# Get the current scene's file path
	var scene_path = get_tree().current_scene.get_scene_file_path()
	# Extract only the scene name (without the file path)
	var scene_name = scene_path.get_file().get_basename()
	change_level(scene_name, true)

func change_level(scene_name, force: bool = false):
	var current_scene_path = get_tree().current_scene.get_scene_file_path()
	var current_scene_name = current_scene_path.get_file().get_basename()
	if current_scene_name == scene_name and not force:
		return
	get_tree().paused = false
	get_tree().change_scene_to_file("res://scenes/"+scene_name+".tscn")

func quit():
	WebSocketServer.stop()
	get_tree().quit()

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed("restart"):
		self.restart_level()
	if Input.is_action_pressed("echap"):
		self.change_level("main_menu")

func _on_message_received(peer_id: int, message: String):
	self.peer_id = peer_id
	# Parse the received message
	var json = JSON.new()
	var error = json.parse(message)
	if error == OK:
		var data: Dictionary = json.data
		if data.has("action"):
			handle_action(data)
		else:
			# Legacy protocol: a bare dict of thruster inputs is one step.
			step_requested.emit(data, 1)
	else:
		print("JSON Parse Error: ", json.get_error_message(), " in ", message, " at line ", json.get_error_line())

func _on_client_connected(peer_id: int):
	self.peer_id = peer_id

func _on_client_disconnected(peer_id: int):
	self.peer_id = null

func _on_rocket_simulation_finished(state: Dictionary) -> void:
	# Keep the first outcome: victory is re-emitted every tick while the rocket sits on the ground.
	if episode_result.is_empty():
		episode_result = state
