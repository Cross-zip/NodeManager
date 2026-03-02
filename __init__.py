import sys
import os
import bpy
from mathutils import Vector
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Function import NodeManager

tree = bpy.context.active_object.active_material.node_tree
active_node = tree.nodes.active

if active_node:
    
    root_wrapper = NodeManager.initialize_hierarchy(active_node)
    
    root_wrapper.out_links_count = 0 
    NodeManager.calculate_depth(root_wrapper, 0)
     
    NodeManager.apply_layout(root_wrapper)