from collections import defaultdict
import bpy

try:
    # 作为 Blender 插件包内模块导入
    from .NodeWrapper import NodeW
except ImportError:
    # 作为独立脚本运行时的回退导入
    from NodeWrapper import NodeW

#节点管理器，用于管理节点之间的关系和布局
class NodeManager:
    def __init__(self):
        self.node_instances = defaultdict(list)
        self.depth_groups = defaultdict(list)
        self.margin = 40

    def loop_in_links(self,loop_node):

        if isinstance(loop_node, bpy.types.Node):
            n=loop_node
        elif isinstance(loop_node,NodeW):
            n=loop_node.node
        else:
            return

        for input in n.inputs:
            for link in input.links:
                yield link
    def loop_out_links(self,loop_node):
        
        if isinstance(loop_node, bpy.types.Node):
            n=loop_node
        elif isinstance(loop_node,NodeW):
            n=loop_node.node
        else:
            return

        for output in n.outputs:
            for link in output.links:
                yield link
    def get_wrapper(self, node):
        ptr = node.as_pointer()
        if ptr not in self.node_instances:
            self.node_instances[ptr] = NodeW(node)
        return self.node_instances[ptr]
    def relink_socket(self, s1, s2):
        return
    def check_type(self,fnode,link,if_changed=None):
        # 检查前一个节点是否为特殊节点类型（REROUTE，GROUP）
        real_node=fnode
        curr_link=link
        while real_node.type == "REROUTE":

            if not real_node.inputs[0].links:
                real_node.id_data.nodes.remove(real_node)
                return None

            link1=curr_link
            link2=real_node.inputs[0].links[0]
            real_node = real_node.inputs[0].links[0].from_node
            extra_node=link1.from_node

            self.relink_socket(link1.to_socket,link2.from_socket)
            extra_node.id_data.nodes.remove(extra_node) # 同样可以选择不删除，等到最后统一删除多余节点

        return real_node

    def initialize_hierarchy(self, node):

        curr_w = self.get_wrapper(node)
        #检查是否已经深度遍历
        if hasattr(curr_w, "_init_flag"):
            curr_w.out_links_count += 1
            return curr_w
        curr_w._init_flag = True
        curr_w.out_links_count = 1 
        
        for link in self.loop_in_links(curr_w):
            from_nodes=self.check_type(link.from_node,link)
            if from_nodes is None:
                continue

            from_w = self.initialize_hierarchy(from_nodes)
    
            from_w.to_nodes.append(curr_w)
            curr_w.from_nodes.append(from_w)
        return curr_w
    def calculate_depth(self, node_w, current_depth):
        
        node_w.depth = max(current_depth, node_w.depth)
        node_w.out_links_count -= 1
        
        if node_w.out_links_count > 0:
            return
        
        self.depth_groups[node_w.depth].append(node_w)

        for parent_w in node_w.from_nodes:
            self.calculate_depth(parent_w, node_w.depth + 1)

    def set_node_priority(self, depth):
        
        nodes_in_layer = self.depth_groups[depth]
        
        right_node_usage = defaultdict(int)
        for nw in nodes_in_layer:
            for target in nw.to_nodes:
                right_node_usage[target.as_pointer()] += 1

        for nw in nodes_in_layer:

            nw.target_y=nw.posW.y
            if nw.to_nodes:
                for tnw in nw.to_nodes:
                    if nw.depth-tnw.depth==1:
                        nw.next_layer_nodes.append(tnw)
                nw.target_y = sum(t.posW.y for t in nw.next_layer_nodes) / len(nw.next_layer_nodes)

            num_targets = len(nw.to_nodes)

            if num_targets == 1:
                target_ptr = nw.to_nodes[0].as_pointer()
                if right_node_usage[target_ptr] == 1:
                    nw.priority = 0 
                else:
                    nw.priority = 1 
            else:
                nw.priority = 2 
    def occupied_handler(self,y,height,areas):
        if not areas:
            areas.append([y, y - height])
            return y

        find_right_pos=False
        while(not find_right_pos):

            for area in areas:
                if y>area[1] and y-height<area[0]:
                    y=area[1]+self.margin
                    continue

            find_right_pos=True

        areas.append([y,y-height])
        return y
        
    def apply_layout(self, root_w):
        
        sorted_depths = sorted(self.depth_groups.keys())
        
        for d in sorted_depths:
            layer_nodes = self.depth_groups[d]
            self.set_node_priority(d)
            
            layer_nodes.sort(key=lambda x: (x.priority, abs(x.target_y - root_w.posW.y)))
            
            occupied_areas = []
            
            for nw in layer_nodes:
                if nw.next_layer_nodes:
                    nw.posW.x = nw.next_layer_nodes[0].posW.x - nw.width*(1-1/6) 
                nw_height=nw.node.dimensions.y

                nw.posW.y=self.occupied_handler(nw.target_y,nw_height,occupied_areas)

                nw.SetWorldPos(nw.posW.x,nw.posW.y)