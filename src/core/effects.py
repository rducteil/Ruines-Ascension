class Effect:
    def __init__(self, name: str, duration: int, power: int):
        self.name = name
        self.duration = duration
        self.power = power
    
    def on_hit(self, ctx):
        pass
    def on_turn_end(self, ctx):
        pass