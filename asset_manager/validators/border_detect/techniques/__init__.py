"""Technique registry — discovers and runs all border detection techniques."""
from border_detect.techniques.edge import TECHNIQUES as EDGE
from border_detect.techniques.color import TECHNIQUES as COLOR
from border_detect.techniques.morphological import TECHNIQUES as MORPHOLOGICAL
from border_detect.techniques.texture import TECHNIQUES as TEXTURE
from border_detect.techniques.statistical import TECHNIQUES as STATISTICAL
from border_detect.techniques.gradient import TECHNIQUES as GRADIENT
from border_detect.techniques.structural import TECHNIQUES as STRUCTURAL
from border_detect.techniques.adaptive import TECHNIQUES as ADAPTIVE
from border_detect.techniques.quantization import TECHNIQUES as QUANTIZATION

def get_all_techniques():
    all_techniques = []
    for module_techniques in [EDGE, COLOR, MORPHOLOGICAL, TEXTURE, STATISTICAL,
                              GRADIENT, STRUCTURAL, ADAPTIVE, QUANTIZATION]:
        all_techniques.extend(module_techniques)
    return all_techniques
