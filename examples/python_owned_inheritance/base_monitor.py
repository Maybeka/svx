class BaseMonitor:
    def __init__(self, seed):
        self.seed = seed
        self.notified = False

    def sample(self):
        return 17

    def notify(self):
        self.notified = True
