import bpy

try:
    from .CompactMode import NodeManager as CompactNodeManager
except ImportError:
    from CompactMode import NodeManager as CompactNodeManager

try:
    from .AlignMode import NodeManager as AlignNodeManager
except ImportError:
    from AlignMode import NodeManager as AlignNodeManager

try:
    from .TilingMode import NodeManager as TilingNodeManager
except ImportError:
    from TilingMode import NodeManager as TilingNodeManager

bl_info = {
    "name": "Node Manager",
    "author": "Cross-zip",
    "version": (0, 2, 0),
    "blender": (5, 0, 0),
    "location": "Node Editor > Sidebar (N) > Node Manager",
    "description": "Based on Sugiyama-style layering with selectable modes",
    "category": "Node",
}


class NODEMANAGER_OT_auto_layout(bpy.types.Operator):
    bl_idname = "node.nodemanager_auto_layout"
    bl_label = "自动布局"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tree = context.space_data.edit_tree

        if tree is None or tree.nodes is None:
            self.report({"ERROR"}, "没有可用的节点树")
            return {"CANCELLED"}

        active_node = tree.nodes.active
        if active_node is None:
            self.report({"ERROR"}, "请选择活动节点")
            return {"CANCELLED"}

        mode = getattr(context.scene, "nodemanager_mode", "TILING")

        if mode == "COMPACT":
            manager = CompactNodeManager(tree)
        elif mode == "ALIGN":
            manager = AlignNodeManager(tree)
        else:
            manager = TilingNodeManager(tree)

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
        col.prop(context.scene, "nodemanager_mode", text="Mode")
        col.operator("node.nodemanager_auto_layout", icon="NODETREE")


classes = (
    NODEMANAGER_OT_auto_layout,
    NODEMANAGER_PT_panel,
)


def register():
    bpy.types.Scene.nodemanager_mode = bpy.props.EnumProperty(
        name="Mode",
        description="Layout mode",
        items=[
            ("COMPACT", "Compact", "Compact layer layout"),
            ("ALIGN", "Align", "Anchor-weight layout with strict overlap solving"),
            ("TILING", "Tiling", "Flowchart blocks (material)"),
        ],
        default="TILING",
    )
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "nodemanager_mode"):
        del bpy.types.Scene.nodemanager_mode


if __name__ == "__main__":
    register()
