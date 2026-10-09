# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Crea el "enviador" de atajos adecuado para el sistema operativo."""
from .capture import PLATFORM


def make_sender():
    """Devuelve (sender, error). Si no se puede crear, sender es None y error explica por qué."""
    try:
        if PLATFORM == "win":
            from .send_win import KeySender
            return KeySender(), None
        if PLATFORM == "linux":
            from .send_linux import UinputSender
            return UinputSender(), None
        from .send_mac import QuartzSender
        return QuartzSender(), None
    except ImportError as e:
        return None, f"Falta una dependencia para enviar teclas: {e.name}"
    except Exception as e:
        return None, str(e)
