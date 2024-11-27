extends Node2D

var peer_id = null
var message_received_flag = false  # Flag to track if a message has been received
var run_once: bool = false

@onready
var Rocket = $Rocket
@onready
var Action = $Actions

func _ready():
	# Connect signals to this scene using Callable
	WebSocketServer.connect("message_received", Callable(self, "_on_message_received"))
	WebSocketServer.connect("client_connected", Callable(self, "_on_client_connected"))
	WebSocketServer.connect("client_disconnected", Callable(self, "_on_client_disconnected"))
	
	Action.connect("request_state", Callable(self, "_on_request_state"))
	
	if Settings.control_mode == "script":
		# Initially, pause the game
		get_tree().paused = true

func _physics_process(delta: float) -> void:
	if Settings.control_mode == "script":
		if run_once:
			get_tree().paused = true
			send_state(self.peer_id)
		run_once = true

func _on_request_state(peer_id):
	send_state(peer_id)

func send_state(peer_id):
	# Responding with a JSON message
	var response = Rocket.get_state()
	var json_response = JSON.stringify(response)
	if peer_id != null:
		WebSocketServer.send(peer_id, json_response)

func allow_one_physics_step() -> void:
	# This method can be called externally or in response to some event
	# Unpause the game and allow one physics step
	run_once = false
	get_tree().paused = false

func _on_message_received(peer_id: int, message: String):
	self.peer_id = peer_id
	# Parse the received message
	var json = JSON.new()
	var error = json.parse(message)
	if error == OK:
		var data: Dictionary = json.data
		if data.has("action"):
			pass
		else:
			Rocket.set_inputs(data)
			allow_one_physics_step()
	else:
		print("JSON Parse Error: ", json.get_error_message(), " in ", message, " at line ", json.get_error_line())

func _on_client_connected(peer_id: int):
	print("Client connected")
	self.peer_id = peer_id

func _on_client_disconnected(peer_id: int):
	print("Client Disconnected")
	self.peer_id = null
