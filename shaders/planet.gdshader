shader_type canvas_item;

// Uniforms for properties
uniform float radius;
uniform vec4 color : source_color;
uniform float atmosphere_size;
uniform vec4 atmosphere_color : source_color;

// Uniform for texture size in pixels
uniform vec2 texture_size;

void fragment() {
    // Convert UV coordinates to pixel space
    vec2 pixel_pos = UV * texture_size;
    vec2 center = texture_size * 0.5; // Center in pixel space

    // Compute the distance in pixels
    float dist = length(pixel_pos - center);

    if (dist < radius) {
        COLOR = color; // Planet color
	//} else if (dist < radius + atmosphere_size && dist > radius + atmosphere_size - 2.0) {
		//COLOR = vec4(0,0,0,1);
    } else if (dist < radius + atmosphere_size) {
        float alpha = 1.0 - exp(-(dist - radius) / (radius+atmosphere_size));
        COLOR = vec4(atmosphere_color.rgb, alpha); // Atmosphere gradient
    } else {
        discard; // Outside the texture, make it transparent
    }
}
