import os

import dotbot

class Cond(dotbot.Plugin):
    """Check that a condition has been met."""

    _directive = "if"

    def can_handle(self, directive):
        return directive == self._directive

    def handle(self, directive, data):
        if directive != self._directive:
            raise ValueError("If cannot handle directive {}".format(directive))

        self._process_conditions(data)
    
    def _process_conditions(self, data):
        self._context.defaults().get("if", {})
        cond_all = data.get("all")
        cond_any = data.get("any")
        ...
