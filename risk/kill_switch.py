class KillSwitch:

    def __init__(self):

        self.enabled = False

    def stop(self):

        self.enabled = True

    def resume(self):

        self.enabled = False

    def active(self):

        return self.enabled