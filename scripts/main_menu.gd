extends Control

var global_peer_id = null

@onready
var input_port = $"HBoxContainer/Server VBoxContainer/InputPortNumber"

# In the script of the new scene (e.g., main_menu.gd)
func _ready():
	# Connect signals to this scene using Callable
	WebSocketServer.connect("message_received", Callable(self, "_on_message_received"))
	WebSocketServer.connect("client_connected", Callable(self, "_on_client_connected"))
	WebSocketServer.connect("client_disconnected", Callable(self, "_on_client_disconnected"))

func _on_client_connected(peer_id: int) -> void:
	print("client connected" + str(peer_id))
	global_peer_id = peer_id

func _on_client_disconnected(peer_id: int) -> void:
	print("client disconnected" + str(peer_id))

func _on_message_received(peer_id: int, message: String):
	# Parse the received message
	var json_parser = JSON.new()
	
	# Parse the received message
	var data = json_parser.parse(message)
	print("Received from Python:", data)
	
	# Responding with a JSON message
	var response = {
		"response": "Hello, Python!",
		"status": "success"
	}
	var json_response = JSON.stringify(response)
	WebSocketServer.send(peer_id, json_response)

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass

func _on_start_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/main.tscn")

func _on_exit_button_pressed() -> void:
	WebSocketServer.stop()
	get_tree().quit()

func _on_listen_button_pressed() -> void:
	WebSocketServer.stop()
	WebSocketServer.listen(int(input_port.text))

func _on_send_message_pressed() -> void:
	if global_peer_id:
		WebSocketServer.send(global_peer_id, "my message")
	else:
		print("No peer_id")
