extends Node2D

var global_peer_id = null
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
	run_once = true

func _on_client_connected(peer_id: int) -> void:
	#print("Client connected: " + str(peer_id))
	global_peer_id = peer_id

func _on_client_disconnected(peer_id: int) -> void:
	#print("Client disconnected: " + str(peer_id))
	pass

func allow_one_physics_step() -> void:
	# This method can be called externally or in response to some event
	# Unpause the game and allow one physics step
	run_once = false
	get_tree().paused = false

func _on_message_received(peer_id: int, message: String):
	allow_one_physics_step()
	# Parse the received message
	var json_parser = JSON.new()
	
	# Parse the received message
	var data = json_parser.parse(message)
	
	# Responding with a JSON message
	var response = rocket.get_state()
	var json_response = JSON.stringify(response)
	WebSocketServer.send(peer_id, json_response)
