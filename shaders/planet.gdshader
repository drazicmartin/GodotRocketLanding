shader_type canvas_item;

// Exported parameters
uniform float radius = 1; // Adjustable radius
uniform vec4 planet_color = vec4(0.0, 1.0, 0.0, 1.0); // Green by default

void fragment() {
    // Get the UV coordinates of the pixel (0 to 1 range)
    vec2 uv = UV;

    // Center the UV coordinates (-0.5 to 0.5 range)
    vec2 centered_uv = uv - vec2(0.5);

    // Calculate the distance from the center of the texture
    float dist = length(centered_uv);

    // Check if the pixel is within the planet's radius
    if (dist <= radius) {
        // Set the planet's color to green
        COLOR = planet_color;
    } else {
        // Make the pixel transparent (outside the planet)
        COLOR = vec4(0.0, 0.0, 0.0, 0.0); // Transparent
    }
}
