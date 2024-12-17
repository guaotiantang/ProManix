import inspect


class ScanError(Exception):
    def __init__(self, message, from_module=None, level=0):
        super().__init__(message)
        self.message = message
        self.from_module = from_module if from_module else inspect.currentframe().f_back.f_globals["__name__"]
        self.function = "" if from_module else f".{inspect.currentframe().f_back.f_code.co_name}"
        self.level = level

    def __str__(self):
        return f"ErrLevel({self.level}) From[{self.from_module}{self.function}] Error: {self.message}"
