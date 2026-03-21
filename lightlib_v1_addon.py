bl_info = {
    "name": "Lightlib Blender Plugin",
    "author": "PRGM Services",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > LightLib",
    "description": "Imports JSON lighting rigs from lightlib.dev",
    "category": "Lighting",
}

import json
import math

import bpy
import mathutils


# Helper functions
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    r, g, b = tuple(int(hex_str[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b))


# Main operator
class LIGHTLIB_OT_import_rig(bpy.types.Operator):
    bl_idname = "lightlib.import_rig"
    bl_label = "Paste Rig from Clipboard"
    bl_description = "Generates a 3D lighting rig from JSON data in your clipboard"

    def execute(self, context):
        clipboard_data = context.window_manager.clipboard
        try:
            data = json.loads(clipboard_data)
        except json.JSONDecodeError:
            self.report({"ERROR"}, "Clipboard does not contain valid JSON.")
            return {"CANCELLED"}

        if "lights" not in data:
            self.report({"ERROR"}, "JSON is missing the 'lights' array.")
            return {"CANCELLED"}

        rig_name = data.get("rig_name", "Lighting Rig")

        # Create Master Anchor
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
        anchor = context.active_object
        anchor.name = rig_name

        # matching blenders Z up axis by rotating objects
        mat_conversion = mathutils.Matrix.Rotation(math.radians(90.0), 4, "X")

        for l_data in data["lights"]:
            light_type = l_data.get("type", "AREA").upper()
            if light_type == "DIRECTIONAL":
                light_type = "SUN"

            # Create Light Object
            light_data = bpy.data.lights.new(name=l_data["name"], type=light_type)
            light_obj = bpy.data.objects.new(
                name=l_data["name"], object_data=light_data
            )
            context.collection.objects.link(light_obj)
            light_obj.parent = anchor

            # Matrix transformation
            pos = l_data.get("position", [0, 0, 0])
            rot = l_data.get("rotation", [0, 0, 0])

            # Build the exact 3D coordinates exactly as they exist in the web browser
            loc_three = mathutils.Vector((pos[0], pos[1], pos[2]))
            eul_three = mathutils.Euler(
                (math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])),
                "XYZ",
            )
            mat_three = mathutils.Matrix.LocRotScale(loc_three, eul_three, None)

            # Multiply by our conversion matrix and apply it! No more guessing!
            light_obj.matrix_local = mat_conversion @ mat_three

            # handling color and temprature
            if hasattr(light_data, "use_color_temperature"):
                if l_data.get("use_temperature", False):
                    light_data.use_color_temperature = True
                    light_data.color_temperature = l_data.get("temperature_k", 5600)
                    light_data.color = (1.0, 1.0, 1.0)
                else:
                    light_data.use_color_temperature = False
                    light_data.color = hex_to_rgb(l_data.get("color_hex", "#ffffff"))
            else:
                light_data.color = hex_to_rgb(l_data.get("color_hex", "#ffffff"))

            # power / exposure for lights
            multiplier = l_data.get("intensity_multiplier", 1.0)
            ev = l_data.get("exposure_ev", 10.0)
            light_data.energy = multiplier * (2**ev)

            # dealing with light type shapes
            if light_type == "AREA":
                light_data.shape = "RECTANGLE"
                light_data.size = l_data.get("width_m", 1.0)
                light_data.size_y = l_data.get("height_m", 1.0)
            elif light_type == "SPOT":
                light_data.spot_size = math.radians(l_data.get("cone_angle_deg", 45.0))
                light_data.spot_blend = l_data.get("penumbra", 0.5)

            # dealing with tracking targets
            if l_data.get("track_target", False):
                t_pos = l_data.get("target_position", [0, 0, 0])
                t_vec = mathutils.Vector((t_pos[0], t_pos[1], t_pos[2]))

                # Convert the target dot using the same master matrix
                t_global = mat_conversion @ t_vec

                bpy.ops.object.empty_add(type="SPHERE", radius=0.1, location=t_global)
                target_empty = context.active_object
                target_empty.name = f"{l_data['name']}_Target"
                target_empty.parent = anchor

                track = light_obj.constraints.new(type="TRACK_TO")
                track.target = target_empty
                track.track_axis = "TRACK_NEGATIVE_Z"
                track.up_axis = "UP_Y"

        self.report({"INFO"}, f"Successfully imported {rig_name}")
        return {"FINISHED"}


class LIGHTLIB_PT_main_panel(bpy.types.Panel):
    bl_label = "Lightlib"
    bl_idname = "LIGHTLIB_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Lightlib"

    def draw(self, context):
        self.layout.operator(
            LIGHTLIB_OT_import_rig.bl_idname,
            text="Paste Rig from Clipboard",
            icon="PASTEDOWN",
        )


classes = (LIGHTLIB_OT_import_rig, LIGHTLIB_PT_main_panel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
