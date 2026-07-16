"""The composed `AstrologyCompute` facade (§4 split).

`AstrologyCompute` is exactly the class it always was — every method is inherited
verbatim from a concern-scoped mixin, so the public API (and behaviour) is
unchanged. The golden tests in tests/test_golden.py pin that.
"""
from .engine import ENGINE_AVAILABLE

from .compute_charts import ChartsMixin
from .compute_dashas import DashasMixin
from .compute_panchanga import PanchangaMixin
from .compute_muhurta import MuhurtaMixin
from .compute_kp import KpMixin
from .compute_tajaka import TajakaMixin
from .compute_transits import TransitsMixin
from .compute_digests import DigestsMixin
from .compute_strength import StrengthMixin
from .compute_match import MatchMixin
from .compute_points import PointsMixin
from .compute_reference import ReferenceMixin
from .compute_rectification import RectificationMixin
from .compute_geo import GeoMixin
from . import compute_charts
from . import compute_dashas
from . import compute_panchanga
from . import compute_muhurta
from . import compute_kp
from . import compute_tajaka
from . import compute_transits
from . import compute_digests
from . import compute_strength
from . import compute_match
from . import compute_points
from . import compute_reference
from . import compute_rectification
from . import compute_geo


class AstrologyCompute(ChartsMixin, DashasMixin, PanchangaMixin, MuhurtaMixin, KpMixin, TajakaMixin, TransitsMixin, DigestsMixin, StrengthMixin, MatchMixin, PointsMixin, ReferenceMixin, RectificationMixin, GeoMixin):
    """Facade over the PyJHora engine — all compute entry points the web app uses.

    Composed from concern-scoped mixins (charts / dashas / panchanga / muhurta /
    kp / tajaka / transits / digests / strength / match / points / reference /
    rectification / geo). All members are static; there is no instance state.
    """
    ENGINE_AVAILABLE = ENGINE_AVAILABLE


# Late-bind the composed class into each mixin module. The moved method bodies
# call sibling helpers as `AstrologyCompute.x(...)`, which resolves from their own
# module globals at CALL time — so binding it here (after the class exists) keeps
# those cross-module references working without touching a single body.
for _mod in (compute_charts, compute_dashas, compute_panchanga, compute_muhurta, compute_kp, compute_tajaka, compute_transits, compute_digests, compute_strength, compute_match, compute_points, compute_reference, compute_rectification, compute_geo,):
    _mod.AstrologyCompute = AstrologyCompute
