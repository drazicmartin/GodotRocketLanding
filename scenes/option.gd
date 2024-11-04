extends Node

signal scene_restart()

@export
var scene_name : String = "level_1"

func restart():
	emit_signal("scene_restart")
	get_tree().change_scene_to_file("res://scenes/"+scene_name+".tscn")

func change_level(local_scene_name):
	emit_signal("scene_restart")
	get_tree().change_scene_to_file("res://scenes/"+local_scene_name+".tscn")

func quit():
	WebSocketServer.stop()
	get_tree().quit()

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed("restart"):
		restart()
