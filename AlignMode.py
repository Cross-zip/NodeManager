from collections import defaultdict
import bpy

try:
    from .NodeWrapper import NodeW
except ImportError:
    from NodeWrapper import NodeW

#节点管理器，用于管理节点之间的关系和布局
class NodeManager:
    def __init__(self, tree):
        self.node_instances = defaultdict(list)
        self.depth_groups = defaultdict(list)
        self.margin = 80
        self.tree = tree
        self._virtual_occupied_by_depth = defaultdict(list)

    def loop_in_links(self, loop_node):

        if isinstance(loop_node, bpy.types.Node):
            n = loop_node
        elif isinstance(loop_node, NodeW):
            n = loop_node.node
        else:
            return

        for input in n.inputs:
            for link in input.links:
                yield link

    def loop_out_links(self, loop_node):

        if isinstance(loop_node, bpy.types.Node):
            n = loop_node
        elif isinstance(loop_node, NodeW):
            n = loop_node.node
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

    def LinkSocket(self, s1, s2):
        self.tree.links.new(s1, s2)
        return

    def check_type(self, fnode, link):
        # 检查前一个节点是否为特殊节点类型（REROUTE）
        real_fnode = fnode
        to_socket = link.to_socket
        while real_fnode.type == "REROUTE":
            if not real_fnode.inputs[0].links:  # 若转接点前面无节点连接，移除转接点并且返回空值
                real_fnode.id_data.nodes.remove(real_fnode)
                return None
            elif len(real_fnode.outputs[0].links)>1:
                return real_fnode

            # 若有节点连接则融并该转接点
            link0 = real_fnode.inputs[0].links[0]
            from_node = link0.from_node
            from_socket = link0.from_socket
            self.LinkSocket(from_socket, to_socket)

            old_fnode = real_fnode
            old_fnode.id_data.nodes.remove(old_fnode)

            real_fnode = from_node

        return real_fnode

    def initialize_hierarchy(self, node):

        curr_w = self.get_wrapper(node)
        # 检查是否已经深度遍历
        if hasattr(curr_w, "_init_flag"):
            curr_w.out_links_count += 1
            return curr_w
        curr_w._init_flag = True
        curr_w.out_links_count = 1

        for link in self.loop_in_links(curr_w):
            from_nodes = self.check_type(link.from_node, link)
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

    def _priority_weight(self, priority: int) -> float:
        if priority == 0:
            return 3.0
        if priority == 1:
            return 2.0
        return 1.0

    def _socket_index(self, node, socket, is_input: bool) -> int:
        try:
            return int(socket.index)
        except Exception:
            pass

        sockets = node.inputs if is_input else node.outputs
        for i, s in enumerate(sockets):
            if s == socket:
                return i
        return 0

    def _socket_world_y(self, node_w: NodeW, socket, is_input: bool) -> float:
        sockets = node_w.node.inputs if is_input else node_w.node.outputs
        count = len(sockets)
        if count <= 0:
            return node_w.posW.y - node_w.height / 2

        idx = self._socket_index(node_w.node, socket, is_input=is_input)
        gap = node_w.height / (count + 1)
        return node_w.posW.y - gap * (idx + 1)

    def _layout_height(self, nw: NodeW) -> float:
        h = float(getattr(nw, "height", 0.0) or 0.0)
        if h > 1.0:
            return h
        # Some Blender node types may report 0 dimensions until UI redraw; use a safe fallback.
        if getattr(nw.node, "type", "") == "REROUTE":
            return 20.0
        return 80.0

    def set_node_priority(self, depth):

        nodes_in_layer = self.depth_groups[depth]

        right_node_usage = defaultdict(int)
        for nw in nodes_in_layer:
            nw.next_layer_nodes = []
        for nw in nodes_in_layer:
            for target in nw.to_nodes:
                right_node_usage[target.as_pointer()] += 1

        for nw in nodes_in_layer:

            nw.target_y = nw.posW.y
            if nw.to_nodes:
                socket_targets_y = []
                for link in self.loop_out_links(nw):
                    to_node = link.to_node
                    if to_node is None:
                        continue
                    tnw = self.get_wrapper(to_node)
                    if nw.depth - tnw.depth != 1:
                        continue

                    nw.next_layer_nodes.append(tnw)
                    socket_targets_y.append(self._socket_world_y(tnw, link.to_socket, is_input=True))

                if socket_targets_y:
                    nw.target_y = sum(socket_targets_y) / len(socket_targets_y)

            num_targets = len(nw.to_nodes)

            if num_targets == 1:
                target_ptr = nw.to_nodes[0].as_pointer()
                if right_node_usage[target_ptr] == 1:
                    nw.priority = 0
                else:
                    nw.priority = 1
            else:
                nw.priority = 2

    def _build_virtual_occupied(self):
        self._virtual_occupied_by_depth = defaultdict(list)

        for depth, nodes in self.depth_groups.items():
            for nw in nodes:
                for tnw in nw.to_nodes:
                    span = nw.depth - tnw.depth
                    if span <= 1:
                        continue

                    from_center = nw.posW.y - nw.height / 2
                    to_center = tnw.posW.y - tnw.height / 2
                    denom = max(1, span)

                    virtual_h = max(16.0, self.margin * 0.6)
                    for inter_depth in range(tnw.depth + 1, nw.depth):
                        t = (inter_depth - tnw.depth) / denom
                        center = to_center + (from_center - to_center) * t
                        top = center + virtual_h / 2
                        self._virtual_occupied_by_depth[inter_depth].append([top, top - virtual_h])

    def _solve_layer_centers(self, layer_nodes, virtual_areas):
        items = []

        for area in virtual_areas or []:
            top, bottom = area
            height = max(1.0, top - bottom)
            center = (top + bottom) / 2
            items.append(
                {
                    "nw": None,
                    "center": center,
                    "ideal": center,
                    "height": height,
                    "weight": 1e9,
                    "fixed": True,
                }
            )

        for nw in layer_nodes:
            height = self._layout_height(nw)
            ideal_center = float(nw.target_y - height / 2)
            items.append(
                {
                    "nw": nw,
                    "center": ideal_center,
                    "ideal": ideal_center,
                    "height": height,
                    "weight": self._priority_weight(getattr(nw, "priority", 2)),
                    "fixed": False,
                }
            )

        if not items:
            return

        max_w = (
            max(it["weight"] for it in items if not it["fixed"])
            if any(not it["fixed"] for it in items)
            else 1.0
        )

        # More nodes -> more iterations needed to fully resolve overlaps (esp. after anchor pulls).
        solve_iters = min(60, max(20, len(layer_nodes) * 2))
        for _ in range(solve_iters):
            items.sort(key=lambda it: it["center"], reverse=True)

            for i in range(len(items) - 1):
                upper = items[i]
                lower = items[i + 1]
                min_sep = (upper["height"] + lower["height"]) / 2 + self.margin
                dist = upper["center"] - lower["center"]
                if dist >= min_sep:
                    continue

                delta = (min_sep - dist)

                upper_fixed = upper["fixed"]
                lower_fixed = lower["fixed"]

                if upper_fixed and lower_fixed:
                    continue
                if upper_fixed and not lower_fixed:
                    lower["center"] -= delta
                    continue
                if lower_fixed and not upper_fixed:
                    upper["center"] += delta
                    continue

                wu = upper["weight"]
                wl = lower["weight"]
                total = wu + wl
                upper["center"] += delta * (wl / total)
                lower["center"] -= delta * (wu / total)

            for it in items:
                if it["fixed"]:
                    continue
                # Anchor pull. Keep modest to avoid reintroducing overlaps late in iterations.
                k = 0.12 * (it["weight"] / max_w)
                it["center"] += (it["ideal"] - it["center"]) * k

        # Final strict sweep to guarantee no overlaps remain.
        items.sort(key=lambda it: it["center"], reverse=True)
        for i in range(len(items) - 1):
            upper = items[i]
            lower = items[i + 1]
            min_sep = (upper["height"] + lower["height"]) / 2 + self.margin
            dist = upper["center"] - lower["center"]
            if dist >= min_sep:
                continue

            delta = (min_sep - dist)
            if upper["fixed"] and lower["fixed"]:
                continue
            if upper["fixed"] and not lower["fixed"]:
                lower["center"] -= delta
                continue
            if lower["fixed"] and not upper["fixed"]:
                upper["center"] += delta
                continue

            wu = upper["weight"]
            wl = lower["weight"]
            total = wu + wl
            upper["center"] += delta * (wl / total)
            lower["center"] -= delta * (wu / total)

        for it in items:
            if it["nw"] is None:
                continue
            nw = it["nw"]
            nw.posW.y = it["center"] + it["height"] / 2

    def _final_polish(self, iterations: int = 8):
        if iterations <= 0:
            return

        depths = sorted(self.depth_groups.keys())

        for _ in range(iterations):
            desired_center_by_ptr = {}
            for d in depths:
                for nw in self.depth_groups[d]:
                    my_center = nw.posW.y - nw.height / 2
                    force = 0.0
                    count = 0

                    for t in nw.to_nodes:
                        force += (t.posW.y - t.height / 2) - my_center
                        count += 1
                    for f in nw.from_nodes:
                        force += (f.posW.y - f.height / 2) - my_center
                        count += 1

                    if count > 0:
                        desired_center_by_ptr[nw.as_pointer()] = my_center + (force / count) * 0.12
                    else:
                        desired_center_by_ptr[nw.as_pointer()] = my_center

            for d in depths:
                layer = self.depth_groups[d]
                if not layer:
                    continue

                centers = [(nw, desired_center_by_ptr[nw.as_pointer()]) for nw in layer]
                centers.sort(key=lambda x: x[1], reverse=True)

                for i in range(len(centers) - 1):
                    a, ca = centers[i]
                    b, cb = centers[i + 1]
                    min_sep = (self._layout_height(a) + self._layout_height(b)) / 2 + self.margin
                    dist = ca - cb
                    if dist >= min_sep:
                        continue
                    push = (min_sep - dist) * 0.5
                    centers[i] = (a, ca + push)
                    centers[i + 1] = (b, cb - push)

                for nw, center in centers:
                    nw.target_y = center + nw.height / 2

                self._solve_layer_centers(layer, self._virtual_occupied_by_depth.get(d, []))

    def apply_layout(self, root_w):

        self._build_virtual_occupied()
        sorted_depths = sorted(self.depth_groups.keys())

        for d in sorted_depths:
            layer_nodes = self.depth_groups[d]
            self.set_node_priority(d)

            layer_nodes.sort(key=lambda x: (x.target_y, abs(x.target_y - root_w.posW.y)), reverse=True)

            for nw in layer_nodes:
                if nw.next_layer_nodes:
                    try:
                        base_x_bias = min(nodeW.posW.x for nodeW in self.depth_groups[d-1])
                        nw.posW.x = base_x_bias - nw.width * (1 - 1 / 6)
                    except ValueError:
                        pass

            self._solve_layer_centers(layer_nodes, self._virtual_occupied_by_depth.get(d, []))

            for nw in layer_nodes:
                nw.SetWorldPos(nw.posW.x, nw.posW.y)

        self._final_polish(iterations=8)
