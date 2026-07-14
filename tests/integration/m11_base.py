class BaseMonitor:
    def __init__(self, seed):
        self.seed = seed

    def sample(self):
        return 17

    def notify(self):
        self.notified = True
