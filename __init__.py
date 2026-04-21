import bpy
from .NodeManager import NodeManager

bl_info = {
    "name": "Node Manager",
    "author": "Cross-zip",
    "version": (0, 1, 0),
    "blender": (5, 0, 0),
    "location": "Node Editor > Sidebar (N) > Node Manager",
    "description": "基于sugiyama算法自动整理材质节点布局",
    "category": "Node",
}


class NODEMANAGER_OT_auto_layout(bpy.types.Operator):
    bl_idname = "node.nodemanager_auto_layout"
    bl_label = "自动布局"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
    
        tree = context.space_data.edit_tree 

        if tree is None or tree.nodes is None:
            self.report({"ERROR"}, "没有可用的材质节点树")
            return {"CANCELLED"}

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


class NODEMANAGER_PT_panel(bpy.types.Panel):
    bl_label = "Node Manager"
    bl_idname = "NODEMANAGER_PT_panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Node Manager"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("node.nodemanager_auto_layout", icon="NODETREE")


classes = (
    NODEMANAGER_OT_auto_layout,
    NODEMANAGER_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()