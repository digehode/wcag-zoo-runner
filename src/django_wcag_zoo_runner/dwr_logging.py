""" Very simple module for selective output based on verbosity level """

from termcolor import colored

DEBUG = 4
FULL = 3
INFO = 2
WARNING = 1
ERROR = 0

labels = {
    FULL: "FULL",
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
}

styles = {
    FULL: "green",
    DEBUG: "yellow",
    INFO: "blue",
    WARNING: "light_red",
    ERROR: "red",
}


class Logger:
    """Controls output based on a verbosit threshold"""

    def __init__(self, level=4, colour=True):
        """Initialise Logger

        Parameters
        ----------

        level : int

          Threshold level for logging. Won't output messages above
          this level.  Constants DEBUG, FULL, INFO, WARNING and ERROR
          are the typical levels and have numeric values 4, 3, 2, 1
          and 0

        colour : bool

          Use colour output. see .styles dict for colours used for
          levels
        """
        self.colour = colour
        self.level = level

    def log(self, message: str, level: int):
        """Display message if level <= threshold"""
        if level > self.level:
            return
        text = message
        if self.colour:
            style = styles[level]
            text = colored(message, style)
        print(text)

    def debug(self, message):
        """Propose a message at DEBUG level"""
        self.log(message, DEBUG)

    def full(self, message):
        """Propose a message at FULL level"""
        self.log(message, FULL)

    def warning(self, message):
        """Propose a message at WARNING level"""
        self.log(message, WARNING)

    def info(self, message):
        """Propose a message at INFO level"""
        self.log(message, INFO)

    def error(self, message):
        """Propose a message at ERROR level"""
        self.log(message, ERROR)
