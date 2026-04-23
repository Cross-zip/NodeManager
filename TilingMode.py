from collections import defaultdict
import bpy

try:
    from .NodeWrapper import NodeW
except ImportError:
    from NodeWrapper import NodeW


class _UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def add(self, x):
        if x in self.parent:
            return
        self.parent[x] = x
        self.rank[x] = 0

    def find(self, x):
        p = self.parent.get(x, x)
        if p != x:
            self.parent[x] = self.find(p)
        return self.parent.get(x, x)

    def union(self, a, b):
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        rka = self.rank.get(ra, 0)
        rkb = self.rank.get(rb, 0)
        if rka < rkb:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if rka == rkb:
            self.rank[ra] = rka + 1


class NodeManager:
    """
    Flowchart layout for ShaderNodeTree:
    1) Build weighted graph and identify backbone (Output.Surface chain).
    2) Cluster nodes into blocks using strong-link union-find.
    3) Layout by depth (X) with cluster-aware Y ordering and strict overlap solving.
    """

    def __init__(self, tree):
        self.node_instances = defaultdict(list)
        self.depth_groups = defaultdict(list)
        self.tree = tree

        # Spacing
        self.margin_y = 90
        self.margin_y_between_blocks = 140
        self.margin_x = 260

        # Clustering
        self.strong_edge_threshold = 2.4

        self._virtual_occupied_by_depth = defaultdict(list)
        self._cluster_id_by_ptr = {}
        self._cluster_center_y = {}

    # -------- wrappers / links --------
    def get_wrapper(self, node):
        ptr = node.as_pointer()
        if ptr not in self.node_instances:
            self.node_instances[ptr] = NodeW(node)
        return self.node_instances[ptr]

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

    # -------- hierarchy (reuse existing patterns) --------
    def initialize_hierarchy(self, node):
        curr_w = self.get_wrapper(node)
        if hasattr(curr_w, "_init_flag"):
            curr_w.out_links_count += 1
            return curr_w
        curr_w._init_flag = True
        curr_w.out_links_count = 1

        for link in self.loop_in_links(curr_w):
            from_node = link.from_node
            if from_node is None:
                continue
            from_w = self.initialize_hierarchy(from_node)
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

    # -------- material-flow specific helpers --------
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
            return node_w.posW.y - node_w.layout_height() / 2

        idx = self._socket_index(node_w.node, socket, is_input=is_input)
        gap = node_w.layout_height() / (count + 1)
        return node_w.posW.y - gap * (idx + 1)

    def _is_material_output(self, node) -> bool:
        return getattr(node, "type", "") == "OUTPUT_MATERIAL"

    def _backbone_nodes(self):
        """
        Trace Output.Surface chain backwards (single-link along inputs),
        returning a set of node pointers on backbone.
        """
        outputs = [n for n in self.tree.nodes if self._is_material_output(n)]
        if not outputs:
            return set()

        out = outputs[0]
        out_w = self.get_wrapper(out)

        # Prefer Surface socket
        surface = None
        for s in out.inputs:
            if getattr(s, "name", "") == "Surface":
                surface = s
                break
        if surface is None and out.inputs:
            surface = out.inputs[0]

        backbone = {out_w.ptr}
        stack = []
        if surface and surface.links:
            stack.append(surface.links[0].from_node)

        while stack:
            n = stack.pop()
            if n is None:
                continue
            nw = self.get_wrapper(n)
            if nw.ptr in backbone:
                continue
            backbone.add(nw.ptr)

            # Follow "main" input: first linked input, prefer Shader-type input named "Shader" or "BSDF"
            next_node = None
            preferred = None
            for inp in n.inputs:
                if not inp.links:
                    continue
                name = getattr(inp, "name", "").lower()
                if "shader" in name or "bsdf" in name or "surface" in name:
                    preferred = inp.links[0].from_node
                    break
                if next_node is None:
                    next_node = inp.links[0].from_node
            stack.append(preferred if preferred is not None else next_node)

        return backbone

    def _edge_weight(self, link) -> float:
        fn = link.from_node
        tn = link.to_node
        if fn is None or tn is None:
            return 0.0

        fw = self.get_wrapper(fn)
        tw = self.get_wrapper(tn)

        if fw.role == "reroute" or tw.role == "reroute":
            return 0.2

        w = 1.0

        # Backbone-ish connections get stronger
        to_name = getattr(link.to_socket, "name", "").lower()
        if "surface" in to_name or "shader" in to_name or "bsdf" in to_name:
            w += 1.6
        elif "volume" in to_name or "displacement" in to_name:
            w += 1.2
        else:
            w += 0.4

        # Role coupling
        if fw.role in {"shader", "shader_mix"} and tw.role in {"shader", "shader_mix", "output"}:
            w += 0.8
        if fw.role in {"texture", "mapping"} and tw.role in {"shader", "math"}:
            w += 0.4
        if fw.role in {"constant"}:
            w -= 0.2

        # Fan-out dampening (shared sources shouldn't glue the whole graph)
        try:
            fan_out = len(fn.outputs[0].links) if fn.outputs else 0
        except Exception:
            fan_out = 0
        if fan_out >= 3:
            w *= 0.65

        return max(0.0, w)

    def _cluster_blocks(self, backbone_ptrs):
        uf = _UnionFind()
        nodes = []
        for n in self.tree.nodes:
            nw = self.get_wrapper(n)
            uf.add(nw.ptr)
            nodes.append(nw)

        # Strong links union
        for link in self.tree.links:
            w = self._edge_weight(link)
            if w < self.strong_edge_threshold:
                continue
            a = self.get_wrapper(link.from_node).ptr
            b = self.get_wrapper(link.to_node).ptr
            uf.union(a, b)

        # Ensure backbone is strongly connected as one block (flow readability)
        backbone_ptrs = set(backbone_ptrs or [])
        bb = list(backbone_ptrs)
        for i in range(1, len(bb)):
            uf.union(bb[0], bb[i])

        # Assign stable small cluster ids
        root_to_id = {}
        next_id = 0
        for nw in nodes:
            r = uf.find(nw.ptr)
            if r not in root_to_id:
                root_to_id[r] = next_id
                next_id += 1
            self._cluster_id_by_ptr[nw.ptr] = root_to_id[r]

    def _compute_cluster_centers(self):
        acc = defaultdict(float)
        cnt = defaultdict(int)
        for depth, nodes in self.depth_groups.items():
            for nw in nodes:
                cid = self._cluster_id_by_ptr.get(nw.ptr, -1)
                acc[cid] += float(nw.target_y)
                cnt[cid] += 1
        for cid, s in acc.items():
            self._cluster_center_y[cid] = s / max(1, cnt[cid])

    # -------- virtual blockers for long wires --------
    def _build_virtual_occupied(self):
        self._virtual_occupied_by_depth = defaultdict(list)

        for depth, nodes in self.depth_groups.items():
            for nw in nodes:
                for tnw in nw.to_nodes:
                    span = nw.depth - tnw.depth
                    if span <= 1:
                        continue

                    from_center = nw.posW.y - nw.layout_height() / 2
                    to_center = tnw.posW.y - tnw.layout_height() / 2
                    denom = max(1, span)

                    virtual_h = max(18.0, self.margin_y * 0.55)
                    for inter_depth in range(tnw.depth + 1, nw.depth):
                        t = (inter_depth - tnw.depth) / denom
                        center = to_center + (from_center - to_center) * t
                        top = center + virtual_h / 2
                        self._virtual_occupied_by_depth[inter_depth].append([top, top - virtual_h])

    # -------- y solver (strict, block-aware) --------
    def _solve_layer_centers(self, layer_nodes, virtual_areas):
        items = []

        # fixed blockers
        for area in virtual_areas or []:
            top, bottom = area
            height = max(1.0, top - bottom)
            center = (top + bottom) / 2
            items.append({"nw": None, "center": center, "ideal": center, "height": height, "fixed": True})

        for nw in layer_nodes:
            height = nw.layout_height()
            ideal_center = float(nw.target_y - height / 2)
            items.append(
                {
                    "nw": nw,
                    "center": ideal_center,
                    "ideal": ideal_center,
                    "height": height,
                    "fixed": False,
                }
            )

        if not items:
            return

        def sep(a, b):
            # bigger gap between different clusters
            if a["nw"] is None or b["nw"] is None:
                return self.margin_y
            ca = self._cluster_id_by_ptr.get(a["nw"].ptr, -1)
            cb = self._cluster_id_by_ptr.get(b["nw"].ptr, -1)
            return self.margin_y_between_blocks if ca != cb else self.margin_y

        solve_iters = min(80, max(30, len(layer_nodes) * 3))
        for _ in range(solve_iters):
            items.sort(key=lambda it: it["center"], reverse=True)

            for i in range(len(items) - 1):
                upper = items[i]
                lower = items[i + 1]
                min_sep = (upper["height"] + lower["height"]) / 2 + sep(upper, lower)
                dist = upper["center"] - lower["center"]
                if dist >= min_sep:
                    continue

                delta = min_sep - dist

                if upper["fixed"] and lower["fixed"]:
                    continue
                if upper["fixed"] and not lower["fixed"]:
                    lower["center"] -= delta
                    continue
                if lower["fixed"] and not upper["fixed"]:
                    upper["center"] += delta
                    continue

                upper["center"] += delta * 0.5
                lower["center"] -= delta * 0.5

            # light anchor pull to avoid drift, but not enough to re-overlap
            for it in items:
                if it["fixed"]:
                    continue
                it["center"] += (it["ideal"] - it["center"]) * 0.08

        # final strict sweep (guarantee)
        items.sort(key=lambda it: it["center"], reverse=True)
        for i in range(len(items) - 1):
            upper = items[i]
            lower = items[i + 1]
            min_sep = (upper["height"] + lower["height"]) / 2 + sep(upper, lower)
            dist = upper["center"] - lower["center"]
            if dist >= min_sep:
                continue
            delta = min_sep - dist
            if upper["fixed"] and lower["fixed"]:
                continue
            if upper["fixed"] and not lower["fixed"]:
                lower["center"] -= delta
            elif lower["fixed"] and not upper["fixed"]:
                upper["center"] += delta
            else:
                upper["center"] += delta * 0.5
                lower["center"] -= delta * 0.5

        for it in items:
            if it["nw"] is None:
                continue
            nw = it["nw"]
            nw.posW.y = it["center"] + it["height"] / 2

    # -------- main layout --------
    def _compute_targets(self):
        # target_y: weighted by downstream socket Y (like AlignMode), but also fall back to current
        for depth, nodes in self.depth_groups.items():
            for nw in nodes:
                nw.target_y = nw.posW.y
                if not nw.to_nodes:
                    continue

                ys = []
                for link in self.loop_out_links(nw):
                    to_node = link.to_node
                    if to_node is None:
                        continue
                    tnw = self.get_wrapper(to_node)
                    if nw.depth - tnw.depth != 1:
                        continue
                    ys.append(self._socket_world_y(tnw, link.to_socket, is_input=True))
                if ys:
                    nw.target_y = sum(ys) / len(ys)

    def apply_layout(self, active_node_wrapper):
        # 1) targets + backbone + clusters
        self._compute_targets()
        backbone = self._backbone_nodes()
        self._cluster_blocks(backbone)
        self._compute_cluster_centers()

        # 2) virtual blockers
        self._build_virtual_occupied()

        # 3) place X by depth, and solve Y with block-aware ordering
        sorted_depths = sorted(self.depth_groups.keys())
        if not sorted_depths:
            return

        # anchor x at active node (treated as "focus")
        base_x = float(active_node_wrapper.posW.x)

        for d in sorted_depths:
            layer = self.depth_groups[d]
            if not layer:
                continue

            for nw in layer:
                nw.posW.x = base_x - d * self.margin_x

            # order: by cluster center then by own target_y
            def key(nw):
                cid = self._cluster_id_by_ptr.get(nw.ptr, -1)
                return (self._cluster_center_y.get(cid, nw.target_y), nw.target_y)

            layer.sort(key=key, reverse=True)
            self._solve_layer_centers(layer, self._virtual_occupied_by_depth.get(d, []))

            for nw in layer:
                nw.SetWorldPos(nw.posW.x, nw.posW.y)