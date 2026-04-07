"""Technique registry — discovers and runs all border detection techniques."""
from .edge import TECHNIQUES as EDGE
from .color import TECHNIQUES as COLOR
from .morphological import TECHNIQUES as MORPHOLOGICAL
from .texture import TECHNIQUES as TEXTURE
from .statistical import TECHNIQUES as STATISTICAL
from .gradient import TECHNIQUES as GRADIENT
from .structural import TECHNIQUES as STRUCTURAL
from .adaptive import TECHNIQUES as ADAPTIVE
from .quantization import TECHNIQUES as QUANTIZATION

def get_all_techniques():
    all_techniques = []
    for module_techniques in [EDGE, COLOR, MORPHOLOGICAL, TEXTURE, STATISTICAL,
                              GRADIENT, STRUCTURAL, ADAPTIVE, QUANTIZATION]:
        all_techniques.extend(module_techniques)
    return all_techniques
