import adsk.core
import adsk.fusion
import traceback

from .commands import generativeDesign, baseContourFeet

_commands = [generativeDesign, baseContourFeet]


def run(context):
    try:
        for cmd in _commands:
            cmd.start()
    except Exception:
        app = adsk.core.Application.get()
        if app:
            app.userInterface.messageBox(
                'Erreur au démarrage du plugin:\n{}'.format(traceback.format_exc())
            )


def stop(context):
    try:
        for cmd in _commands:
            cmd.stop()
    except Exception:
        pass
