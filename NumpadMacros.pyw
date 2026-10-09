# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Numpad Macros — convierte un numpad USB en un panel de sonidos y atajos.

Para usarlo desde el código fuente: python NumpadMacros.pyw
Para compilar la app: ver README.md (sección «Compilar desde el código»).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from npm.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
