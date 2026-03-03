import bpy
from .NodeManager import NodeManager

bl_info = {
    "name": "Node Manager",
    "author": "Cross-zip",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "Node Editor > Search (F3)",
    "description": "自动整理材质节点布局",
    "category": "Node",
}

class NODEMANAGER_OT_auto_layout(bpy.types.Operator):

    bl_idname = "node.nodemanager_auto_layout"
    bl_label = "Node Manager 自动布局"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            self.report({"ERROR"}, "没有活动物体")
            return {"CANCELLED"}

        mat = getattr(obj, "active_material", None)
        if mat is None or mat.node_tree is None:
            self.report({"ERROR"}, "没有可用的材质节点树")
            return {"CANCELLED"}

        tree = mat.node_tree
        active_node = tree.nodes.active
        if active_node is None:
            self.report({"ERROR"}, "请选择活动节点")
            return {"CANCELLED"}

        manager = NodeManager()
        root_wrapper = manager.initialize_hierarchy(active_node)

        root_wrapper.out_links_count = 0
        manager.calculate_depth(root_wrapper, 0)
        manager.apply_layout(root_wrapper)

        return {"FINISHED"}


classes = (
    NODEMANAGER_OT_auto_layout,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()