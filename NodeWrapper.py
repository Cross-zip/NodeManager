
class NodeW:
    def __init__(self, node):
        self.node = node
        self.depth = 0
        self.out_links_count = 0  
        self.priority = 2         
        self.target_y = 0
        self.is_processed = False 

        self.next_layer_nodes= []
        self.to_nodes = []       
        self.from_nodes = []      

    def __getattr__(self, name):
        return getattr(self.node, name)

    @property
    def height(self):
        if self.node.type == 'REROUTE':
            return 20
        return self.node.dimensions.y
    @property
    def width(self):
        if self.node.type == 'REROUTE':
            return 20
        return self.node.dimensions.x
