#节点包装器，用于包装节点对象，并提供节点相关属性和方法
class posWorld:
    def __init__(self) -> None:
        self.x=0
        self.y=0
class NodeW:
    def __init__(self, node):
        self.node = node
        self.depth = 0
        self.out_links_count = 0  
        self.priority = 2         
        self.target_y = 0
        # self.is_processed = False 

        self.next_layer_nodes= []
        self.to_nodes = []       
        self.from_nodes = []

        self.posW=posWorld()
        self.posW.x=self.node.location.x
        self.posW.y=self.node.location.y

        cur_node=self.node
        while cur_node.parent:
            parent_node=cur_node.parent
            self.posW.x+=parent_node.location.x
            self.posW.y+=parent_node.location.y
            cur_node=parent_node      

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

    def SetWorldPos(self,x,y):

        cur_node=self.node
        while cur_node.parent:
            parent_node=cur_node.parent
            x-=parent_node.location.x
            y-=parent_node.location.y
            cur_node=parent_node 

        self.node.location.x=x
        self.node.location.y=y