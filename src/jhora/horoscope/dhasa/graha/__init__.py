#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Make '...shashtisama' import resolve to the same module as '...shastihayani'
from . import shastihayani as _shastihayani
import sys as _sys

_sys.modules[__name__ + '.shashtisama'] = _shastihayani

# Optional: help IDEs & static analyzers
try:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from . import shastihayani as shashtisama  # for type hints / code completion
except Exception:
    pass