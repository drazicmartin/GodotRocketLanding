extends Node2D

var peer_id = null
var message_received_flag = false  # Flag to track if a message has been received
var run_once: bool = false

@onready
var rocket = $Rocket

func _ready():
	# Connect signals to this scene using Callable
	WebSocketServer.connect("message_received", Callable(self, "_on_message_received"))
	WebSocketServer.connect("client_connected", Callable(self, "_on_client_connected"))
	WebSocketServer.connect("client_disconnected", Callable(self, "_on_client_disconnected"))
	
	# Initially, pause the game
	get_tree().paused = true
	
func _physics_process(delta: float) -> void:
	if run_once:
		get_tree().paused = true
		send_state()
	run_once = true

func send_state():
	# Responding with a JSON message
	var response = rocket.get_state()
	var json_response = JSON.stringify(response)
	WebSocketServer.send(self.peer_id, json_response)

func allow_one_physics_step() -> void:
	# This method can be called externally or in response to some event
	# Unpause the game and allow one physics step
	run_once = false
	get_tree().paused = false

func _on_message_received(peer_id: int, message: String):
	self.peer_id = peer_id
	allow_one_physics_step()
	# Parse the received message
	var json = JSON.new()
	var error = json.parse(message)
	if error == OK:
		var data = json.data
		rocket.set_inputs(data)
	else:
		print("JSON Parse Error: ", json.get_error_message(), " in ", message, " at line ", json.get_error_line())

func _on_client_connected(peer_id: int):
	print("Client connected")
	self.peer_id = peer_id
	send_state()

func _on_client_disconnected(peer_id: int):
	self.peer_id = null

func _on_rocket_simulation_finished(state: Dictionary) -> void:
	var json_response = JSON.stringify(state)
	if self.peer_id != null:
		WebSocketServer.send(self.peer_id, json_response)

func _on_restart_scene_restart() -> void:
	var json_response = JSON.stringify({"game_state": "restart"})
	if self.peer_id != null:
		WebSocketServer.send(self.peer_id, json_response)
