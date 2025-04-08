extends Node

var peer_id = null

signal request_state(peer_id:int)

func _ready():
	# Connect signals to this scene using Callable
	WebSocketServer.connect("message_received", Callable(self, "_on_message_received"))
	WebSocketServer.connect("client_connected", Callable(self, "_on_client_connected"))
	WebSocketServer.connect("client_disconnected", Callable(self, "_on_client_disconnected"))

func handle_action(data):
	var action = data['action']
	if action == "restart_level":
		self.restart_level()
	elif action == "get_state":
		request_state.emit(self.peer_id)
	elif action == "set_scripted":
		Settings.control_mode = "script"
	elif action == "quit":
		self.quit()
	elif action == "change_level":
		self.change_level(data['level_name'])

func _on_game_state_change(state) -> void:
	var json_response = JSON.stringify({"game_state": state})
	if self.peer_id != null:
		WebSocketServer.send(self.peer_id, json_response)

func restart_level():
	self._on_game_state_change("restart")
	# Get the current scene's file path
	var scene_path = get_tree().current_scene.get_scene_file_path()
	# Extract only the scene name (without the file path)
	var scene_name = scene_path.get_file().get_basename()
	change_level(scene_name, true, false)

func change_level(scene_name, force: bool = false, send_signal: bool = true):
	var current_scene_path = get_tree().current_scene.get_scene_file_path()
	var current_scene_name = current_scene_path.get_file().get_basename()
	if current_scene_name == scene_name and not force:
		return
	get_tree().paused = false
	if send_signal:
	self._on_game_state_change("new_level")
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
		print("JSON Parse Error: ", json.get_error_message(), " in ", message, " at line ", json.get_error_line())

func _on_client_connected(peer_id: int):
	self.peer_id = peer_id

func _on_client_disconnected(peer_id: int):
	self.peer_id = null

func _on_rocket_simulation_finished(state: Dictionary) -> void:
	var json_response = JSON.stringify(state)
	if self.peer_id != null:
		WebSocketServer.send(self.peer_id, json_response)
