extends Control

var global_peer_id = null

@onready var input_port_number: TextEdit = $"VBoxContainer2/HBoxContainer/Server VBoxContainer/InputPortNumber"
@onready var check_button: CheckButton = $"VBoxContainer2/VBoxContainer/Select Mode/CheckButton"

# In the script of the new scene (e.g., main_menu.gd)
func _ready():
	
	# Connect signals to this scene using Callable
	WebSocketServer.connect("message_received", Callable(self, "_on_message_received"))
	WebSocketServer.connect("client_connected", Callable(self, "_on_client_connected"))
	WebSocketServer.connect("client_disconnected", Callable(self, "_on_client_disconnected"))
	
	var args = OS.get_cmdline_args()
	for arg in args:
		print("Argument passed: ", arg)
	# Example of using arguments
	if "-p" in args:
		var value_index = args.find("-p") + 1
		if value_index < args.size():
			var value = args[value_index]
			input_port_number.text = value
	if "--port" in args:
		var value_index = args.find("--port") + 1
		if value_index < args.size():
			var value = args[value_index]
			input_port_number.text = value
	
	check_button.button_pressed = Settings.control_mode == "script"
	
	WebSocketServer.stop()
	WebSocketServer.listen(int(input_port_number.text)) # Replace with function body.

func _on_exit_button_pressed() -> void:
	$Actions.quit()

func _on_send_message_pressed() -> void:
	if global_peer_id:
		WebSocketServer.send(global_peer_id, "my message")
	else:
		print("No peer_id")

func _on_check_button_toggled(toggled_on: bool) -> void:
	Settings.control_mode = "script" if toggled_on else "manual"

func _on_check_button_button_up() -> void:
	WebSocketServer.stop()
	WebSocketServer.listen(int(input_port_number.text)) # Replace with function body.

func _on_check_button_button_down() -> void:
	WebSocketServer.stop()

func _on_start_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/random_level.tscn")

func _on_start_level_1_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/level_1.tscn")

func _on_start_level_2_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/level_2.tscn")

func _on_start_level_3_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/level_3.tscn")

func _on_start_level_4_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/level_4.tscn")
