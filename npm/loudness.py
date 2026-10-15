# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Medición de volumen percibido (LUFS, norma ITU-R BS.1770) y compresor.

- measure(): cuánto "suena" un archivo, para igualar el volumen de todos.
- Compressor: baja los picos de la mezcla para que no sature en Discord/OBS.

Solo usa numpy (sin scipy): el filtro K de la norma se aplica en frecuencia.
"""
import math

SR = 48000

# Presets del compresor: umbral (dB), relación, techo del limitador (dB)
PRESETS = {
    "suave": (-12.0, 2.0, -1.0),
    "media": (-18.0, 3.0, -1.0),
    "fuerte": (-24.0, 6.0, -2.0),
}
PRESET_NAMES = [("suave", "Suave"), ("media", "Media"), ("fuerte", "Fuerte"),
                ("custom", "Personalizada")]

# Coeficientes de la norma BS.1770 a 48 kHz: estante de agudos + pasa-altos RLB
_PRE = ([1.53512485958697, -2.69169618940638, 1.19839281085285],
        [1.0, -1.69065929318241, 0.73248077421585])
_RLB = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])

MAX_SECONDS = 600      # se analizan como máximo los primeros 10 minutos
GAIN_MIN, GAIN_MAX = -24.0, 12.0


def _response(np, n):
    """|H(f)| del filtro K para una FFT real de n muestras."""
    w = 2 * np.pi * np.fft.rfftfreq(n)        # radianes por muestra
    z1 = np.exp(-1j * w)
    z2 = z1 * z1
    h = np.ones_like(z1)
    for b, a in (_PRE, _RLB):
        h = h * (b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)
    return np.abs(h)


def measure(np, data):
    """Volumen integrado en LUFS de un audio estéreo float32 a 48 kHz
    (forma (n, 2)). Devuelve None si es silencio."""
    if data is None or len(data) == 0:
        return None
    data = data[:SR * MAX_SECONDS]
    n = len(data)
    nfft = 1 << max(10, (n - 1).bit_length())
    mag = _response(np, nfft)
    power = None
    for c in range(data.shape[1]):
        spec = np.fft.rfft(data[:, c].astype(np.float64), nfft) * mag
        y = np.fft.irfft(spec, nfft)[:n]
        p = y * y
        power = p if power is None else power + p
    block, hop = int(0.4 * SR), int(0.1 * SR)
    if n < block:
        z = np.array([power.mean()])
    else:
        cs = np.concatenate(([0.0], np.cumsum(power)))
        starts = np.arange(0, n - block + 1, hop)
        z = (cs[starts + block] - cs[starts]) / block
    with np.errstate(divide="ignore"):
        lk = -0.691 + 10 * np.log10(np.maximum(z, 1e-20))
    z = z[lk > -70.0]                              # puerta absoluta
    if len(z) == 0:
        return None
    rel = -0.691 + 10 * math.log10(float(z.mean())) - 10.0
    with np.errstate(divide="ignore"):
        lk = -0.691 + 10 * np.log10(np.maximum(z, 1e-20))
    z = z[lk > rel]                                # puerta relativa
    if len(z) == 0:
        return None
    return round(-0.691 + 10 * math.log10(float(z.mean())), 1)


def norm_gain_db(lufs, target) -> float:
    """Ajuste (dB) para llevar un sonido de `lufs` al objetivo."""
    if lufs is None:
        return 0.0
    return max(GAIN_MIN, min(GAIN_MAX, float(target) - float(lufs)))


def db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def lin_to_db(x: float) -> float:
    return 20.0 * math.log10(x) if x > 1e-9 else -math.inf


def comp_params(settings: dict):
    """(umbral, relación, techo) según el preset elegido."""
    c = settings.get("compressor") or {}
    p = c.get("preset", "media")
    if p in PRESETS:
        return PRESETS[p]
    return (float(c.get("thr", -18.0)), max(1.0, float(c.get("ratio", 3.0))),
            min(0.0, float(c.get("ceil", -1.0))))


def curve(level_db, thr, ratio):
    """Nivel de salida de la curva estática del compresor (para dibujarla)."""
    if level_db <= thr:
        return level_db
    return thr + (level_db - thr) / ratio


class Compressor:
    """Compresor por bloques (10 ms) + limitador de picos.

    Por bloque: detecta el nivel RMS, calcula cuánto bajar según la curva,
    suaviza (ataque rápido, relajación lenta), y si un pico pasaría del techo
    baja de inmediato. La ganancia se interpola dentro del bloque para que
    no se escuchen saltos."""

    def __init__(self, np):
        self.np = np
        self.env = -120.0
        self.gain = 1.0
        self.gr_db = 0.0
        self.a_att = self.a_rel = 0.0
        self._dt = None

    def process(self, x, thr, ratio, ceil_db):
        np = self.np
        dt = len(x) / SR
        if dt != self._dt:                         # el tamaño del bloque puede variar
            self._dt = dt
            self.a_att = math.exp(-dt / 0.005)
            self.a_rel = math.exp(-dt / 0.150)
        rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
        level = lin_to_db(rms) if rms > 0 else -120.0
        a = self.a_att if level > self.env else self.a_rel
        self.env = a * self.env + (1 - a) * level
        over = self.env - thr
        gr = over * (1 - 1 / ratio) if over > 0 else 0.0
        target = db_to_lin(-gr)
        peak = float(np.max(np.abs(x))) if len(x) else 0.0
        ceil = db_to_lin(ceil_db)
        if peak * target > ceil:
            target = ceil / peak                   # limitador: baja de inmediato
        elif target > self.gain:                   # al soltar, sube despacio
            target = self.gain + (target - self.gain) * (1 - self.a_rel)
        ramp = np.linspace(self.gain, target, len(x), dtype=np.float32)[:, None]
        x *= ramp
        np.clip(x, -ceil, ceil, out=x)
        self.gain = target
        self.gr_db = -lin_to_db(target) if target < 1 else 0.0
        return x
