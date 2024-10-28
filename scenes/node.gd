extends Node

signal scene_restart()

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed("restart"):
		emit_signal("scene_restart")
		get_tree().change_scene_to_file("res://scenes/main.tscn")
