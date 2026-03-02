from collections import defaultdict
from NodeWrapper import NodeW

class NodeManager:
    def __init__(self):
        self.node_instances = defaultdict(list)
        self.depth_groups = defaultdict(list)
        self.margin = 40

    def get_wrapper(self, node):
        ptr = node.as_pointer()
        if ptr not in self.node_instances:
            self.node_instances[ptr] = NodeW(node)
        return self.node_instances[ptr]
    def initialize_hierarchy(self, node):
        curr_w = self.get_wrapper(node)

        if hasattr(curr_w, "_init_flag"):
            curr_w.out_links_count += 1
            return curr_w
        curr_w._init_flag = True
        curr_w.out_links_count = 1 
        
        for input in node.inputs:
            for link in input.links:
                from_w = self.initialize_hierarchy(link.from_node)
                
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

            nw.target_y=nw.node.location.y
            if nw.to_nodes:
                for tnw in nw.to_nodes:
                    if nw.depth-tnw.depth==1:
                        nw.next_layer_nodes.append(tnw)
                nw.target_y = sum(t.location.y for t in nw.next_layer_nodes) / len(nw.next_layer_nodes)

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
        for area in areas:
            if y>area[1] and y-height<area[0]:
                y=area[1]+self.margin
                continue
        areas.append([y,y-height])
        return y
    def apply_layout(self, root_w):
        
        sorted_depths = sorted(self.depth_groups.keys())
        
        for d in sorted_depths:
            layer_nodes = self.depth_groups[d]
            self.set_node_priority(d)
            
            layer_nodes.sort(key=lambda x: (x.priority, abs(x.target_y - root_w.location.y)))
            
            occupied_areas = []
            
            for nw in layer_nodes:
                if nw.next_layer_nodes:
                    nw.node.location.x = nw.next_layer_nodes[0].node.location.x - nw.width*(1-1/6) 
                nw_height=nw.node.dimensions.y
                nw.node.location.y=self.occupied_handler(nw.target_y,nw_height,occupied_areas)
