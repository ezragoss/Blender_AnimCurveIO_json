
bl_info = {
    'name': 'Importer/Exporter for Animation Curve Data as JSON',
    'blender': (2, 93, 0),
    'category': 'Animation'
}

import bpy
import logging
import json


log = logging.getLogger(__name__)


# ---- EXPORT


class ANIMIO_OT_fcurve_exporter(bpy.types.Operator):
    """Export action data to JSON"""
    
    bl_idname = 'animio.fcurve_exporter'
    bl_label = 'Export Anim Data'
    # We want a cleaner label for the graph context menu
    contextual_label = 'Export as JSON'
    
    # Ensure we are only writing out json
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    # -- Logging helpers
    
    def _log_error(self, type, msg):
        """Bundle the console and ui error logging"""
        log.error(msg)
        self.report({'ERROR'}, msg)
        
    # -- JSON converters
        
    def keyframe_to_json(self, keyframe, data_path, array_index, group):
        if type(keyframe) != bpy.types.Keyframe:
            print(keyframe)
            raise TypeError('Fcurve exporter is treating a non-keyframe object as a keyframe. Contact dev.')
        
        return {
            'data_path': data_path,
            'group': group,
            'array_index': array_index,
            'amplitude': keyframe.amplitude,
            'back': keyframe.back,
            'co': list(keyframe.co),
            'easing': keyframe.easing,
            'handle_left': list(keyframe.handle_left),
            'handle_left_type': keyframe.handle_left_type,
            'handle_right': list(keyframe.handle_right),
            'handle_right_type': keyframe.handle_right_type,
            'interpolation': keyframe.interpolation,
            'period': keyframe.period,
            'type': keyframe.type
        }
        
    # -- Entry point
    
    @classmethod
    def poll(cls, context):
        return context.object is not None
    
    def execute(self, context):
        """Serialize the keyframe data as json and write to disk"""
        
        # Safe because we verify with cls.poll
        export_obj = context.object
        
        # Check if any animation data exists
        anim_data = export_obj.animation_data
        if not anim_data or not anim_data.action:
            # If we have no animation data, just log as error and exit - should only happen if called directly from console
            self._log_error(ValueError, 'No animation data exists in the selected object.')
            return
        
        # Good to go, grab active action
        action = anim_data.action
            
        action_data = {
                        'name': action.name,
                        'keyframes': []
                       }
        
        # Grab groups and iterate over to write fcurve data
        groups = action.groups
        for group_name, group in groups.items():
            # For each fcurve write out the keyframes
            for _, channel in group.channels.items():
                # Each channel is an fcurve, make sure it's calculated as keyframes
                sampled = False
                if not channel.keyframe_points:
                    # Treat as sampled and convert
                    sampled = True
                    channel.convert_to_keyframes(*[int(f) for f in channel.range()])
                data_path = channel.data_path
                array_index = channel.array_index
                # We store the channel and group info in each keyframe because it pairs well with blender's keyframe_insert
                keyframes = [self.keyframe_to_json(kf, data_path, array_index, group_name) for kf in channel.keyframe_points]
                # Add these keyframes to our list to serialize
                action_data['keyframes'].extend(keyframes)
                
                if sampled:
                    channel.convert_to_samples(*[int(f) for f in channel.range()])
        
        print("Writing curve data to %s" % self.filepath)
        
        with open(self.filepath, 'w+') as file:
            # Write the json to file via the output path prop
            serialized_action = json.dumps(action_data)
            file.write(serialized_action)
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        

# ---- IMPORT

class FCurveImporterMixin:
    
    # Ensure we are only allowing json to be imported
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def _log_error(self, msg):
        """Bundle the console and ui error logging"""
        log.error(msg)
        self.report({'ERROR'}, msg)
        
    @staticmethod
    def touch_fcurve(action, data_path, array_index, replace=False):
        """Create or grab the fcurve for the data_path of a given action"""
        for curve in action.fcurves:
            if curve.data_path != data_path:
                continue
            if curve.array_index == array_index:
                if not replace:
                    # Return the found curve
                    return curve
                # Otherwise free up the curve slot
                action.fcurves.remove(curve)
                break
            
        return action.fcurves.new(data_path, index=array_index)
        
    def insert_keyframes(self, action, keyframe_data, filter=None, replace_curve=True):
        """
        Insert keyframes from dict data into action
        
        Parameters
        ------
        obj
            The object containing the curve
        keyframe_data
            The JSON-like list of keyframes
        filter
            an optional set of fcurves to target, i.e. filter = {(data_path, array_index)} will target that path and index and omit
            all other curves
        replace_curve
            an toggle for whether to replace a curve with the keyframe data being passed in or merge the imported keyframes into it
        """
        
        replaced = set()
        for keyframe in keyframe_data:
            data_path = keyframe['data_path']
            array_index = keyframe['array_index']
            
            if filter and (data_path, array_index) not in filter:
                # Ignore this curve
                continue
            
            # Grab/create the relevant fcurve based on path and index data
            fcurve = self.touch_fcurve(action, data_path, array_index, 
                                        replace_curve if (data_path, array_index) not in replaced else False)
            if replace_curve:
                # Log that this curve is one we added so we don't replace in the future
                replaced.add((data_path, array_index))
            
            # We want to insert directly like this rather than use keyframe_insert since this returns the new keyframe itself
            new_keyframe = fcurve.keyframe_points.insert(
                *keyframe['co'],
                keyframe_type=keyframe['type']
            )
            
            # Add other properties
            new_keyframe.amplitude = float(keyframe['amplitude'])
            new_keyframe.back = float(keyframe['back'])
            new_keyframe.easing = keyframe['easing']
            new_keyframe.handle_left = [float(v) for v in keyframe['handle_left']]
            new_keyframe.handle_left_type = keyframe['handle_left_type']
            new_keyframe.handle_right = [float(v) for v in keyframe['handle_right']]
            new_keyframe.handle_right_type = keyframe['handle_right_type']
            new_keyframe.interpolation = keyframe['interpolation']
            new_keyframe.period = keyframe['period']
            
    # --- Standard operator logic
    
    @classmethod
    def poll(cls, context):
        return context.object is not None
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
            

class ANIMIO_OT_action_importer(bpy.types.Operator, FCurveImporterMixin):
    """Import an action from JSON and set it as active in the selected object"""
    
    bl_idname = "animio.action_importer"
    bl_label = "Import from JSON"
    contextual_label = "Replace Action from JSON"
    
    # -- Entry point
    
    def execute(self, context):
        with open(self.filepath, 'r') as file:
            # As long as we successfully open the file
            text = file.read()
            anim_data_json = json.loads(text)
            
            print(anim_data_json)
            
            # Grab the selected object
            obj = context.object
            # Clear any animation data that might exist (in case this is being used to replace existing action)
            obj.animation_data_clear()
            anim_data = obj.animation_data_create()
            # Create the action to assign
            action = context.blend_data.actions.new(anim_data_json['name'])
            anim_data.action = action
            
            # Insert all keyframes into new action
            self.insert_keyframes(action, anim_data_json['keyframes'])
            
        return {'FINISHED'}


class FCurveResolverMixin(FCurveImporterMixin):
    """Shared execution logic for our replacer and merger"""
    
    def execute(self, context):
        """Open file path and import keyframes. Replace fcurves according to the replace class property"""
        with open(self.filepath, 'r') as file:
            # As long as we successfully open the file
            text = file.read()
            anim_data_json = json.loads(text)
            
            # Grab the selected object
            obj = context.object
            # This operator assumes an action already exists, raise exception if called in other context
            if not obj.animation_data or not obj.animation_data.action:
                # This will only be necessary if called from console after registered since we filter it out in our menu_func
                raise ValueError('Operator %s should only be called on objects with animation data and action')
            
            action = obj.animation_data.action
            
            # Insert keyframes with the replace toggle on
            self.insert_keyframes(action, anim_data_json['keyframes'], replace_curve=self.replace_curve)
            
        return {'FINISHED'}
    
    
class ANIMIO_OT_fcurve_replacer(bpy.types.Operator, FCurveResolverMixin):
    """Import curves from JSON and replace their corresponding curves in this action. Add any imported curves that don't exist yet"""
    
    bl_idname = "animio.fcurve_replacer"
    bl_label = "Import from JSON"
    contextual_label = "Replace/Add Curves from JSON"
    
    replace_curve = True

    
class ANIMIO_OT_fcurve_merger(bpy.types.Operator, FCurveResolverMixin):
    """Import curves from JSON and merge their keyframes into corresponding curves in this action. Add any imported curves that don't exist yet"""
    
    bl_idname = "animio.fcurve_merger"
    bl_label = "Import from JSON"
    contextual_label = "Merge/Add Curves from JSON"
    
    replace_curve = False
    

# ---- Add-on registration

importers = (ANIMIO_OT_action_importer, ANIMIO_OT_fcurve_replacer, ANIMIO_OT_fcurve_merger)
operators = (ANIMIO_OT_fcurve_exporter, *importers)

def graph_context_menu_func(self, context):
    """Our menu logic for the graph menu context menu"""
    layout = self.layout
    
    layout.operator_context = 'INVOKE_DEFAULT'
    
    obj = context.object
    if context.object.animation_data and context.object.animation_data.action:
        # Present all options
        for operator in operators:
            layout.operator(operator.bl_idname, text=operator.contextual_label)
    else:
        # There is no data to export or replace just add the import action button to menu with more generic label
        layout.operator(ANIMIO_OT_action_importer.bl_idname, text='Import Action from JSON')
        
    layout.separator()
        
def register():
    for cls in operators:
        bpy.utils.register_class(cls)
    # Add the ops to the graph context menu
    bpy.types.GRAPH_MT_context_menu.prepend(graph_context_menu_func)
    
def unregister():
    for cls in operators:
        bpy.utils.unregister_class(cls)
        
if __name__ == "__main__":
    register()